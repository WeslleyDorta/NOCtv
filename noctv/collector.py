"""One independent schedule per source; all displays consume a shared snapshot."""
import copy
import threading
import time
from .model import now, stale, validate
from .brands import identify, catalog
from .connectors.demo import Demo
from .connectors.librenms import LibreNMS
from .connectors.forcepoint import Forcepoint
from .connectors.zabbix import Zabbix
from .connectors.firewalls import FortiGate, PANOS, CheckPoint, SophosCentral

ADAPTERS = {'librenms': LibreNMS, 'forcepoint': Forcepoint, 'zabbix': Zabbix, 'fortigate': FortiGate, 'panos': PANOS, 'checkpoint': CheckPoint, 'sophos_central': SophosCentral}


class Collector:
    def __init__(self, config):
        self.config = config
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.threads = []
        self.sources = [{'id': 'demo', 'type': 'demo', 'interval_seconds': 5, 'max_age_seconds': 20}] if config['mode'] == 'demo' else config['connectors']
        self.data = {s['id']: {'state': 'loading', 'devices': [], 'links': [], 'last_success': None} for s in self.sources}

    def poll(self, source):
        start = time.monotonic()
        try:
            adapter = Demo(self.config) if source['type'] == 'demo' else ADAPTERS[source['type']](source)
            batch = adapter.collect()
            validate(batch)
            result = {**batch, 'state': 'partial' if batch.get('warnings') else 'ok', 'last_success': now()}
        except Exception as error:
            # Exception text may contain an upstream response or a credential.
            code = str(error) if str(error) in {'missing_credentials', 'http_401', 'http_403', 'authentication_rejected', 'authentication_failed'} else 'collection_failed'
            with self.lock:
                result = {**self.data[source['id']], 'state': 'error', 'error': code}
        result.update(attempted_at=now(), duration_ms=round((time.monotonic() - start) * 1000))
        with self.lock:
            self.data[source['id']] = result
        return result.get('error') not in ('http_401', 'http_403', 'authentication_rejected', 'authentication_failed')

    def _run(self, source):
        while not self.stop.is_set():
            started = time.monotonic()
            if not self.poll(source):
                return  # Rejected credentials require configuration review and a restart.
            self.stop.wait(max(1, source['interval_seconds'] - (time.monotonic() - started)))

    def start(self):
        for source in self.sources:
            thread = threading.Thread(target=self._run, args=(source,), daemon=True)
            self.threads.append(thread)
            thread.start()

    def snapshot(self):
        with self.lock:
            batches = copy.deepcopy(self.data)
        devices, links, sources, alerts = [], [], [], []
        for source in self.sources:
            batch = batches[source['id']]
            bad = batch['state'] in ('error', 'loading') or stale(batch['last_success'], source['max_age_seconds'])
            sources.append({'id': source['id'], 'type': source['type'], 'state': 'stale' if bad and batch['state'] not in ('error', 'loading') else batch['state'],
                'last_success': batch['last_success'], 'interval_seconds': source['interval_seconds'],
                'duration_ms': batch.get('duration_ms'), 'warnings': batch.get('warnings', []), 'error': batch.get('error')})
            if bad or batch['state'] == 'partial':
                alerts.append({'id': 'source:' + source['id'], 'severity': 'warning', 'text': source['id'] + ': telemetry ' + sources[-1]['state']})
            for d in batch['devices']:
                d['source'] = source['id']
                d['brand'] = d.get('brand') if d.get('brand') in catalog() else identify(d)
                d['stale'] = bad or stale(d.get('observed_at'), source['max_age_seconds'])
                if d['stale']:
                    d['state'] = 'unknown'
                for metric in list(d.get('metrics', {})):
                    observed = d.get('metric_observed_at', {}).get(metric, d.get('observed_at'))
                    if bad or stale(observed, source['max_age_seconds']):
                        d['metrics'].pop(metric)
                if bad:
                    d['management_state'] = 'unknown'
                    for service in d.get('services', []):
                        service['state'] = 'unknown'
                for p in d.get('ports', []):
                    if bad or stale(p.get('observed_at'), source['max_age_seconds']):
                        p['state'] = 'unknown'
                        p['rx_bps'] = p['tx_bps'] = None
                    if p.get('required') and p['state'] == 'down' and d['state'] != 'down':
                        alerts.append({'id': d['id'] + ':port:' + p['id'], 'severity': 'critical', 'text': d['name'] + ' · ' + p['name'] + ' required port DOWN', 'device_id': d['id']})
                if d['state'] == 'down':
                    alerts.append({'id': d['id'], 'severity': 'critical', 'text': d['name'] + ' offline', 'device_id': d['id']})
                devices.append(d)
            by_id = {d['id']: d for d in batch['devices']}
            for link in batch['links']:
                link['source'] = source['id']
                if bad or stale(link.get('observed_at'), link.get('max_age_seconds', source['max_age_seconds'])) or any(by_id[x]['state'] == 'unknown' for x in (link['a'], link['b'])):
                    link['state'] = 'unknown'
                    for metric in ('traffic_bps', 'latency_ms', 'loss_percent'):
                        link[metric] = None
                elif link['kind'] == 'lan':
                    states = [next((p['state'] for p in by_id[link[end]].get('ports', []) if p['id'] == link.get(end + '_port')), 'unknown') for end in ('a', 'b')]
                    link['state'] = 'down' if 'down' in states or any(by_id[x]['state'] == 'down' for x in (link['a'], link['b'])) else 'up' if all(s == 'up' for s in states) else 'unknown'
                if link['state'] in ('down', 'attention'):
                    alerts.append({'id': link['id'], 'severity': 'critical' if link['state'] == 'down' else 'warning', 'text': by_id[link['a']]['name'] + ' ↔ ' + by_id[link['b']]['name'] + ': ' + link['state']})
                links.append(link)
        alerts.sort(key=lambda a: (a['severity'] != 'critical', a['id']))
        return {'schema_version': 1, 'generated_at': now(), 'mode': self.config['mode'], 'devices': devices, 'links': links, 'sources': sources, 'alerts': alerts}
