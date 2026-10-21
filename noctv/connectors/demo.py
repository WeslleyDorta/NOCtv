"""Synthetic, deterministic telemetry. Documentation IPs; no external calls."""
import math
import time
from ..model import now


class Demo:
    def __init__(self, config):
        self.config = config

    def collect(self):
        stamp, tick = now(), int(time.time() / 5)
        sites = self.config['sites'] or [{'id': 'unassigned'}]
        devices, links = [], []
        for index, site in enumerate(sites):
            sid = site['id']
            types = ['firewall', 'switch', 'switch', 'server', 'printer', 'wireless', 'device'] if index == 0 else ['firewall', 'switch', 'wireless']
            local = []
            for n, kind in enumerate(types):
                did = 'demo:' + sid + ':' + str(n)
                state = 'down' if index == 0 and kind == 'device' else 'up'
                d = {'id': did, 'name': f'{kind.upper()}-{index + 1:02d}{n + 1:02d}', 'site': sid, 'type': kind,
                    'ip': f'192.0.2.{index * 20 + n + 1}', 'model': 'Demo ' + kind.title(), 'state': state,
                    'observed_at': stamp, 'root': kind == 'switch' and n == 1, 'metrics': {}, 'ports': []}
                d['vendor'] = {'firewall': 'Fortinet', 'switch': 'Cisco' if n == 1 else 'MikroTik', 'printer': 'HP', 'wireless': 'Ubiquiti', 'server': '', 'device': ''}[kind]
                d['metrics']['latency_ms'] = round(1.4 + index * 12 + .3 * math.sin(tick + n), 2) if state == 'up' else None
                if kind == 'server':
                    d['metrics'].update(cpu_percent=round(25 + 8 * math.sin(tick / 3), 1), memory_percent=62, disk_percent=48)
                if kind == 'printer':
                    d['metrics'].update(toner_percent=18)
                if kind == 'wireless':
                    d['metrics'].update(clients=18 + tick % 4)
                if kind in ('switch', 'firewall'):
                    for p in range(1, 25 if kind == 'switch' else 5):
                        status = 'up' if p <= 17 or kind == 'firewall' else 'down'
                        if kind == 'switch' and n == 2 and p == 5:
                            status = 'down' if tick % 12 < 6 else 'up'
                        d['ports'].append({'id': str(p), 'name': f'Gi{p}', 'state': status, 'admin_state': 'up',
                            'speed_mbps': 1000, 'description': 'Workstation' if p > 3 else 'Infrastructure',
                            'required': p <= 3, 'observed_at': stamp, 'rx_bps': 1e6 * (1 + p / 5) if status == 'up' else 0,
                            'tx_bps': 4e5 if status == 'up' else 0, 'neighbors': []})
                devices.append(d)
                local.append(d)
            for a, b in zip(local, local[1:]):
                if b['type'] in ('switch', 'firewall'):
                    a_port = a['ports'][0] if a['ports'] else None
                    b_port = b['ports'][1] if b['ports'] else None
                    if a_port:
                        a_port['neighbors'].append({'id': b['id'], 'name': b['name'], 'ip': b['ip'], 'evidence': 'DEMO'})
                    if b_port:
                        b_port['neighbors'].append({'id': a['id'], 'name': a['name'], 'ip': a['ip'], 'evidence': 'DEMO'})
                    links.append({'id': 'demo:lan:' + b['id'], 'a': a['id'], 'b': b['id'], 'a_port': '1', 'b_port': '2', 'kind': 'lan', 'state': 'up', 'observed_at': stamp, 'evidence': 'DEMO'})
            if index:
                links.append({'id': 'demo:vpn:' + sid, 'a': devices[0]['id'], 'b': local[0]['id'], 'kind': 'vpn',
                    'state': 'attention' if index == 2 else 'up', 'latency_ms': 12 + index * 8,
                    'loss_percent': .8 if index == 2 else 0, 'traffic_bps': (5 + index + math.sin(tick)) * 1e6,
                    'observed_at': stamp, 'evidence': 'DEMO'})
        return {'devices': devices, 'links': links}
