import base64
import copy
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from noctv.config import load, public
from noctv.model import now, stale, number, web_url, validate
from noctv.collector import Collector
from noctv.server import Application
from noctv.connectors.librenms import LibreNMS
from noctv.connectors.http import JSONClient, SourceError
from noctv.connectors.smc import state as smc_state


class ConfigurationTests(unittest.TestCase):
    def test_defaults_and_public_allowlist(self):
        c = load('config/demo.json')
        c['connectors'] = [{'token': 'never-expose-this'}]
        c['display']['secret'] = 'hidden'
        c['sites'][0]['secret'] = 'hidden'
        blob = json.dumps(public(c))
        self.assertNotIn('hidden', blob)
        self.assertNotIn('token', blob)
        self.assertEqual(c['display']['views'][0], 'connections')

    def test_invalid_settings_fail_before_network(self):
        for mutate in [lambda c: c.update(mode='oops'), lambda c: c['sites'].append(c['sites'][0]), lambda c: c['sites'][0].update(x=500), lambda c: c.update(mode='live'), lambda c: c.update(display={'refresh_seconds': 0})]:
            c = load('config/demo.json')
            mutate(c)
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / 'config.json'
                p.write_text(json.dumps(c))
                with self.assertRaises((ValueError, KeyError)):
                    load(p)

    def test_numeric_and_url_boundaries(self):
        for bad in [None, True, 'NaN', float('inf'), -1]:
            self.assertIsNone(number(bad))
        for url in ['javascript:alert(1)', 'https://user:pass@example.com', '//example.com', 'https://example.com/\nx']:
            self.assertIsNone(web_url(url))
        self.assertEqual(web_url('https://switch.example.com'), 'https://switch.example.com')
        self.assertTrue(stale(None, 60))
        self.assertTrue(stale((datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(), 60))
        self.assertFalse(stale(now(), 60))


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.collector = Collector(load('config/demo.json'))
        self.collector.poll(self.collector.sources[0])

    def test_demo_contract_and_required_port_policy(self):
        snapshot = self.collector.snapshot()
        validate(snapshot)
        self.assertEqual(len(snapshot['devices']), 16)
        self.assertGreater(len(snapshot['links']), 0)
        self.assertTrue(any(a['severity'] == 'critical' for a in snapshot['alerts']))
        self.assertFalse(any('port DOWN' in a['text'] for a in snapshot['alerts']))
        d = self.collector.data['demo']['devices'][1]
        d['ports'][0]['state'] = 'down'
        self.assertTrue(any('required port DOWN' in a['text'] for a in self.collector.snapshot()['alerts']))

    def test_stale_source_never_keeps_green_states_or_rates(self):
        self.collector.data['demo']['last_success'] = '2000-01-01T00:00:00+00:00'
        snapshot = self.collector.snapshot()
        self.assertTrue(all(d['state'] == 'unknown' and d['metrics'] == {} for d in snapshot['devices']))
        self.assertTrue(all(p['state'] == 'unknown' and p['rx_bps'] is None for d in snapshot['devices'] for p in d['ports']))
        self.assertTrue(all(l['state'] == 'unknown' for l in snapshot['links']))
        self.assertFalse(any(a['severity'] == 'critical' for a in snapshot['alerts']))

    def test_fresh_metric_without_reachability_is_preserved(self):
        d = self.collector.data['demo']['devices'][0]
        d.update(observed_at=None, state='unknown', metrics={'cpu_percent': 20}, metric_observed_at={'cpu_percent': now()})
        result = self.collector.snapshot()['devices'][0]
        self.assertEqual(result['state'], 'unknown')
        self.assertEqual(result['metrics']['cpu_percent'], 20)
        self.assertEqual(result['ports'][0]['state'], 'up')

    def test_failed_collection_retains_inventory_as_unknown_without_exception_text(self):
        with patch('noctv.collector.Demo.collect', side_effect=RuntimeError('secret upstream response')):
            self.collector.poll(self.collector.sources[0])
        snapshot = self.collector.snapshot()
        self.assertEqual(len(snapshot['devices']), 16)
        self.assertTrue(all(d['state'] == 'unknown' for d in snapshot['devices']))
        self.assertNotIn('secret upstream', json.dumps(snapshot))

    def test_auth_rejection_stops_retries(self):
        for code in ('http_401', 'http_403', 'authentication_rejected', 'authentication_failed'):
            with self.subTest(code=code), patch('noctv.collector.Demo.collect', side_effect=SourceError(code)):
                self.assertFalse(self.collector.poll(self.collector.sources[0]))
                self.assertEqual(self.collector.data['demo']['error'], code)

    def test_lan_state_ages_with_ports_not_only_discovery(self):
        batch = self.collector.data['demo']
        lan = next(l for l in batch['links'] if l['kind'] == 'lan')
        for d in batch['devices']:
            if d['id'] in (lan['a'], lan['b']):
                for p in d['ports']:
                    p['observed_at'] = '2000-01-01T00:00:00+00:00'
        current = next(l for l in self.collector.snapshot()['links'] if l['id'] == lan['id'])
        self.assertEqual(current['state'], 'unknown')

    def test_duplicate_contract_is_rejected(self):
        s = self.collector.snapshot()
        s['devices'].append(s['devices'][0])
        with self.assertRaises(ValueError):
            validate(s)


class LibreNMSTests(unittest.TestCase):
    def setUp(self):
        self.adapter = LibreNMS.__new__(LibreNMS)
        self.adapter.config = {'id': 'nms', 'site_map': {'Campus': 'hq'}, 'devices': {'1': {'required_ports': ['Gi1']}}}
        self.rows = [{'device_id': '1', 'hostname': 'switch.example.com', 'sysName': 'Core', 'type': 'network', 'status': 1, 'last_polled': now(), 'last_discovered': now(), 'location': 'Campus', 'hardware': 'C9300'}, {'device_id': '2', 'hostname': 'edge.example.com', 'type': 'network', 'status': 1, 'last_polled': now(), 'last_discovered': now(), 'location': 'Campus'}]
        self.ports = [{'device_id': '1', 'port_id': '11', 'ifName': 'Gi1', 'ifOperStatus': 'up', 'ifAdminStatus': 'up', 'ifSpeed': 1000000000, 'ifInOctets_rate': 10, 'poll_time': int(datetime.now(timezone.utc).timestamp())}, {'device_id': '2', 'port_id': '21', 'ifName': 'Gi1', 'ifOperStatus': 'down', 'ifAdminStatus': 'up'}]

    def test_inventory_ports_rates_and_link_evidence(self):
        links = [{'id': 1, 'local_device_id': 1, 'remote_device_id': 2, 'local_port_id': 11, 'remote_port_id': 21, 'protocol': 'lldp'}]
        result = self.adapter.normalize(self.rows, self.ports, links)
        validate(result)
        self.assertEqual(result['devices'][0]['site'], 'hq')
        p = result['devices'][0]['ports'][0]
        self.assertTrue(p['required'])
        self.assertEqual(p['rx_bps'], 80)
        self.assertEqual(p['speed_mbps'], 1000)
        self.assertEqual(p['neighbors'][0]['name'], 'edge.example.com')
        self.assertEqual(result['links'][0]['state'], 'down')
        self.assertIsNone(result['devices'][0]['web_url'])

    def test_new_and_removed_devices_follow_api_inventory(self):
        self.assertEqual(len(self.adapter.normalize(self.rows, [], [])['devices']), 2)
        self.assertEqual(len(self.adapter.normalize(self.rows[:1], [], [])['devices']), 1)
        self.rows[1]['disabled'] = 1
        self.assertEqual(len(self.adapter.normalize(self.rows, [], [])['devices']), 1)

    def test_missing_status_not_offline_and_admin_down_not_critical(self):
        self.rows[0].pop('status')
        self.ports[0]['ifAdminStatus'] = 'down'
        result = self.adapter.normalize(self.rows, self.ports, [])
        self.assertEqual(result['devices'][0]['state'], 'unknown')
        self.assertEqual(result['devices'][0]['ports'][0]['state'], 'disabled')

    def test_rate_overflow_cannot_break_snapshot_serialization(self):
        self.ports[0]['ifInOctets_rate'] = '1e308'
        result = self.adapter.normalize(self.rows, self.ports, [])
        self.assertIsNone(result['devices'][0]['ports'][0]['rx_bps'])
        validate(result)
        result['devices'][0]['metrics']['cpu_percent'] = float('inf')
        with self.assertRaises(ValueError):
            validate(result)

    def test_no_inferred_connection_from_names(self):
        self.assertEqual(self.adapter.normalize(self.rows, [], [])['links'], [])

    def test_https_and_origin_required(self):
        for url in ['http://api.example.com', 'https://user:pass@api.example.com', 'https://api.example.com?key=bad']:
            with self.assertRaises(SourceError):
                JSONClient(url)
        client = JSONClient('https://api.example.com/api/v0/')
        with self.assertRaises(SourceError):
            client.get('https://another.example.com/steal')

    def test_smc_partial_failure_is_attention(self):
        self.assertEqual(smc_state({'monitoring_state': 'READY', 'vpn_status_code': 'PARTIALLY_FAILED'}), 'attention')
        self.assertEqual(smc_state({'monitoring_state': 'READY', 'vpn_status_code': 'FAILED'}), 'down')
        self.assertEqual(smc_state({'monitoring_state': 'NOT_READY', 'vpn_status_code': 'ONLINE'}), 'unknown')


class ServerTests(unittest.TestCase):
    def call(self, app, path, auth=None, method='GET'):
        response = {}
        env = {'PATH_INFO': path, 'REQUEST_METHOD': method, 'wsgi.input': io.BytesIO()}
        if auth:
            env['HTTP_AUTHORIZATION'] = auth
        def start(status, headers):
            response.update(status=status, headers=dict(headers))
        response['body'] = b''.join(app(env, start))
        return response

    def test_only_web_and_versioned_api_are_served(self):
        app = Application(start=False)
        for path in ['/../.env', '/config/live.example.json', '/noctv/server.py', '/fonts/../../requirements.txt']:
            self.assertTrue(self.call(app, path)['status'].startswith('404'))
        self.assertTrue(self.call(app, '/')['status'].startswith('200'))
        self.assertTrue(self.call(app, '/api/v1/snapshot', method='POST')['status'].startswith('405'))
        self.assertEqual(self.call(app, '/', method='HEAD')['body'], b'')
        self.assertIn('Content-Security-Policy', self.call(app, '/')['headers'])

    def test_live_mode_fails_closed_and_requires_auth_for_inventory(self):
        with patch.dict(os.environ, {'NOCTV_USER': '', 'NOCTV_PASSWORD': ''}):
            with self.assertRaises(ValueError):
                Application('config/live.example.json', start=False)
        with patch.dict(os.environ, {'NOCTV_USER': 'viewer', 'NOCTV_PASSWORD': 'unit-test-passphrase-1234'}):
            app = Application('config/live.example.json', start=False)
        self.assertTrue(self.call(app, '/api/v1/snapshot')['status'].startswith('401'))
        self.assertTrue(self.call(app, '/healthz')['status'].startswith('200'))
        auth = 'Basic ' + base64.b64encode(b'viewer:unit-test-passphrase-1234').decode()
        self.assertTrue(self.call(app, '/api/v1/snapshot', auth)['status'].startswith('200'))
        self.assertNotIn(b'unit-test-passphrase', self.call(app, '/api/v1/config', auth)['body'])

class ForcepointTests(unittest.TestCase):
    def test_device_overrides_and_required_ports(self):
        from noctv.connectors.forcepoint import Forcepoint
        adapter = Forcepoint.__new__(Forcepoint)
        adapter.config = {'id': 'smc', 'devices': {'/engine/1': {'name': 'Edge', 'site': 'branch', 'root': True, 'required_ports': ['eth1'], 'web_url': 'https://firewall.example.com'}}}
        result = adapter.normalize({'generated_at': now(), 'firewalls': [{'id': '/engine/1', 'name': 'Original', 'state': 'up', 'checked_at': now(), 'nodes': [{'interfaces': [{'name': 'eth1', 'status': 'DOWN'}]}]}], 'connections': []})
        device = result['devices'][0]
        self.assertEqual(device['name'], 'Edge')
        self.assertEqual(device['site'], 'branch')
        self.assertTrue(device['root'])
        self.assertTrue(device['ports'][0]['required'])
        validate(result)

    def test_smc_forbidden_is_terminal_outside_login(self):
        import urllib.error
        from noctv.connectors.smc import Client, AuthError
        client = Client({'url': 'https://smc.example.com'}, None)
        with patch.object(client.opener, 'open', side_effect=urllib.error.HTTPError('https://smc.example.com/7.2/nodes', 403, 'secret', {}, io.BytesIO(b'secret'))):
            with self.assertRaises(AuthError):
                client.request('/7.2/nodes')
