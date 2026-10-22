import base64
import io
import json
import os
import subprocess
import unittest
from unittest.mock import patch

from noctv.config import load, public
from noctv.diagnostics import Diagnostics, validate_config
from noctv.server import Application


class DiagnosticTests(unittest.TestCase):
    def live(self):
        config = {'mode': 'live', 'diagnostics': {'enabled': True, 'allowed_cidrs': ['192.0.2.0/24', '2001:db8::/32']}}
        validate_config(config)
        return Diagnostics(config)

    def test_defaults_and_invalid_scope(self):
        config = load('config/demo.json')
        self.assertFalse(config['diagnostics']['enabled'])
        self.assertNotIn('diagnostics', public(config))
        for setting in [None, {'enabled': 'yes'}, {'enabled': True}, {'allowed_cidrs': ['bad']}, {'allowed_cidrs': [123]}]:
            with self.assertRaises(ValueError):
                validate_config({'diagnostics': setting})

    @patch('noctv.diagnostics.subprocess.run')
    def test_demo_never_executes_commands(self, run):
        service = Diagnostics(load('config/demo.json'))
        for tool in ['ping', 'trace', 'dns', 'nmap_quick', 'nmap_services']:
            status, result = service.run({'tool': tool, 'target': '192.0.2.10'})
            self.assertEqual(status, 200)
            self.assertTrue(result['simulated'])
        run.assert_not_called()

    @patch('noctv.diagnostics.subprocess.run')
    def test_rejects_injection_ranges_special_addresses_and_unlisted_targets(self, run):
        service = self.live()
        for target in ['192.0.2.10;id', '-oN/tmp/x', 'example.com', '192.0.2.0/24', '127.0.0.1', '169.254.169.254', '224.0.0.1', '::1', '::ffff:192.0.2.10', '0.0.0.0', '198.51.100.1']:
            with self.subTest(target=target):
                self.assertIn(service.run({'tool': 'ping', 'target': target})[0], (400, 403))
        for request in [None, [], {'tool': []}, {'tool': 'shell', 'target': '192.0.2.1'}]:
            self.assertEqual(service.run(request)[0], 400)
        run.assert_not_called()

    @patch('noctv.diagnostics.shutil.which', return_value='/usr/bin/nmap')
    @patch('noctv.diagnostics.subprocess.run')
    def test_fixed_unprivileged_command_no_secrets_and_output_limit(self, run, which):
        run.return_value = subprocess.CompletedProcess([], 1, b'x' * 20000, b'')
        with patch.dict(os.environ, {'LIBRENMS_TOKEN': 'never-forward-this'}):
            status, result = self.live().run({'tool': 'nmap_services', 'target': '2001:db8::10'})
        self.assertEqual(status, 200)
        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(len(result['output']), 16384)
        args, kwargs = run.call_args
        self.assertEqual(args[0][-1], '2001:db8::10')
        self.assertIn('-6', args[0])
        self.assertIn('-sT', args[0])
        self.assertIn('--unprivileged', args[0])
        self.assertFalse(kwargs['shell'])
        self.assertNotIn('LIBRENMS_TOKEN', kwargs['env'])
        self.assertEqual(kwargs['timeout'], 35)

    def test_missing_tool_disabled_busy_and_timeout(self):
        service = self.live()
        with patch('noctv.diagnostics.shutil.which', return_value=None):
            self.assertEqual(service.run({'tool': 'ping', 'target': '192.0.2.10'})[0], 503)
            self.assertFalse(service.status()['tools'][0]['available'])
        with patch('noctv.diagnostics.shutil.which', return_value='/usr/bin/ping'), patch('noctv.diagnostics.subprocess.run', side_effect=subprocess.TimeoutExpired('ping', 35)):
            service.lock.acquire()
            self.assertEqual(service.run({'tool': 'ping', 'target': '192.0.2.10'})[0], 429)
            service.lock.release()
            self.assertEqual(service.run({'tool': 'ping', 'target': '192.0.2.10'})[0], 504)
            self.assertFalse(service.lock.locked())
            self.assertEqual(service.run({'tool': 'ping', 'target': '192.0.2.10'})[0], 429)
        service.enabled = False
        self.assertEqual(service.run({'tool': 'ping', 'target': '192.0.2.10'})[0], 403)

    def call(self, app, method='POST', headers=None, body=None):
        payload = json.dumps(body or {'tool': 'ping', 'target': '192.0.2.10'}).encode()
        env = {'PATH_INFO': '/api/v1/diagnostics/run', 'REQUEST_METHOD': method,
               'CONTENT_TYPE': 'application/json', 'HTTP_X_NOCTV_REQUEST': 'diagnostic',
               'CONTENT_LENGTH': str(len(payload)), 'wsgi.input': io.BytesIO(payload), **(headers or {})}
        response = {}
        def start(status, hdrs):
            response.update(status=status, headers=dict(hdrs))
        response['body'] = b''.join(app(env, start))
        return response

    def test_http_auth_csrf_and_body_boundaries(self):
        demo = Application('config/demo.json', start=False)
        self.assertTrue(self.call(demo)['status'].startswith('200'))
        for headers in [{'HTTP_X_NOCTV_REQUEST': ''}, {'CONTENT_TYPE': 'text/plain'}]:
            self.assertTrue(self.call(demo, headers=headers)['status'].startswith('403'))
        for length in ['2048', '-1', 'invalid']:
            self.assertTrue(self.call(demo, headers={'CONTENT_LENGTH': length})['status'].startswith('400'))
        with patch.dict(os.environ, {'NOCTV_USER': 'viewer', 'NOCTV_PASSWORD': 'unit-test-passphrase-1234'}):
            live = Application('config/live.example.json', start=False)
        self.assertTrue(self.call(live)['status'].startswith('401'))
        auth = 'Basic ' + base64.b64encode(b'viewer:unit-test-passphrase-1234').decode()
        self.assertTrue(self.call(live, headers={'HTTP_AUTHORIZATION': auth})['status'].startswith('403'))
        self.assertTrue(self.call(demo, method='GET')['status'].startswith('404'))
