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
            types = ['firewall', 'switch', 'switch', 'server', 'printer', 'wireless', 'device', 'switch', 'switch', 'switch', 'switch', 'server', 'printer', 'printer', 'printer', 'wireless', 'wireless', 'wireless', 'device', 'device', 'device'] if index == 0 else ['firewall', 'switch', 'wireless']
            local = []
            for n, kind in enumerate(types):
                did = 'demo:' + sid + ':' + str(n)
                state = 'down' if index == 0 and n == 6 else 'up'
                d = {'id': did, 'name': f'{kind.upper()}-{index + 1:02d}{n + 1:02d}', 'site': sid, 'type': kind,
                    'ip': f'192.0.2.{index * 50 + n + 1}', 'model': 'Demo ' + kind.title(), 'state': state,
                    'observed_at': stamp, 'root': kind == 'switch' and n == 1, 'metrics': {}, 'ports': []}
                d['vendor'] = {'firewall': 'Fortinet', 'switch': 'Cisco' if n == 1 else 'MikroTik', 'printer': 'HP', 'wireless': 'Ubiquiti', 'server': '', 'device': ''}[kind]
                if kind == 'device':
                    d['category'] = 'Cameras' if n % 2 else 'Production devices'
                d['metrics']['latency_ms'] = round(1.4 + index * 12 + .3 * math.sin(tick + n), 2) if state == 'up' else None
                if kind == 'server':
                    d['metrics'].update(cpu_percent=round(25 + 8 * math.sin(tick / 3), 1), memory_percent=62 + n % 3, disk_percent=48 + n % 3, temperature_celsius=39 + n % 4, power_watts=170 + n * 3, cpu_capacity_mhz=32000, memory_total_bytes=256e9, disk_total_bytes=4e12)
                    d['management_state'] = 'up'
                    d['hardware'] = {'state': 'up', 'processor': 'Demo 16-core processor', 'fan_count': 6, 'fan_state': 'up', 'power_supply_count': 2, 'power_supply_state': 'up', 'drive_count': 8, 'drive_state': 'up'}
                    d['storage'] = [{'name': 'Demo datastore A', 'used_percent': 45 + n % 5, 'capacity_bytes': 2e12}, {'name': 'Demo datastore B', 'used_percent': 65 + n % 3, 'capacity_bytes': 2e12}]
                if kind == 'printer':
                    d['metrics'].update(toner_percent=18 + n % 4 * 20, toner_cyan_percent=64, toner_magenta_percent=78, toner_yellow_percent=51)
                if kind == 'wireless':
                    d['metrics'].update(clients=18 + tick % 4, cpu_percent=8 + tick % 6, memory_percent=32 + n % 4)
                if kind == 'switch':
                    d['metrics']['cpu_percent'] = 3 + n % 5
                if kind in ('switch', 'firewall'):
                    for p in range(1, 25 if kind == 'switch' else 5):
                        status = 'up' if p <= 17 or kind == 'firewall' else 'down'
                        if kind == 'switch' and n == 2 and p == 5:
                            status = 'down' if tick % 12 < 6 else 'up'
                        if index == 0 and n == 7 and p == 16:
                            status = 'down'
                        d['ports'].append({'id': str(p), 'name': f'Gi{p}', 'state': status, 'admin_state': 'up',
                            'speed_mbps': 100 if p in (12, 15) else 1000, 'description': ('WAN uplink' if p == 1 else 'LAN interface') if kind == 'firewall' else 'Workstation' if p > 3 else 'Infrastructure',
                            'required': p <= 3 or (index == 0 and n == 7 and p == 16), 'observed_at': stamp, 'rx_bps': 1e6 * (1 + p / 5) if status == 'up' else 0,
                            'tx_bps': 4e5 if status == 'up' else 0, 'neighbors': []})
                devices.append(d)
                local.append(d)
            pairs = [(0, 1), (1, 2), (1, 7), (1, 8), (2, 9), (2, 10)] if index == 0 else [(0, 1)]
            for parent, child in pairs:
                a, b = local[parent], local[child]
                # Each synthetic branch uses a distinct uplink on the parent.
                a_port, b_port = a['ports'][pairs.index((parent, child)) % len(a['ports'])], b['ports'][3]
                a_port['neighbors'].append({'id': b['id'], 'name': b['name'], 'ip': b['ip'], 'evidence': 'DEMO'})
                b_port['neighbors'].append({'id': a['id'], 'name': a['name'], 'ip': a['ip'], 'evidence': 'DEMO'})
                links.append({'id': 'demo:lan:' + b['id'], 'a': a['id'], 'b': b['id'], 'a_port': a_port['id'], 'b_port': b_port['id'], 'kind': 'lan', 'state': 'up', 'observed_at': stamp, 'evidence': 'DEMO'})
            if index:
                links.append({'id': 'demo:vpn:' + sid, 'a': devices[0]['id'], 'b': local[0]['id'], 'kind': 'vpn',
                    'state': 'attention' if index == 2 else 'up', 'latency_ms': 12 + index * 8,
                    'loss_percent': .8 if index == 2 else 0, 'traffic_bps': (5 + index + math.sin(tick)) * 1e6,
                    'observed_at': stamp, 'evidence': 'DEMO'})
        for i, kind in enumerate(('HTTPS', 'HTTPS', 'TCP', 'DNS', 'PING')):
            state = 'attention' if i == 1 else 'down' if i == 2 and tick % 12 < 6 else 'up'
            metrics = {'latency_ms': round(24 + i * 4 + math.sin(tick), 1)}
            if kind == 'HTTPS':
                metrics.update(http_status_code=200, certificate_days=8 if i == 1 else 85)
            devices.append({'id': f'demo:service:{i}', 'name': f'Demo {kind} check {i + 1}',
                'type': 'service', 'site': sites[0]['id'], 'category': kind, 'model': kind + ' check',
                'ip': 'service.example.com', 'state': state, 'observed_at': stamp, 'metrics': metrics, 'ports': [],
                'services': [{'name': 'TLS certificate expires soon' if i == 1 else 'Connection refused' if state == 'down' else 'Check passed', 'state': state}]})
        for i, health in enumerate(('healthy', 'unhealthy', 'not configured')):
            devices.append({'id': f'demo:container:{i}', 'name': ('demo-web', 'demo-worker', 'demo-cache')[i],
                'type': 'container', 'site': sites[-1]['id'], 'category': 'Demo Docker host', 'model': 'Docker container',
                'state': 'down' if health == 'unhealthy' else 'up', 'observed_at': stamp, 'ports': [],
                'runtime_state': 'running', 'health_state': health,
                'metrics': {'restart_count': i, 'cpu_percent': round(3 + i + math.sin(tick), 1), 'memory_percent': 25 + i * 12}})
        return {'devices': devices, 'links': links}
