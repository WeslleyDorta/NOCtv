"""Read-only instant selectors with paired upstream sample timestamps."""
import os
import re
import time
from urllib.parse import urlencode

from .http import JSONClient, SourceError
from ..model import number, stale, timestamp, web_url

METRICS = {'latency_ms', 'uptime_seconds', 'cpu_percent', 'memory_percent', 'disk_percent', 'toner_percent', 'clients'}
LABEL = r'[a-zA-Z_][a-zA-Z0-9_]*'
MATCHER = LABEL + r'\s*(?:=~|!~|!=|=)\s*"(?:[^"\\\r\n]|\\[^\r\n])*"'
SELECTOR = re.compile(r'([a-zA-Z_:][a-zA-Z0-9_:]*)\s*(?:\{\s*(?:' + MATCHER + r'(?:\s*,\s*' + MATCHER + r')*\s*,?)?\s*\})?')


def selector(value):
    match = SELECTOR.fullmatch(value) if isinstance(value, str) and len(value) <= 4096 else None
    if not match:
        raise SourceError('invalid_selector')
    return match.group(1)


class Prometheus:
    def __init__(self, config):
        self.config = config
        if selector(config.get('status_query')) == 'up':
            raise SourceError('scrape_health_is_not_device_status')
        self.identity = config.get('identity_label', 'instance')
        if not isinstance(self.identity, str) or not re.fullmatch(LABEL, self.identity) or self.identity == '__name__':
            raise SourceError('invalid_identity_label')
        self.limit = config.get('max_series', 1000)
        if type(self.limit) is not int or not 1 <= self.limit <= 10000:
            raise SourceError('invalid_series_limit')
        self.max_age = number(config.get('max_age_seconds', 600))
        if not self.max_age:
            raise SourceError('invalid_max_age')
        self.metrics = config.get('metric_queries', {})
        if not isinstance(self.metrics, dict) or any(k not in METRICS for k in self.metrics):
            raise SourceError('invalid_metric_queries')
        for settings in self.metrics.values():
            if not isinstance(settings, dict) or not number(settings.get('scale', 1)):
                raise SourceError('invalid_metric_queries')
            selector(settings.get('query'))
        self.overrides = config.get('devices', {})
        if not isinstance(self.overrides, dict) or len(self.overrides) > self.limit or any(not isinstance(k, str) or not k or not isinstance(v, dict) for k, v in self.overrides.items()):
            raise SourceError('invalid_device_map')
        if any(v.get('type', 'device') not in {'switch', 'router', 'firewall', 'server', 'printer', 'wireless', 'device'} for v in self.overrides.values()):
            raise SourceError('invalid_device_type')
        if not isinstance(config.get('site_map', {}), dict) or ('site_label' in config and (not isinstance(config['site_label'], str) or not re.fullmatch(LABEL, config['site_label']))):
            raise SourceError('invalid_site_map')
        url = os.environ.get(config.get('url_env', 'PROMETHEUS_URL'))
        token = os.environ.get(config['token_env']) if config.get('token_env') else None
        if not url or (config.get('token_env') and not token):
            raise SourceError('missing_credentials')
        if token and any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise SourceError('invalid_credentials')
        self.client = JSONClient(url, {'Authorization': 'Bearer ' + token} if token else {}, config.get('ca_file'))

    def query(self, query, evaluation):
        payload = self.client.get('api/v1/query?' + urlencode({'query': query, 'time': evaluation, 'timeout': '8s', 'limit': self.limit + 1}))
        if not isinstance(payload, dict) or payload.get('status') != 'success':
            raise SourceError('prometheus_query_failed')
        data = payload.get('data')
        if not isinstance(data, dict) or data.get('resultType') != 'vector' or not isinstance(data.get('result'), list):
            raise SourceError('invalid_prometheus_response')
        if len(data['result']) > self.limit:
            raise SourceError('series_limit_exceeded')
        if payload.get('warnings'):
            raise SourceError('prometheus_query_incomplete')
        return data['result']

    def samples(self, query, evaluation, warnings):
        values = self.query(query, evaluation)
        clocks = self.query('timestamp(' + query + ')', evaluation)

        def index(rows):
            indexed = {}
            for row in rows:
                labels = row.get('metric') if isinstance(row, dict) else None
                if not isinstance(labels, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in labels.items()) or not labels.get(self.identity):
                    warnings.add('malformed_series')
                    continue
                native = labels[self.identity]
                indexed.setdefault(native, []).append(row)
            return indexed

        values, clocks = index(values), index(clocks)
        samples = {}
        for native in values.keys() | clocks.keys():
            rows, times = values.get(native, []), clocks.get(native, [])
            labels, value, observed = {}, None, None
            if len(rows) == len(times) == 1:
                labels = {k: v for k, v in rows[0]['metric'].items() if k != '__name__'}
                time_labels = {k: v for k, v in times[0]['metric'].items() if k != '__name__'}
                sample, clock = rows[0].get('value'), times[0].get('value')
                if labels == time_labels and isinstance(sample, list) and len(sample) == 2 and isinstance(clock, list) and len(clock) == 2:
                    seconds = number(clock[1])
                    observed = timestamp(seconds) if seconds else None
                    if not stale(observed, self.max_age):
                        value = number(sample[1])
            if value is None:
                warnings.add('mapped_sample_unavailable')
            samples[native] = (labels, value, observed)
        return samples

    def collect(self):
        evaluation, warnings = time.time(), set()
        status = self.samples(self.config['status_query'], evaluation, warnings)
        metrics = {key: self.samples(settings['query'], evaluation, warnings) for key, settings in self.metrics.items()}
        identities = set(self.overrides) | set(status)
        for samples in metrics.values():
            identities.update(samples)
        if len(identities) > self.limit:
            raise SourceError('series_limit_exceeded')
        devices = []
        for native in sorted(identities):
            override = self.overrides.get(native, {})
            labels, value, observed = status.get(native, ({}, None, None))
            state = {0: 'down', 1: 'up'}.get(value, 'unknown')
            if state == 'unknown':
                warnings.add('mapped_sample_unavailable')
            device_metrics, metric_times = {}, {}
            for key, samples in metrics.items():
                _, raw, stamp = samples.get(native, ({}, None, None))
                converted = number(raw * float(self.metrics[key].get('scale', 1))) if raw is not None else None
                if converted is not None and ((key.endswith('_percent') and converted > 100) or (key == 'clients' and not converted.is_integer())):
                    converted = None
                if converted is None:
                    warnings.add('mapped_sample_unavailable')
                else:
                    device_metrics[key], metric_times[key] = converted, stamp
            devices.append({'id': self.config['id'] + ':' + native, 'name': override.get('name') or native,
                'type': override.get('type', 'device'), 'site': override.get('site', self.config.get('site_map', {}).get(labels.get(self.config.get('site_label')), 'unassigned')),
                'state': state, 'observed_at': observed, 'metrics': device_metrics, 'metric_observed_at': metric_times,
                'ip': override.get('ip', ''), 'model': override.get('model', ''), 'vendor': override.get('vendor', ''),
                'os': override.get('os', ''), 'web_url': web_url(override.get('web_url')), 'root': override.get('root') is True, 'ports': []})
        return {'devices': devices, 'links': [], 'warnings': sorted(warnings)}
