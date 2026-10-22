"""Docker Engine inventory and health through an HTTPS read-only endpoint."""
from concurrent.futures import ThreadPoolExecutor
import os
import re
from .http import JSONClient, SourceError
from ..model import now, number, web_url


def validate_docker(config):
    if not re.fullmatch(r'1\.\d{2,3}', str(config.get('api_version', '1.45'))):
        raise SourceError('invalid_docker_api_version')
    if type(config.get('max_containers', 50)) is not int or not 1 <= config.get('max_containers', 50) <= 200:
        raise SourceError('invalid_container_limit')
    if type(config.get('collect_stats', False)) is not bool:
        raise SourceError('invalid_docker_stats_setting')
    names = config.get('container_names', [])
    if not isinstance(names, list) or any(not isinstance(n, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', n) for n in names) or len(names) != len(set(names)):
        raise SourceError('invalid_container_names')


class Docker:
    def __init__(self, config):
        validate_docker(config)
        self.config = config
        base = os.environ.get(config.get('url_env', 'DOCKER_API_URL'), '')
        token = os.environ.get(config['token_env'], '') if config.get('token_env') else None
        if not base or (config.get('token_env') and not token):
            raise SourceError('missing_credentials')
        if token and any(ord(c) < 33 or ord(c) > 126 for c in token):
            raise SourceError('invalid_credentials')
        self.client = JSONClient(base, {'Authorization': 'Bearer ' + token} if token else {}, config.get('ca_file'),
                                 client_cert=config.get('client_cert_file'), client_key=config.get('client_key_file'))
        self.prefix = 'v' + config.get('api_version', '1.45') + '/containers/'

    def container(self, item):
        native, name = item['Id'], item['Names'][0].lstrip('/')
        override = self.config.get('devices', {}).get(name, {})
        device = {'id': self.config['id'] + ':' + name, 'name': override.get('name', name), 'type': 'container',
                  'site': override.get('site', self.config.get('site', 'unassigned')), 'category': self.config.get('name', self.config['id']),
                  'model': 'Docker container', 'state': 'unknown', 'observed_at': None, 'metrics': {}, 'ports': [],
                  'web_url': web_url(override.get('web_url')), 'ip': '', 'services': [], 'runtime_state': 'unknown', 'health_state': 'unknown'}
        try:
            detail = self.client.get(self.prefix + native + '/json')
            status = detail.get('State', {})
            runtime = status.get('Status', 'unknown')
            health = status.get('Health', {}).get('Status', 'not configured')
            state = {'running': 'up', 'restarting': 'attention', 'created': 'down', 'exited': 'down', 'dead': 'down', 'paused': 'down'}.get(runtime, 'unknown')
            if runtime == 'running' and health != 'not configured':
                state = {'healthy': 'up', 'unhealthy': 'down', 'starting': 'attention'}.get(health, 'unknown')
            device.update(state=state, runtime_state=runtime if runtime in ('running', 'restarting', 'created', 'exited', 'dead', 'paused') else 'unknown',
                          health_state=health if health in ('healthy', 'unhealthy', 'starting', 'not configured') else 'unknown', observed_at=now())
            restart = number(detail.get('RestartCount'))
            if restart is not None:
                device['metrics']['restart_count'] = restart
            if self.config.get('collect_stats') and runtime == 'running':
                try:
                    stats = self.client.get(self.prefix + native + '/stats?stream=false&one-shot=true')
                    memory = stats.get('memory_stats', {})
                    used, limit = number(memory.get('usage')), number(memory.get('limit'))
                    if used is not None and limit:
                        device['metrics']['memory_percent'] = min(100, used / limit * 100)
                    cpu, previous = stats.get('cpu_stats', {}), stats.get('precpu_stats', {})
                    total, prior = number(cpu.get('cpu_usage', {}).get('total_usage')), number(previous.get('cpu_usage', {}).get('total_usage'))
                    system, old_system = number(cpu.get('system_cpu_usage')), number(previous.get('system_cpu_usage'))
                    if None not in (total, prior, system, old_system) and total >= prior and system > old_system:
                        device['metrics']['cpu_percent'] = min(100, (total - prior) / (system - old_system) * 100)
                except (SourceError, TypeError, AttributeError):
                    device['services'].append({'name': 'Resource measurements unavailable', 'state': 'unknown'})
        except (SourceError, TypeError, AttributeError):
            device['services'].append({'name': 'Container inspection unavailable', 'state': 'unknown'})
        return device

    def collect(self):
        rows = self.client.get(self.prefix + 'json?all=true')
        if not isinstance(rows, list) or any(not isinstance(r, dict) or not re.fullmatch(r'[a-f0-9]{64}', str(r.get('Id', ''))) or not isinstance(r.get('Names'), list) or not r['Names'] or not isinstance(r['Names'][0], str) or not re.fullmatch(r'/?[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', r['Names'][0]) for r in rows):
            raise SourceError('invalid_container_inventory')
        names = self.config.get('container_names', [])
        selected = [r for r in rows if not names or r['Names'][0].lstrip('/') in names]
        if len(selected) > self.config.get('max_containers', 50) or len(names) > self.config.get('max_containers', 50):
            raise SourceError('container_limit_exceeded')
        with ThreadPoolExecutor(max_workers=4) as executor:
            devices = list(executor.map(self.container, selected))
        present = {r['Names'][0].lstrip('/') for r in selected}
        for name in set(names) - present:
            override = self.config.get('devices', {}).get(name, {})
            devices.append({'id': self.config['id'] + ':' + name, 'name': override.get('name', name), 'type': 'container',
                            'site': override.get('site', self.config.get('site', 'unassigned')), 'category': self.config.get('name', self.config['id']),
                            'model': 'Docker container', 'state': 'down', 'observed_at': now(), 'metrics': {}, 'ports': [],
                            'runtime_state': 'missing', 'health_state': 'unknown', 'services': [{'name': 'Expected container not found', 'state': 'down'}]})
        return {'devices': devices, 'links': [], 'warnings': ['container_data_unavailable'] if any(d['state'] == 'unknown' or any(s['state'] == 'unknown' for s in d.get('services', [])) for d in devices) else []}
