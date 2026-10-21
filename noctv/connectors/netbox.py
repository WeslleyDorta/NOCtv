"""NetBox 4.5+ inventory via GET, authenticated with a v2 token."""
import os
from ipaddress import ip_interface
from urllib.parse import urljoin, urlsplit

from .http import JSONClient, SourceError
from ..model import web_url

MAX_PAGES = 100
MAX_DEVICES = 10000


def nested(row, key):
    value = row.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SourceError('invalid_device_response')
    return value


class NetBox:
    def __init__(self, config):
        self.config = config
        token = os.environ.get(config.get('token_env', 'NETBOX_TOKEN'))
        url = os.environ.get(config.get('url_env', 'NETBOX_URL'))
        if not token or not url:
            raise SourceError('missing_credentials')
        if any(c.isspace() for c in token):
            raise SourceError('invalid_credentials')
        self.client = JSONClient(url, {'Authorization': 'Bearer ' + token}, config.get('ca_file'), config.get('allow_http') is True)
        self.endpoint = urljoin(self.client.base, 'api/dcim/devices/')

    def collect(self):
        route = self.endpoint + '?limit=100&ordering=id&exclude=config_context'
        rows, visited = [], set()
        for _ in range(MAX_PAGES):
            if route in visited:
                raise SourceError('pagination_cycle')
            visited.add(route)
            payload = self.client.get(route)
            if not isinstance(payload, dict) or not isinstance(payload.get('results'), list) or 'next' not in payload:
                raise SourceError('invalid_devices_response')
            rows.extend(payload['results'])
            if len(rows) > MAX_DEVICES:
                raise SourceError('inventory_limit_exceeded')
            next_page = payload['next']
            if next_page is None:
                return self.normalize(rows)
            if not isinstance(next_page, str) or not next_page or any(c.isspace() for c in next_page):
                raise SourceError('invalid_pagination')
            try:
                route = urljoin(route, next_page)
                if urlsplit(route).path != urlsplit(self.endpoint).path:
                    raise SourceError('untrusted_resource')
            except ValueError:
                raise SourceError('invalid_pagination') from None
        raise SourceError('pagination_limit_exceeded')

    def normalize(self, rows):
        devices, seen = [], set()
        for row in rows:
            if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] <= 0:
                raise SourceError('invalid_device_response')
            native = str(row['id'])
            if native in seen:
                raise SourceError('duplicate_device')
            seen.add(native)
            override = self.config.get('devices', {}).get(native, {})
            kind = nested(row, 'device_type')
            vendor = nested(kind, 'manufacturer').get('name')
            site = nested(row, 'site').get('slug')
            primary = nested(row, 'primary_ip') or nested(row, 'primary_ip4') or nested(row, 'primary_ip6')
            try:
                address = primary.get('address')
                ip = str(ip_interface(address).ip) if isinstance(address, str) else ''
            except ValueError:
                ip = ''
            devices.append({'id': self.config['id'] + ':' + native,
                'name': override.get('name') or (row.get('name') if isinstance(row.get('name'), str) else '') or native,
                'ip': ip, 'vendor': override.get('vendor', vendor if isinstance(vendor, str) else ''),
                'model': kind.get('model') if isinstance(kind.get('model'), str) else '',
                'brand': override.get('brand'), 'type': override.get('type', 'device'),
                'site': override.get('site', self.config.get('site_map', {}).get(site if isinstance(site, str) else '', 'unassigned')),
                'web_url': web_url(override.get('web_url')), 'root': override.get('root') is True,
                'state': 'unknown', 'observed_at': None, 'metrics': {}, 'ports': []})
        return {'devices': devices, 'links': [], 'warnings': []}
