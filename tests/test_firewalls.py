import io
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, Mock, patch

from noctv.connectors.firewalls import CheckPoint, FirewallClient, FortiGate, PANOS, SophosCentral
from noctv.connectors.http import SourceError
from noctv.model import validate

ENV = {'FORTIGATE_URL': 'https://firewall.example.test', 'FORTIGATE_TOKEN': 'private-token',
       'PANOS_URL': 'https://firewall.example.test', 'PANOS_API_KEY': 'private-key',
       'CHECKPOINT_URL': 'https://manager.example.test', 'CHECKPOINT_USERNAME': 'reader', 'CHECKPOINT_PASSWORD': 'private-password',
       'SOPHOS_URL': 'https://api-eu01.central.sophos.com', 'SOPHOS_CLIENT_ID': 'client',
       'SOPHOS_CLIENT_SECRET': 'private-secret', 'SOPHOS_TENANT_ID': 'tenant'}
PAN_XML = b'<response status="success"><result><system><serial>pan-1</serial><hostname>edge</hostname><model>PA-VM</model></system></result></response>'


@patch.dict('os.environ', ENV, clear=True)
class AdapterTests(unittest.TestCase):
    def test_fortigate_inventory_and_override(self):
        adapter = FortiGate({'id': 'fg', 'devices': {'fg-1': {'site': 'hq', 'name': 'Edge'}}})
        adapter.client.get = Mock(return_value={'status': 'success', 'serial': 'fg-1', 'results': {'hostname': 'fw', 'model': 'FGT'}})
        result = adapter.collect()
        validate(result)
        item = result['devices'][0]
        self.assertEqual((item['id'], item['state'], item['management_state'], item['site']), ('fg:fg-1', 'unknown', 'up', 'hq'))
        self.assertEqual(result['links'], [])
        self.assertEqual(result['warnings'], [])
        self.assertEqual(result['capabilities'], ['inventory', 'management'])
        adapter.client.get.assert_called_once_with('api/v2/monitor/system/status')

    def test_fortigate_error_and_missing_id(self):
        adapter = FortiGate({'id': 'fg'})
        for response in [{'status': 'error', 'message': 'private-token'}, {'status': 'success', 'results': {}}]:
            adapter.client.get = Mock(return_value=response)
            with self.assertRaises(SourceError) as caught:
                adapter.collect()
            self.assertNotIn('private-token', str(caught.exception))

    def test_panos_inventory_request_is_read_only_and_key_is_header(self):
        adapter = PANOS({'id': 'pan', 'site_map': {'pan-1': 'hq'}})
        adapter.client.request = Mock(return_value=ET.fromstring(PAN_XML))
        item = adapter.collect()['devices'][0]
        self.assertEqual((item['id'], item['state'], item['management_state'], item['site']), ('pan:pan-1', 'unknown', 'up', 'hq'))
        args, kwargs = adapter.client.request.call_args
        self.assertEqual(args[1], {'type': 'op', 'cmd': '<show><system><info></info></system></show>'})
        self.assertTrue(kwargs['xml'])
        self.assertEqual(adapter.client.headers, {'X-PAN-KEY': 'private-key'})

    def test_panos_error_and_missing_system(self):
        adapter = PANOS({'id': 'pan'})
        for response in ['<response status="error"><msg>private-key</msg></response>', '<response status="success"><result /></response>', '<response status="success"><result><system /></result></response>']:
            adapter.client.request = Mock(return_value=ET.fromstring(response))
            with self.assertRaises(SourceError) as caught:
                adapter.collect()
            self.assertNotIn('private-key', str(caught.exception))

    def test_checkpoint_pagination_and_logout_no_gateway_health_inference(self):
        adapter = CheckPoint({'id': 'cp'})
        adapter.client.request = Mock(side_effect=[{'sid': 'session'},
            {'objects': [{'uid': 'g1', 'name': 'Edge', 'type': 'simple-gateway'}], 'total': 2},
            {'objects': [{'uid': 'm1', 'name': 'Manager', 'type': 'checkpoint-host'}], 'total': 2}, {}])
        result = adapter.collect()
        validate(result)
        self.assertEqual([x['type'] for x in result['devices']], ['firewall', 'server'])
        self.assertTrue(all(x['state'] == x['management_state'] == 'unknown' for x in result['devices']))
        self.assertEqual(adapter.client.request.call_args_list[2].args[1]['offset'], 1)
        self.assertEqual(adapter.client.request.call_args.args, ('web_api/logout', {}))
        self.assertNotIn('X-chkp-sid', adapter.client.headers)

    def test_checkpoint_missing_id_logs_out_and_clears_session(self):
        adapter = CheckPoint({'id': 'cp'})
        adapter.client.request = Mock(side_effect=[{'sid': 'session'}, {'objects': [{}], 'total': 1}, {}])
        with self.assertRaisesRegex(SourceError, 'missing_device_id'):
            adapter.collect()
        self.assertEqual(adapter.client.request.call_args.args[0], 'web_api/logout')
        self.assertNotIn('X-chkp-sid', adapter.client.headers)

    def test_checkpoint_logout_failure_is_a_warning(self):
        adapter = CheckPoint({'id': 'cp'})
        adapter.client.request = Mock(side_effect=[{'sid': 'session'}, {'objects': [], 'total': 0}, SourceError('http_503')])
        self.assertEqual(adapter.collect()['warnings'], ['logout_failed'])
        self.assertNotIn('X-chkp-sid', adapter.client.headers)

    def test_checkpoint_auth_error_sanitized(self):
        adapter = CheckPoint({'id': 'cp'})
        adapter.client.request = Mock(return_value={'message': 'private-password'})
        with self.assertRaisesRegex(SourceError, '^authentication_failed$'):
            adapter.collect()

    def test_checkpoint_pagination_limit_and_logout_failure(self):
        adapter = CheckPoint({'id': 'cp'})
        adapter.client.request = Mock(side_effect=[{'sid': 'session'}] + [{'objects': [{'uid': 'g'}], 'total': 99}] * 10 + [SourceError('http_500')])
        with self.assertRaisesRegex(SourceError, '^pagination_limit$'):
            adapter.collect()
        self.assertNotIn('X-chkp-sid', adapter.client.headers)

    def sophos(self):
        adapter = SophosCentral({'id': 'sophos'})
        adapter.auth.request = Mock(return_value={'access_token': 'bearer'})
        return adapter

    def test_sophos_connected_disconnected_missing_do_not_claim_dataplane_health(self):
        adapter = self.sophos()
        adapter.client.get = Mock(return_value={'items': [
            {'id': 's1', 'status': {'connected': True}}, {'id': 's2', 'status': {'connected': False}}, {'id': 's3'}],
            'pages': {'current': 1, 'total': 1}})
        result = adapter.collect()
        validate(result)
        self.assertEqual([x['management_state'] for x in result['devices']], ['up', 'down', 'unknown'])
        self.assertTrue(all(x['state'] == 'unknown' for x in result['devices']))
        self.assertNotIn('Authorization', adapter.client.headers)
        self.assertEqual(adapter.auth.request.call_args.args[0], 'api/v2/oauth2/token')

    def test_sophos_missing_pagination_or_id_fails(self):
        adapter = self.sophos()
        for response in [{'items': []}, {'items': [{}], 'pages': {'current': 1, 'total': 1}}]:
            adapter.client.get = Mock(return_value=response)
            with self.assertRaises(SourceError):
                adapter.collect()
            self.assertNotIn('Authorization', adapter.client.headers)

    def test_sophos_paginates(self):
        adapter = self.sophos()
        adapter.client.get = Mock(side_effect=[{'items': [{'id': 's1'}], 'pages': {'current': 1, 'total': 2}},
                                               {'items': [{'id': 's2'}], 'pages': {'current': 2, 'total': 2}}])
        self.assertEqual(len(adapter.collect()['devices']), 2)
        self.assertIn('page=2', adapter.client.get.call_args.args[0])

    def test_sophos_auth_error_sanitized(self):
        adapter = self.sophos()
        adapter.auth.request = Mock(return_value={'error_description': 'private-secret'})
        with self.assertRaisesRegex(SourceError, '^authentication_failed$'):
            adapter.collect()

    def test_missing_credentials(self):
        with patch.dict('os.environ', {}, clear=True):
            for adapter in [FortiGate, PANOS, CheckPoint, SophosCentral]:
                with self.assertRaisesRegex(SourceError, '^missing_credentials$'):
                    adapter({'id': 'test'})

    def test_unavailable_upstream_propagates_error_instead_of_false_device_down(self):
        for cls in [FortiGate, PANOS, CheckPoint, SophosCentral]:
            adapter = cls({'id': 'test'})
            adapter.client.get = Mock(side_effect=SourceError('http_503'))
            adapter.client.request = Mock(side_effect=SourceError('http_503'))
            if isinstance(adapter, SophosCentral):
                adapter.auth.request = Mock(return_value={'access_token': 'token'})
            with self.assertRaisesRegex(SourceError, '^http_503$'):
                adapter.collect()


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client = FirewallClient('https://firewall.example.test/', {'X-PAN-KEY': 'secret'})

    def respond(self, raw):
        self.client.opener = MagicMock()
        self.client.opener.open.return_value.__enter__.return_value.read.return_value = raw

    def test_xml_and_request_bounds(self):
        self.respond(PAN_XML)
        self.assertEqual(self.client.request('api/', xml=True).tag, 'response')
        self.client.opener.open.assert_called_once()
        self.assertEqual(self.client.opener.open.call_args.kwargs['timeout'], 10)
        self.client.opener.open.return_value.__enter__.return_value.read.assert_called_once_with(2_000_001)

    def test_dtd_entities_and_utf16_rejected(self):
        evil = '<!DOCTYPE response [<!ENTITY x SYSTEM "file:///etc/passwd">]><response>&x;</response>'
        for raw in [evil.encode(), evil.encode('utf-16'), evil.encode('utf-32'), b'<!DOCTYPE a [<!ENTITY x "boom">]><a>&x;</a>']:
            self.respond(raw)
            with self.assertRaises(SourceError):
                self.client.request('api/', xml=True)

    def test_invalid_and_oversized_responses(self):
        for raw in [b'private-credential', b'x' * 2_000_001]:
            self.respond(raw)
            with self.assertRaises(SourceError) as caught:
                self.client.get('api/')
            self.assertNotIn('private-credential', str(caught.exception))

    def test_cross_origin_rejected_before_network(self):
        self.client.opener = MagicMock()
        with self.assertRaisesRegex(SourceError, '^untrusted_resource$'):
            self.client.request('https://other.example.test/api/', {'password': 'secret'})
        self.client.opener.open.assert_not_called()

    def test_redirect_and_http_errors_never_include_body_or_url(self):
        for code in [302, 401, 500]:
            self.client.opener = MagicMock()
            self.client.opener.open.side_effect = urllib.error.HTTPError('https://secret.example.test', code, 'private-key', {}, io.BytesIO(b'private-key'))
            with self.assertRaisesRegex(SourceError, '^http_' + str(code) + '$'):
                self.client.get('api/')

    def test_network_error_is_sanitized(self):
        self.client.opener = Mock()
        self.client.opener.open.side_effect = urllib.error.URLError('private-token and private-host')
        with self.assertRaisesRegex(SourceError, '^connection_or_response_error$'):
            self.client.get('api/')

    def test_tls_required_and_redirect_handler_rejects(self):
        from noctv.connectors.http import NoRedirect
        with self.assertRaises(SourceError):
            FirewallClient('http://firewall.example.test/')
        original = FirewallClient('https://firewall.example.test/')
        self.assertTrue(any(isinstance(h, NoRedirect) for h in original.opener.handlers))
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://elsewhere.test'))


if __name__ == '__main__':
    unittest.main()
