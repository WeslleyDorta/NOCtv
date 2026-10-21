"""Translate SMC's operational allowlist to the shared device/link contract."""
import os
from . import smc
from .http import SourceError
from ..model import web_url


class Forcepoint:
    def __init__(self, config):
        self.config = config
        key = os.environ.get(config.get('token_env', 'FORCEPOINT_KEY'))
        url = os.environ.get(config.get('url_env', 'FORCEPOINT_URL'))
        if not key or not url:
            raise SourceError('missing_credentials')
        self.client = smc.Client({**config, 'url': url, 'authenticationkey': key,
            'domain': os.environ.get(config.get('domain_env', 'FORCEPOINT_DOMAIN'), '')}, config.get('ca_file'))

    def collect(self):
        return self.normalize(smc.collect(self.client))

    def normalize(self, raw):
        source, devices, links = self.config['id'], [], []
        for engine in raw['firewalls']:
            override = self.config.get('devices', {}).get(engine['id'], {})
            ports = []
            for i, node in enumerate(engine.get('nodes', [])):
                for interface in node.get('interfaces', []):
                    status = str(interface.get('status', '')).upper()
                    ports.append({'id': str(i) + ':' + str(interface.get('interface_id', interface.get('name'))),
                        'name': interface.get('name') or str(interface.get('interface_id', 'Interface')),
                        'description': node.get('name', ''), 'state': {'UP': 'up', 'DOWN': 'down'}.get(status, 'unknown'),
                        'observed_at': engine['checked_at'], 'neighbors': [], 'required': (interface.get('name') or str(interface.get('interface_id', 'Interface'))) in override.get('required_ports', [])})
            devices.append({'id': source + ':' + engine['id'], 'name': override.get('name', engine['name']), 'type': override.get('type', 'firewall'),
                'vendor': 'Forcepoint', 'brand': override.get('brand'), 'root': override.get('root') is True, 'web_url': web_url(override.get('web_url')),
                'site': override.get('site', engine.get('site') or 'unassigned'), 'state': engine['state'], 'observed_at': engine['checked_at'],
                'ip': next((a['address'] for a in engine.get('addresses', []) if a.get('primary_mgt')), next((a['address'] for a in engine.get('addresses', [])), '')),
                'model': next((n.get('platform') for n in engine.get('nodes', []) if n.get('platform')), 'SMC engine'),
                'ports': ports, 'metrics': {}, 'services': [
                    {'name': h.get('name', ''), 'state': h.get('status', 'unknown')}
                    for n in engine.get('nodes', []) for h in n.get('hardware', [])]})
        ids = {d['id'] for d in devices}
        for connection in raw['connections']:
            a, b = source + ':' + str(connection.get('from_id')), source + ':' + str(connection.get('to_id'))
            if a not in ids or b not in ids:
                continue
            links.append({'id': source + ':' + connection['id'], 'a': a, 'b': b, 'name': connection.get('name', 'VPN'),
                'kind': 'vpn', 'evidence': 'SMC', 'state': connection['state'], 'observed_at': raw['generated_at'],
                **{k: connection[k] for k in ('latency_ms', 'traffic_bps', 'loss_percent') if k in connection}})
        return {'devices': devices, 'links': links, 'warnings': [e['code'] for e in raw.get('errors', [])]}
