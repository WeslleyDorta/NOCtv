import io
import json
import os
import time
import unittest
import urllib.error
from unittest.mock import Mock, patch

from noctv.connectors.http import SourceError
from noctv.connectors.zabbix import RPCClient, Zabbix
from noctv.model import timestamp, validate


def host(identifier='1', **extra):
    return {'hostid': identifier, 'host': 'test-host', 'name': 'Test device', 'status': '0',
            'inventory': {'location': 'Test site', 'vendor': 'Example', 'model': 'Sample', 'os': 'Linux'},
            'interfaces': [{'main': '1', 'useip': '1', 'ip': '192.0.2.10'}], **extra}


def item(key='icmpping', value='1', **extra):
    return {'itemid': key, 'hostid': '1', 'key_': key, 'lastvalue': value,
            'lastclock': str(int(time.time()) - 10), 'status': '0', 'state': '0', **extra}


class ZabbixTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'ZABBIX_URL': 'https://monitor.example/api_jsonrpc.php', 'ZABBIX_TOKEN': 'private-test-token'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def adapter(self, **settings):
        return Zabbix({'id': 'test', 'max_age_seconds': 600, **settings})

    def test_contract_and_observed_status(self):
        sample = item()
        batch = self.adapter(site_map={'Test site': 'lab'}, devices={'1': {'type': 'server'}}).normalize(
            [host()], [sample, item('icmppingsec', '0.025'), item('vm.memory.size[pused]', '72')])
        validate(batch)
        device = batch['devices'][0]
        self.assertEqual((device['id'], device['state'], device['type'], device['site']), ('test:1', 'up', 'server', 'lab'))
        self.assertEqual(device['observed_at'], timestamp(sample['lastclock']))
        self.assertEqual(device['metrics'], {'latency_ms': 25, 'memory_percent': 72})
        self.assertEqual(device['vendor'], 'Example')
        self.assertEqual(batch['links'], [])

    def test_enabled_host_is_not_online_evidence(self):
        device = self.adapter().normalize([host()], [])['devices'][0]
        self.assertEqual(device['state'], 'unknown')
        self.assertIsNone(device['observed_at'])

    def test_disabled_hosts_and_unusable_samples(self):
        self.assertEqual(self.adapter().normalize([host(status='1')], [item()])['devices'], [])
        for extra in ({'status': '1'}, {'state': '1'}, {'lastclock': '0'}, {'lastclock': str(int(time.time()) - 3600)}, {'lastvalue': '3'}):
            with self.subTest(extra=extra):
                self.assertEqual(self.adapter().normalize([host()], [item(**extra)])['devices'][0]['state'], 'unknown')
        self.assertEqual(self.adapter().normalize([host()], [item(value='0')])['devices'][0]['state'], 'down')

    def test_explicit_metrics_and_ports_are_fresh_and_typed(self):
        adapter = self.adapter(item_map={'cpu_percent': 'custom.cpu', 'toner_percent': 'custom.toner', 'clients': 'custom.clients'},
            devices={'1': {'ports': [{'id': 'uplink', 'state_key': 'custom.port', 'required': True}]}})
        batch = adapter.normalize([host()], [item(), item('custom.cpu', '33'), item('custom.toner', '101'),
            item('custom.clients', '2.5'), item('custom.port', '2')])
        validate(batch)
        device = batch['devices'][0]
        self.assertEqual(device['metrics'], {'cpu_percent': 33})
        self.assertEqual((device['ports'][0]['state'], device['ports'][0]['required']), ('down', True))
        stale_batch = adapter.normalize([host()], [item(), item('custom.cpu', '99', lastclock='1'), item('custom.port', '1', state='1')])
        self.assertEqual(stale_batch['devices'][0]['metrics'], {})
        self.assertEqual(stale_batch['devices'][0]['ports'][0]['state'], 'unknown')
        self.assertEqual(stale_batch['warnings'], ['1:mapped_item_unavailable'])

    def test_missing_mapping_and_override(self):
        adapter = self.adapter(item_map={'cpu_percent': 'wrong'}, devices={'1': {'item_map': {'status': 'custom.alive'}, 'site': 'branch', 'type': 'printer'}})
        batch = adapter.normalize([host()], [item(), item('custom.alive', '0')])
        self.assertEqual(batch['devices'][0]['state'], 'down')
        self.assertEqual(batch['devices'][0]['site'], 'branch')
        self.assertEqual(batch['warnings'], ['1:mapped_item_unavailable'])
        with self.assertRaisesRegex(SourceError, 'invalid_item_map'):
            self.adapter(item_map={'invented_metric': 'x'})
        with self.assertRaisesRegex(SourceError, 'invalid_port_map'):
            self.adapter(ports=[{'id': 'a', 'state_key': 'x'}, {'id': 'a', 'state_key': 'y'}])

    def test_missing_credentials_and_nonfinite_metrics(self):
        with patch.dict(os.environ, {'ZABBIX_TOKEN': ''}), self.assertRaisesRegex(SourceError, '^missing_credentials$'):
            self.adapter()
        batch = self.adapter().normalize([host()], [item(), item('icmppingsec', '1e308')])
        self.assertEqual(batch['devices'][0]['metrics'], {})

    def test_dynamic_inventory_and_restricted_output(self):
        adapter = self.adapter()
        adapter.client.call = Mock(side_effect=[[host()], [item()], [host(), host('2')], [item(), item(hostid='2')]])
        self.assertEqual(len(adapter.collect()['devices']), 1)
        self.assertEqual(len(adapter.collect()['devices']), 2)
        methods = [c.args[0] for c in adapter.client.call.call_args_list]
        self.assertEqual(methods, ['host.get', 'item.get', 'host.get', 'item.get'])
        self.assertNotIn('details', adapter.client.call.call_args_list[0].args[1]['selectInterfaces'])
        self.assertEqual(adapter.client.call.call_args_list[-1].args[1]['hostids'], ['1', '2'])


