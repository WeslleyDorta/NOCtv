"""Zabbix 7.0 JSON-RPC: inventory and observed item values, never writes."""
import json
import os
import urllib.error
import urllib.request

from .http import JSONClient, SourceError
from ..model import number, stale, timestamp, web_url

DEFAULT_ITEMS = {'status': 'icmpping', 'latency_ms': 'icmppingsec',
                 'uptime_seconds': 'system.uptime', 'memory_percent': 'vm.memory.size[pused]'}
METRICS = {'latency_ms', 'uptime_seconds', 'cpu_percent', 'memory_percent', 'disk_percent', 'toner_percent', 'clients'}


class RPCClient(JSONClient):
    def __init__(self, url, token, ca_file=None, allow_http=False):
        if any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise SourceError('invalid_credentials')
        super().__init__(url, {'Authorization': 'Bearer ' + token}, ca_file, allow_http)
        self.endpoint = url

    def call(self, method, params):
        if method not in {'host.get', 'item.get'}:
            raise SourceError('method_not_allowed')
        request = urllib.request.Request(self.endpoint,
            data=json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params, 'id': 1}).encode(),
            headers={**self.headers, 'Content-Type': 'application/json-rpc', 'Accept': 'application/json'}, method='POST')
        try:
            with self.opener.open(request, timeout=10) as response:
                raw = response.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise SourceError('response_too_large')
                payload = json.loads(raw)
        except urllib.error.HTTPError as error:
            error.close()
            raise SourceError('http_' + str(error.code)) from None
        except (OSError, ValueError, urllib.error.URLError):
            raise SourceError('connection_or_response_error') from None
        if not isinstance(payload, dict) or payload.get('jsonrpc') != '2.0' or payload.get('id') != 1:
            raise SourceError('invalid_rpc_response')
        if 'error' in payload:
            # Never expose server error text: it can echo request credentials.
            error = payload['error']
            detail = str(error.get('data', '')).lower() if isinstance(error, dict) else ''
            rejected = any(s in detail for s in ('not authorized', 'session terminated', 'invalid api token', 'api token expired'))
            raise SourceError('authentication_rejected' if rejected else 'rpc_error')
        result = payload.get('result')
        if not isinstance(result, list) or any(not isinstance(row, dict) for row in result):
            raise SourceError('invalid_rpc_response')
        return result


