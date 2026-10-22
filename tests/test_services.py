import copy
import json
import os
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from noctv.config import load, public
from noctv.collector import Collector
from noctv.connectors.probes import Probes, validate_probes
from noctv.connectors.docker import Docker, validate_docker
from noctv.connectors.http import SourceError
from noctv.model import validate


class Handler(BaseHTTPRequestHandler):
    paths = []
    def do_GET(self):
        self.paths.append(self.path)
        code = 302 if self.path.startswith('/redirect') else 503 if self.path.startswith('/failure') else 200
        self.send_response(code)
        if code == 302:
            self.send_header('Location', '/never-follow')
        self.end_headers()
        self.wfile.write(b'healthy synthetic response')
    def log_message(self, *args):
        pass


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def check(self, check, path='/ok?secret=private-query'):
        with patch.dict(os.environ, {'TEST_PROBE_URL': f'http://127.0.0.1:{self.server.server_port}{path}'}):
            batch = Probes({'id': 'checks', 'checks': [{'id': 'test', **check}]}).collect()
        validate(batch)
        self.assertNotIn('private-query', json.dumps(batch))
        self.assertNotIn('healthy synthetic response', json.dumps(batch))
        return batch['devices'][0]

    def test_http_status_keyword_and_no_redirect(self):
        base = {'kind': 'http', 'url_env': 'TEST_PROBE_URL'}
        self.assertEqual(self.check({**base, 'keyword': 'healthy'})['state'], 'up')
        self.assertEqual(self.check({**base, 'keyword': 'absent'})['state'], 'down')
        self.assertEqual(self.check(base, '/failure')['metrics']['http_status_code'], 503)
        self.assertEqual(self.check(base, '/failure')['state'], 'down')
        self.assertEqual(self.check({**base, 'expected_status': [503]}, '/failure')['state'], 'up')
        Handler.paths.clear()
        self.assertEqual(self.check(base, '/redirect')['state'], 'down')
        self.assertEqual(Handler.paths, ['/redirect'])

    def test_tcp_and_missing_environment(self):
        self.assertEqual(self.check({'kind': 'tcp', 'host': '127.0.0.1', 'port': self.server.server_port})['state'], 'up')
        with patch('noctv.connectors.probes.socket.create_connection', side_effect=ConnectionRefusedError):
            self.assertEqual(self.check({'kind': 'tcp', 'host': '127.0.0.1', 'port': 9})['state'], 'down')
        self.assertEqual(self.check({'kind': 'http', 'url_env': 'NOCTV_MISSING_TEST_URL'})['state'], 'unknown')

    def test_dns_ping_fixed_commands_and_missing_dependencies(self):
        check = {'kind': 'dns', 'host': 'example.com', 'expected_value': '192.0.2.1'}
        with patch('noctv.connectors.probes.shutil.which', return_value='/usr/bin/dig'), patch('noctv.connectors.probes.subprocess.run') as run:
            run.return_value = SimpleNamespace(returncode=0, stdout=b';; status: NOERROR\nexample.com. 30 IN A 192.0.2.1\n')
            self.assertEqual(self.check(check)['state'], 'up')
            self.assertEqual(run.call_args.args[0][-1], 'example.com')
            self.assertFalse(run.call_args.kwargs['shell'])
            self.assertEqual(set(run.call_args.kwargs['env']), {'PATH', 'LANG'})
            self.assertEqual(self.check({**check, 'expected_value': '192.0.2.2'})['state'], 'down')
            run.return_value = SimpleNamespace(returncode=1, stdout=b'')
            self.assertEqual(self.check({'kind': 'ping', 'host': '192.0.2.1'})['state'], 'down')
            run.return_value.returncode = 2
            self.assertEqual(self.check({'kind': 'ping', 'host': '192.0.2.1'})['state'], 'unknown')
        with patch('noctv.connectors.probes.shutil.which', return_value=None):
            self.assertEqual(self.check(check)['state'], 'unknown')

    def test_https_verified_certificate_and_expiry(self):
        import time
        response = MagicMock(); response.__enter__.return_value = response; response.code = 200
        tls = MagicMock(); tls.__enter__.return_value = tls
        tls.getpeercert.return_value = {'notAfter': time.strftime('%b %d %H:%M:%S %Y GMT', time.gmtime(time.time()+8*86400))}
        context = MagicMock(); context.wrap_socket.return_value = tls
        with patch.dict(os.environ, {'TEST_TLS_URL': 'https://example.com/health'}), patch('noctv.connectors.probes.ssl.create_default_context', return_value=context) as verify, patch('noctv.connectors.probes.socket.create_connection'), patch('noctv.connectors.probes.urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = response
            d = Probes({'id': 'p', 'checks': [{'id': 'tls', 'kind': 'http', 'url_env': 'TEST_TLS_URL'}]}).collect()['devices'][0]
            self.assertEqual(d['state'], 'attention'); self.assertLessEqual(d['metrics']['certificate_days'], 8)
            verify.assert_called_once_with(cafile=None)
            self.assertEqual(context.wrap_socket.call_args.kwargs['server_hostname'], 'example.com')

    def test_config_rejects_invalid_and_public_hides_targets(self):
        base = {'id': 'checks', 'type': 'probes', 'checks': [{'id': 'dns', 'kind': 'dns', 'host': 'example.com'}]}
        for edit in [{'host': '-f'}, {'host': 'x;touch bad'}, {'kind': 'shell'}, {'timeout_seconds': 0}, {'dns_server': 'not-an-ip'}, {'record_type': 'AXFR'}]:
            bad = copy.deepcopy(base); bad['checks'][0].update(edit)
            with self.assertRaises((SourceError, ValueError)):
                validate_probes(bad)
        c = load('config/demo.json'); c.update(mode='live', connectors=[base])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'config.json'; path.write_text(json.dumps(c)); checked = load(path)
        self.assertNotIn('example.com', json.dumps(public(checked)))
        self.assertIn('services', checked['display']['views']); self.assertIn('containers', checked['display']['views'])


class DockerTests(unittest.TestCase):
    def setUp(self):
        self.source = {'id': 'docker', 'type': 'docker', 'url_env': 'TEST_DOCKER_URL', 'collect_stats': True}
        self.rows = [{'Id': 'a'*64, 'Names': ['/web']}]
        self.detail = {'State': {'Status': 'running', 'Health': {'Status': 'healthy'}}, 'RestartCount': 3,
                       'Config': {'Env': ['TOP_SECRET=do-not-expose']}, 'Mounts': [{'Source': '/private/path'}]}
        self.stats = {'memory_stats': {'usage': 25, 'limit': 100}, 'cpu_stats': {'cpu_usage': {'total_usage': 20}, 'system_cpu_usage': 100}, 'precpu_stats': {'cpu_usage': {'total_usage': 10}, 'system_cpu_usage': 50}}
        self.calls = []
    def get(self, path):
        self.calls.append(path)
        if path.endswith('json?all=true'): return self.rows
        if '/stats?' in path: return self.stats
        return self.detail
    def batch(self, **options):
        with patch.dict(os.environ, {'TEST_DOCKER_URL': 'https://docker.example.com'}), patch('noctv.connectors.docker.JSONClient') as client:
            client.return_value.get.side_effect = self.get
            batch = Docker({**self.source, **options}).collect()
        validate(batch)
        for secret in ['TOP_SECRET', 'do-not-expose', '/private/path']:
            self.assertNotIn(secret, json.dumps(batch))
        return batch
    def test_inventory_runtime_health_resources_and_fixed_reads(self):
        d = self.batch()['devices'][0]
        self.assertEqual(d['state'], 'up'); self.assertEqual(d['metrics'], {'restart_count': 3, 'memory_percent': 25, 'cpu_percent': 20})
        self.assertEqual(self.calls, ['v1.45/containers/json?all=true', 'v1.45/containers/'+'a'*64+'/json', 'v1.45/containers/'+'a'*64+'/stats?stream=false&one-shot=true'])
        self.detail['State']['Health']['Status'] = 'unhealthy'
        self.assertEqual(self.batch()['devices'][0]['state'], 'down')
        del self.detail['State']['Health']
        self.assertEqual(self.batch()['devices'][0]['health_state'], 'not configured')
        self.detail['State']['Status'] = 'restarting'
        self.assertEqual(self.batch()['devices'][0]['state'], 'attention')
    def test_dynamic_inventory_missing_and_inspect_failures(self):
        self.rows.append({'Id': 'b'*64, 'Names': ['/worker']})
        self.assertEqual(len(self.batch()['devices']), 2)
        d = self.batch(container_names=['absent'])['devices'][0]
        self.assertEqual(d['state'], 'down'); self.assertEqual(d['runtime_state'], 'missing')
        self.detail = None
        self.assertTrue(all(d['state'] == 'unknown' for d in self.batch()['devices']))
        self.assertIn('container_data_unavailable', self.batch()['warnings'])
    def test_boundaries_and_https_required(self):
        for edit in [{'api_version': '../delete'}, {'max_containers': 0}, {'collect_stats': 'yes'}, {'container_names': ['x', 'x']}, {'container_names': ['../x']}]:
            with self.assertRaises(SourceError): validate_docker(edit)
        with patch.dict(os.environ, {'TEST_DOCKER_URL': 'http://docker.example.com'}):
            with self.assertRaises(SourceError): Docker(self.source)
        self.rows[0]['Id'] = '../escape'
        with self.assertRaises(SourceError): self.batch()
    def test_failure_clears_container_health_and_preserves_alerts_independent_of_views(self):
        c = load('config/demo.json'); c['display']['views'] = ['connections']
        collector = Collector(c); collector.poll(collector.sources[0])
        snapshot = collector.snapshot()
        self.assertTrue(any(a.get('device_id') == 'demo:container:1' for a in snapshot['alerts']))
        collector.data['demo']['state'] = 'error'
        stale = collector.snapshot()
        for d in stale['devices']:
            if d['type'] == 'container':
                self.assertEqual(d['state'], 'unknown'); self.assertEqual(d['health_state'], 'unknown'); self.assertEqual(d['metrics'], {})

if __name__ == '__main__':
    unittest.main()
