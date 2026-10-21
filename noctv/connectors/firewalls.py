"""Read-only management inventory; never infer forwarding or VPN health."""
import http.client
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .http import JSONClient, SourceError
from ..model import now, web_url


class FirewallClient(JSONClient):
    """Reuse the project's verified TLS and redirect policy for POST/XML APIs."""

    def request(self, relative, payload=None, form=False, xml=False):
        target = urllib.parse.urljoin(self.base, relative)
        parsed = urllib.parse.urlsplit(target)
        if (parsed.scheme, parsed.netloc) != (self.origin.scheme, self.origin.netloc) or parsed.username or parsed.fragment:
            raise SourceError('untrusted_resource')
        headers = {**self.headers, 'Accept': 'application/xml' if xml else 'application/json'}
        body = None
        if payload is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
            body = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
        try:
            request = urllib.request.Request(target, data=body, headers=headers)
            with self.opener.open(request, timeout=10) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise SourceError('response_too_large')
            if xml:
                text = raw.decode('utf-8')
                # Reject DTDs/entities before parsing, including UTF-16/32 bypasses.
                if '<!' in text or '\x00' in text:
                    raise SourceError('unsafe_xml')
                return ET.fromstring(text)
            return json.loads(raw)
        except urllib.error.HTTPError as error:
            error.close()
            raise SourceError('http_' + str(error.code)) from None
        except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException, ET.ParseError, RecursionError):
            raise SourceError('connection_or_response_error') from None

    def get(self, relative):
        return self.request(relative)


def credential(config, key, default):
    value = os.environ.get(config.get(key, default))
    if not value:
        raise SourceError('missing_credentials')
    return value


def client(config, default_url, headers=None):
    try:
        return FirewallClient(credential(config, 'url_env', default_url), headers, config.get('ca_file'))
    except (OSError, ValueError):
        raise SourceError('invalid_tls_or_url_configuration') from None


def text(value):
    return value if isinstance(value, str) else ''


def device(config, native, name='', model='', ip='', management='unknown', kind='firewall'):
    if not isinstance(native, str) or not native:
        raise SourceError('missing_device_id')
    override = config.get('devices', {}).get(native, {})
    return {'id': config['id'] + ':' + native, 'name': override.get('name') or text(name) or native,
            'type': kind, 'site': override.get('site', config.get('site_map', {}).get(native, 'unassigned')),
            'ip': text(ip), 'model': text(model), 'state': 'unknown', 'management_state': management,
            'observed_at': now(), 'ports': [], 'metrics': {}, 'root': override.get('root') is True,
            'web_url': web_url(override.get('web_url'))}


def batch(devices, warnings=None):
    return {'devices': devices, 'links': [], 'warnings': warnings or [], 'capabilities': ['inventory', 'management']}


def rows(payload, key):
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list) or any(not isinstance(row, dict) for row in payload[key]):
        raise SourceError('invalid_inventory_response')
    return payload[key]


def count(value):
    try:
        if isinstance(value, bool) or str(int(value)) != str(value) or int(value) < 0:
            raise ValueError
        return int(value)
    except (TypeError, ValueError, OverflowError):
        raise SourceError('invalid_pagination') from None


class FortiGate:
    def __init__(self, config):
        self.config = config
        token = credential(config, 'token_env', 'FORTIGATE_TOKEN')
        self.client = client(config, 'FORTIGATE_URL', {'Authorization': 'Bearer ' + token})

    def collect(self):
        payload = self.client.get('api/v2/monitor/system/status')
        if not isinstance(payload, dict) or payload.get('status') != 'success' or not isinstance(payload.get('results'), dict):
            raise SourceError('invalid_fortigate_status')
        result = payload['results']
        return batch([device(self.config, payload.get('serial'), result.get('hostname'), result.get('model'), management='up')])


class PANOS:
    def __init__(self, config):
        self.config = config
        key = credential(config, 'token_env', 'PANOS_API_KEY')
        self.client = client(config, 'PANOS_URL', {'X-PAN-KEY': key})

    def collect(self):
        response = self.client.request('api/', {'type': 'op', 'cmd': '<show><system><info></info></system></show>'}, form=True, xml=True)
        system = response.find('./result/system')
        if response.tag != 'response' or response.get('status') != 'success' or system is None:
            raise SourceError('invalid_panos_status')
        return batch([device(self.config, system.findtext('serial'), system.findtext('hostname'),
                             system.findtext('model'), system.findtext('ip-address'), management='up')])