class Zabbix:
    def __init__(self, config):
        self.config = config
        token = os.environ.get(config.get('token_env', 'ZABBIX_TOKEN'))
        url = os.environ.get(config.get('url_env', 'ZABBIX_URL'))
        if not token or not url:
            raise SourceError('missing_credentials')
        self.client = RPCClient(url, token, config.get('ca_file'), config.get('allow_http') is True)
        for settings in [config, *config.get('devices', {}).values()]:
            mapping = settings.get('item_map', {})
            if not isinstance(mapping, dict) or any(k not in METRICS | {'status'} or not isinstance(v, str) or not v for k, v in mapping.items()):
                raise SourceError('invalid_item_map')
            ports = settings.get('ports', [])
            if not isinstance(ports, list):
                raise SourceError('invalid_port_map')
            ids = set()
            for port in ports:
                if not isinstance(port, dict) or not isinstance(port.get('id'), str) or not port['id'] or port['id'] in ids or not isinstance(port.get('state_key'), str) or not port['state_key']:
                    raise SourceError('invalid_port_map')
                if str(port.get('up_value', '1')) == str(port.get('down_value', '2')):
                    raise SourceError('invalid_port_map')
                ids.add(port['id'])

    def collect(self):
        hosts = self.client.call('host.get', {
            'output': ['hostid', 'host', 'name', 'status'],
            'selectInterfaces': ['ip', 'dns', 'useip', 'main'],
            'selectInventory': ['location', 'model', 'vendor', 'os'],
            'filter': {'status': '0'}})
        if not hosts:
            return {'devices': [], 'links': [], 'warnings': []}
        keys = set(DEFAULT_ITEMS.values())
        for settings in [self.config, *self.config.get('devices', {}).values()]:
            keys.update(settings.get('item_map', {}).values())
            keys.update(p['state_key'] for p in settings.get('ports', []))
        items = self.client.call('item.get', {
            'output': ['itemid', 'hostid', 'key_', 'lastvalue', 'lastclock', 'status', 'state'],
            'hostids': [str(h['hostid']) for h in hosts], 'filter': {'key_': sorted(keys)}})
        return self.normalize(hosts, items)

    def normalize(self, hosts, items):
        config, devices, warnings = self.config, [], []
        by_host = {}
        for item in items:
            by_host.setdefault(str(item.get('hostid')), {})[item.get('key_')] = item
        max_age = config.get('max_age_seconds', 600)
        for host in hosts:
            if str(host.get('status')) != '0':
                continue
            native = str(host['hostid'])
            override = config.get('devices', {}).get(native, {})
            mapping = {**DEFAULT_ITEMS, **config.get('item_map', {}), **override.get('item_map', {})}
            host_items = by_host.get(native, {})

            def sample(key):
                item = host_items.get(key, {})
                observed = timestamp(item.get('lastclock')) if number(item.get('lastclock')) else None
                valid = str(item.get('status')) == '0' and str(item.get('state')) == '0' and not stale(observed, max_age)
                return item.get('lastvalue') if valid else None, observed

            status, observed = sample(mapping['status'])
            state = {'0': 'down', '1': 'up'}.get(str(status), 'unknown')
            metrics, metric_times = {}, {}
            for metric, key in mapping.items():
                if metric == 'status':
                    continue
                raw, stamp = sample(key)
                value = number(raw)
                if value is not None and (metric.endswith('_percent') and value > 100 or metric == 'clients' and not value.is_integer()):
                    value = None
                if value is not None:
                    if metric == 'latency_ms' and (key == 'icmppingsec' or key.startswith('icmppingsec[')):
                        value *= 1000
                    if number(value) is not None:
                        metrics[metric], metric_times[metric] = value, stamp
            if observed is None and metric_times:
                observed = max(metric_times.values())
            inventory = host.get('inventory') or {}
            interfaces = sorted(host.get('interfaces', []), key=lambda i: i.get('main') != '1')
            interface = interfaces[0] if interfaces else {}
            device = {'id': config['id'] + ':' + native, 'name': override.get('name') or host.get('name') or host.get('host') or native,
                'ip': interface.get('ip' if str(interface.get('useip')) == '1' else 'dns', ''),
                'model': inventory.get('model', ''), 'vendor': inventory.get('vendor', ''), 'os': inventory.get('os', ''),
                'type': override.get('type', 'device'), 'site': override.get('site', config.get('site_map', {}).get(inventory.get('location'), 'unassigned')),
                'state': state, 'observed_at': observed, 'discovered_at': None, 'metrics': metrics, 'metric_observed_at': metric_times,
                'web_url': web_url(override.get('web_url')), 'root': override.get('root') is True, 'ports': []}
            for port in override.get('ports', config.get('ports', [])):
                value, stamp = sample(port['state_key'])
                states = {str(port.get('up_value', '1')): 'up', str(port.get('down_value', '2')): 'down'}
                device['ports'].append({'id': port['id'], 'name': port.get('name', port['id']),
                    'state': states.get(str(value), 'unknown') if value is not None else 'unknown',
                    'admin_state': 'unknown', 'observed_at': stamp, 'required': port.get('required') is True,
                    'neighbors': [], 'rx_bps': None, 'tx_bps': None, 'speed_mbps': None})
            explicit = {**config.get('item_map', {}), **override.get('item_map', {})}
            port_keys = [p['state_key'] for p in override.get('ports', config.get('ports', []))]
            if any(sample(key)[0] is None for key in [*explicit.values(), *port_keys]):
                warnings.append(native + ':mapped_item_unavailable')
            devices.append(device)
        return {'devices': devices, 'links': [], 'warnings': warnings}