class RPCTests(unittest.TestCase):
    def client(self, payload):
        client = RPCClient('https://monitor.example/api_jsonrpc.php', 'private-test-token')
        client.opener = Mock()
        client.opener.open.return_value = io.BytesIO(json.dumps(payload).encode())
        return client

    def test_auth_in_header_only_and_no_writes(self):
        client = self.client({'jsonrpc': '2.0', 'id': 1, 'result': []})
        self.assertEqual(client.call('host.get', {}), [])
        request = client.opener.open.call_args.args[0]
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Authorization'), 'Bearer private-test-token')
        self.assertNotIn('private-test-token', request.full_url + request.data.decode())
        self.assertEqual(client.opener.open.call_args.kwargs['timeout'], 10)
        with self.assertRaisesRegex(SourceError, 'method_not_allowed'):
            client.call('host.delete', {})
        self.assertEqual(client.opener.open.call_count, 1)

    def test_rejection_and_response_redaction(self):
        client = self.client({'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32602, 'data': 'Not authorized. private-test-token'}})
        with self.assertRaisesRegex(SourceError, '^authentication_rejected$'):
            client.call('host.get', {})
        client = self.client({'jsonrpc': '2.0', 'id': 1, 'error': {'data': 'private-test-token'}})
        with self.assertRaisesRegex(SourceError, '^rpc_error$'):
            client.call('host.get', {})
        client.opener.open.side_effect = urllib.error.HTTPError('https://monitor.example', 401, 'private-test-token', {}, io.BytesIO())
        with self.assertRaisesRegex(SourceError, '^http_401$'):
            client.call('host.get', {})

    def test_invalid_responses_and_size_bound(self):
        for payload in ([], {'jsonrpc': '2.0', 'id': 2, 'result': []}, {'jsonrpc': '2.0', 'id': 1, 'result': ['private-test-token']}):
            with self.subTest(payload=payload), self.assertRaisesRegex(SourceError, '^invalid_rpc_response$'):
                self.client(payload).call('item.get', {})
        client = self.client({})
        client.opener.open.return_value = io.BytesIO(b' ' * 8_000_001)
        with self.assertRaisesRegex(SourceError, '^response_too_large$'):
            client.call('host.get', {})

    def test_tls_url_credentials_and_redirect_restrictions(self):
        for url in ('http://monitor.example/api', 'https://user:secret@monitor.example/api', 'https://monitor.example/api?token=secret', 'https://monitor.example/api#secret'):
            with self.subTest(url=url), self.assertRaisesRegex(SourceError, 'invalid_api_url'):
                RPCClient(url, 'token')
        with self.assertRaisesRegex(SourceError, 'invalid_credentials'):
            RPCClient('https://monitor.example/api', 'token\r\nExtra: bad')
        client = RPCClient('https://monitor.example/api', 'token')
        redirect = next(h for h in client.opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler))
        self.assertIsNone(redirect.redirect_request(None, None, 302, '', {}, 'https://other.example'))
        https = next(h for h in client.opener.handlers if isinstance(h, urllib.request.HTTPSHandler))
        self.assertTrue(https._context.check_hostname)


if __name__ == '__main__':
    unittest.main()