class CheckPoint:
    def __init__(self, config):
        self.config = config
        self.user = credential(config, 'username_env', 'CHECKPOINT_USERNAME')
        self.password = credential(config, 'password_env', 'CHECKPOINT_PASSWORD')
        self.client = client(config, 'CHECKPOINT_URL')

    def collect(self):
        login = {'user': self.user, 'password': self.password}
        if self.config.get('domain'):
            login['domain'] = self.config['domain']
        response = self.client.request('web_api/login', login)
        if not isinstance(response, dict) or not isinstance(response.get('sid'), str) or not response['sid']:
            raise SourceError('authentication_failed')
        self.client.headers['X-chkp-sid'] = response['sid']
        devices, warnings = [], []
        try:
            offset = 0
            for _ in range(10):
                page = self.client.request('web_api/show-gateways-and-servers', {'limit': 100, 'offset': offset, 'details-level': 'standard'})
                objects = rows(page, 'objects')
                total = count(page.get('total'))
                for obj in objects:
                    # Management hosts are not firewall engines; retain their real type.
                    kind = 'server' if obj.get('type') == 'checkpoint-host' else 'firewall'
                    devices.append(device(self.config, obj.get('uid'), obj.get('name'), obj.get('type'), obj.get('ipv4-address'), kind=kind))
                offset += len(objects)
                if offset >= total:
                    break
                if not objects:
                    raise SourceError('invalid_pagination')
            else:
                raise SourceError('pagination_limit')
        finally:
            try:
                self.client.request('web_api/logout', {})
            except SourceError:
                warnings.append('logout_failed')
            finally:
                self.client.headers.pop('X-chkp-sid', None)
        return batch(devices, warnings)


class SophosCentral:
    def __init__(self, config):
        self.config = config
        self.client_id = credential(config, 'client_id_env', 'SOPHOS_CLIENT_ID')
        self.client_secret = credential(config, 'client_secret_env', 'SOPHOS_CLIENT_SECRET')
        tenant = credential(config, 'tenant_id_env', 'SOPHOS_TENANT_ID')
        self.client = client(config, 'SOPHOS_URL', {'X-Tenant-ID': tenant})
        try:
            self.auth = FirewallClient('https://id.sophos.com/', ca_file=config.get('ca_file'))
        except (OSError, ValueError):
            raise SourceError('invalid_tls_or_url_configuration') from None

    def collect(self):
        token = self.auth.request('api/v2/oauth2/token', {'grant_type': 'client_credentials', 'scope': 'token',
                                 'client_id': self.client_id, 'client_secret': self.client_secret}, form=True)
        if not isinstance(token, dict) or not isinstance(token.get('access_token'), str) or not token['access_token']:
            raise SourceError('authentication_failed')
        self.client.headers['Authorization'] = 'Bearer ' + token['access_token']
        devices = []
        try:
            for page_number in range(1, 11):
                page = self.client.get('firewall/v1/firewalls?' + urllib.parse.urlencode({'page': page_number, 'pageSize': 100, 'pageTotal': 'true'}))
                objects = rows(page, 'items')
                pages = page.get('pages')
                if not isinstance(pages, dict):
                    raise SourceError('invalid_pagination')
                total = count(pages.get('total'))
                if count(pages.get('current')) != page_number:
                    raise SourceError('invalid_pagination')
                for obj in objects:
                    status = obj.get('status') or {}
                    connected = status.get('connected') if isinstance(status, dict) else None
                    management = 'up' if connected is True else 'down' if connected is False else 'unknown'
                    devices.append(device(self.config, obj.get('id'), obj.get('name') or obj.get('hostname'), obj.get('model'), management=management))
                if page_number >= total:
                    break
                if not objects:
                    raise SourceError('invalid_pagination')
            else:
                raise SourceError('pagination_limit')
        finally:
            self.client.headers.pop('Authorization', None)
        return batch(devices)
