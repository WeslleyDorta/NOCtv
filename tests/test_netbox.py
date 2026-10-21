import io
import json
import os
import unittest
import urllib.error
from unittest.mock import Mock, patch

from noctv.collector import Collector
from noctv.connectors.http import SourceError
from noctv.connectors.netbox import NetBox
from noctv.model import now, validate


def device(identifier=1, **extra):
    return {'id': identifier, 'name': 'Core switch', 'status': {'value': 'active'},
            'site': {'name': 'Corporate HQ', 'slug': 'corporate-hq'},
            'device_type': {'model': 'Sample switch', 'manufacturer': {'name': 'Example'}},
            'primary_ip': {'address': '192.0.2.10/24'}, 'last_updated': now(), **extra}


def page(rows, next_page=None):
    return {'count': len(rows), 'next': next_page, 'results': rows}


class NetBoxTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'NETBOX_URL': 'https://netbox.example/', 'NETBOX_TOKEN': 'nbt_test.private-test-token'})
        env.start()
        self.addCleanup(env.stop)

    def adapter(self, **settings):
        return NetBox({'id': 'inventory', **settings})

    def responses(self, adapter, *payloads):
        adapter.client.opener = Mock()
        adapter.client.opener.open.side_effect = [io.BytesIO(json.dumps(p).encode()) for p in payloads]

    def test_inventory_contract_and_overrides(self):
        batch = self.adapter(site_map={'corporate-hq': 'hq'}, devices={'1': {'type': 'switch', 'web_url': 'https://switch.example/'}}).normalize([device()])
        validate(batch)
        row = batch['devices'][0]
        self.assertEqual((row['id'], row['name'], row['site'], row['type']), ('inventory:1', 'Core switch', 'hq', 'switch'))
        self.assertEqual((row['ip'], row['vendor'], row['model']), ('192.0.2.10', 'Example', 'Sample switch'))
        self.assertEqual(row['web_url'], 'https://switch.example/')
        self.assertEqual(batch['links'], [])
        self.assertEqual(batch['warnings'], [])

    def test_lifecycle_and_inventory_timestamps_never_imply_health(self):
        for status in ('active', 'offline', 'planned', 'failed', 'decommissioning', None):
            for updated in (now(), '2000-01-01T00:00:00Z', None):
                with self.subTest(status=status, updated=updated):
                    row = self.adapter().normalize([device(status={'value': status}, last_updated=updated)])['devices'][0]
                    self.assertEqual((row['state'], row['observed_at'], row['metrics'], row['ports']), ('unknown', None, {}, []))

    def test_missing_fields_and_ip_validation(self):
        row = self.adapter().normalize([{'id': 1}])['devices'][0]
        self.assertEqual((row['name'], row['ip'], row['model'], row['vendor'], row['type'], row['site']), ('1', '', '', '', 'device', 'unassigned'))
        for address, expected in [('2001:db8::1/64', '2001:db8::1'), ('192.0.2.1', '192.0.2.1'), ('192.0.2.1/200', ''), ('host.example/24', ''), (123, '')]:
            with self.subTest(address=address):
                row = self.adapter().normalize([device(primary_ip=None, primary_ip6={'address': address})])['devices'][0]
                self.assertEqual(row['ip'], expected)
        row = self.adapter(site_map={'Corporate HQ': 'wrong'}, devices={'1': {'name': 'Named', 'site': 'branch'}}).normalize([device()])['devices'][0]
        self.assertEqual((row['name'], row['site']), ('Named', 'branch'))

    def test_upstream_urls_are_not_management_links(self):
        row = self.adapter().normalize([device(url='https://netbox.example/api/dcim/devices/1/', display_url='https://netbox.example/dcim/devices/1/')])['devices'][0]
        self.assertIsNone(row['web_url'])
        row = self.adapter(devices={'1': {'web_url': 'javascript:alert(1)'}}).normalize([device()])['devices'][0]
        self.assertIsNone(row['web_url'])

    def test_get_auth_pagination_and_dynamic_inventory(self):
        adapter = self.adapter()
        self.responses(adapter, page([device()], 'https://netbox.example/api/dcim/devices/?limit=100&offset=100'), page([device(2)]), page([device(3)]))
        first = adapter.collect()
        validate(first)
        self.assertEqual([d['id'] for d in first['devices']], ['inventory:1', 'inventory:2'])
        self.assertEqual([d['id'] for d in adapter.collect()['devices']], ['inventory:3'])
        for call in adapter.client.opener.open.call_args_list:
            request = call.args[0]
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(request.get_header('Authorization'), 'Bearer nbt_test.private-test-token')
            self.assertNotIn('private-test-token', request.full_url)
            self.assertIsNone(request.data)
            self.assertEqual(call.kwargs['timeout'], 10)
        self.assertIn('exclude=config_context', adapter.client.opener.open.call_args_list[0].args[0].full_url)

    def test_deployment_prefix_and_query_relative_next(self):
        with patch.dict(os.environ, {'NETBOX_URL': 'https://netbox.example/netbox/'}):
            adapter = self.adapter()
        self.responses(adapter, page([device()], '?limit=100&offset=100'), page([device(2)]))
        adapter.collect()
        urls = [c.args[0].full_url for c in adapter.client.opener.open.call_args_list]
        self.assertTrue(all(u.startswith('https://netbox.example/netbox/api/dcim/devices/?') for u in urls))

    def test_untrusted_pagination_never_receives_credentials(self):
        for target in ('https://foreign.example/api/dcim/devices/?offset=100', '//foreign.example/api/dcim/devices/',
                       'http://netbox.example/api/dcim/devices/', 'https://user:private-test-token@netbox.example/api/dcim/devices/',
                       '/api/users/tokens/', '/api/dcim/devices/1/', '/api/dcim/devices/#fragment'):
            with self.subTest(target=target):
                adapter = self.adapter()
                self.responses(adapter, page([device()], target))
                with self.assertRaisesRegex(SourceError, '^untrusted_resource$'):
                    adapter.collect()
                self.assertEqual(adapter.client.opener.open.call_count, 1)

    def test_invalid_shapes_and_duplicate_ids_are_rejected(self):
        for payload in ([], {}, {'results': [], 'next': []}, {'results': [], 'next': ''}, {'results': [], 'next': 'https://[bad'},
                        page(['private-test-token']), page([{'id': None}]), page([{'id': True}]), page([{'id': -1}]),
                        page([device(), device()]), page([device(site=[])]), page([device(device_type={'manufacturer': []})])):
            with self.subTest(payload=payload):
                adapter = self.adapter()
                self.responses(adapter, payload)
                with self.assertRaises(SourceError) as caught:
                    adapter.collect()
                self.assertNotIn('private-test-token', str(caught.exception))

    def test_pagination_cycles_and_bounds(self):
        adapter = self.adapter()
        route = '/api/dcim/devices/?offset=100'
        self.responses(adapter, page([device()], route), page([device(2)], route))
        with self.assertRaisesRegex(SourceError, '^pagination_cycle$'):
            adapter.collect()
        self.assertEqual(adapter.client.opener.open.call_count, 2)
        self.responses(adapter, page([device()], route))
        with patch('noctv.connectors.netbox.MAX_PAGES', 1), self.assertRaisesRegex(SourceError, '^pagination_limit_exceeded$'):
            adapter.collect()
        self.responses(adapter, page([device(), device(2)]))
        with patch('noctv.connectors.netbox.MAX_DEVICES', 1), self.assertRaisesRegex(SourceError, '^inventory_limit_exceeded$'):
            adapter.collect()

    def test_auth_errors_are_terminal_and_preserve_previous_inventory(self):
        source = {'id': 'inventory', 'type': 'netbox', 'interval_seconds': 300, 'max_age_seconds': 900}
        for code in (401, 403):
            with self.subTest(code=code):
                adapter = self.adapter()
                collector = Collector({'mode': 'live', 'connectors': [source]})
                self.responses(adapter, page([device()]))
                with patch.dict('noctv.collector.ADAPTERS', {'netbox': lambda _: adapter}):
                    self.assertTrue(collector.poll(source))
                    adapter.client.opener.open.side_effect = urllib.error.HTTPError('https://netbox.example/', code, 'private-test-token', {}, io.BytesIO())
                    self.assertFalse(collector.poll(source))
                snapshot = collector.snapshot()
                self.assertEqual(snapshot['sources'][0]['error'], 'http_' + str(code))
                self.assertEqual(snapshot['devices'][0]['state'], 'unknown')
                self.assertTrue(snapshot['devices'][0]['stale'])
                self.assertFalse(any(a['severity'] == 'critical' for a in snapshot['alerts']))
                self.assertNotIn('private-test-token', json.dumps(snapshot))

    def test_successful_inventory_poll_does_not_refresh_observation(self):
        source = {'id': 'inventory', 'type': 'netbox', 'interval_seconds': 300, 'max_age_seconds': 900}
        adapter = self.adapter()
        collector = Collector({'mode': 'live', 'connectors': [source]})
        self.responses(adapter, page([device()]))
        with patch.dict('noctv.collector.ADAPTERS', {'netbox': lambda _: adapter}):
            self.assertTrue(collector.poll(source))
        snapshot = collector.snapshot()
        self.assertEqual(snapshot['sources'][0]['state'], 'ok')
        self.assertEqual(snapshot['devices'][0]['state'], 'unknown')
        self.assertIsNone(snapshot['devices'][0]['observed_at'])
        self.assertTrue(snapshot['devices'][0]['stale'])
        self.assertEqual(snapshot['alerts'], [])

    def test_missing_credentials_and_injected_header(self):
        with patch.dict(os.environ, {'NETBOX_TOKEN': ''}), self.assertRaisesRegex(SourceError, '^missing_credentials$'):
            self.adapter()
        with patch.dict(os.environ, {'NETBOX_TOKEN': 'secret\r\nX-Extra: value'}), self.assertRaisesRegex(SourceError, '^invalid_credentials$'):
            self.adapter()


if __name__ == '__main__':
    unittest.main()
