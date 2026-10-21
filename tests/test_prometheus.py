import io
import json
import os
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from noctv.connectors.http import SourceError
from noctv.connectors.prometheus import Prometheus
from noctv.model import timestamp, validate


def row(value='1', identity='192.0.2.10', **labels):
    return {'metric': {'instance': identity, 'job': 'probe', **labels}, 'value': [time.time(), value]}


def vector(rows):
    return {'status': 'success', 'data': {'resultType': 'vector', 'result': rows}}


class PrometheusTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'PROMETHEUS_URL': 'https://monitor.example/prometheus/', 'TEST_TOKEN': 'secret-test-token'})
        env.start()
        self.addCleanup(env.stop)

    def adapter(self, **settings):
        return Prometheus({'id': 'prom', 'status_query': 'probe_success{job="probe"}', **settings})

    def collect(self, adapter, *rows):
        adapter.client.get = Mock(side_effect=[vector(r) for r in rows])
        return adapter.collect()

    def test_real_sample_timestamp_and_unit_conversion(self):
        stamp = time.time() - 10
        adapter = self.adapter(metric_queries={'latency_ms': {'query': 'probe_duration_seconds', 'scale': 1000}},
            site_label='site', site_map={'Example': 'lab'}, devices={'192.0.2.10': {'name': 'Edge', 'type': 'router'}})
        batch = self.collect(adapter, [row(site='Example')], [row(str(stamp), site='Example')], [row('0.025')], [row(str(stamp))])
        validate(batch)
        device = batch['devices'][0]
        self.assertEqual((device['id'], device['name'], device['state'], device['site'], device['type']), ('prom:192.0.2.10', 'Edge', 'up', 'lab', 'router'))
        self.assertEqual(device['observed_at'], timestamp(stamp))
        self.assertEqual(device['metrics'], {'latency_ms': 25})
        self.assertEqual(device['metric_observed_at']['latency_ms'], timestamp(stamp))
        self.assertEqual(batch['links'], [])
        params = [parse_qs(urlsplit(call.args[0]).query) for call in adapter.client.get.call_args_list]
        self.assertEqual(params[1]['query'], ['timestamp(probe_success{job="probe"})'])
        self.assertEqual(len({p['time'][0] for p in params}), 1)

    def test_stale_missing_and_invalid_status_are_unknown(self):
        for value, stamp in [('1', '1'), ('3', str(time.time())), ('NaN', str(time.time())), ('1', 'NaN')]:
            with self.subTest(value=value, stamp=stamp):
                batch = self.collect(self.adapter(), [row(value)], [row(stamp)])
                self.assertEqual(batch['devices'][0]['state'], 'unknown')
                self.assertTrue(batch['warnings'])
        adapter = self.adapter(devices={'absent': {'site': 'lab'}})
        batch = self.collect(adapter, [], [])
        self.assertEqual(batch['devices'][0]['id'], 'prom:absent')
        self.assertEqual(batch['devices'][0]['state'], 'unknown')
        self.assertIsNone(batch['devices'][0]['observed_at'])

    def test_duplicate_identity_and_mismatched_labels_never_choose_first(self):
        for samples, times in [([row(), row('0', job='other')], [row(str(time.time()))]),
                               ([row()], [row(str(time.time()), job='other')]),
                               ([row()], [row(str(time.time())), row(str(time.time()))])]:
            with self.subTest(samples=samples):
                batch = self.collect(self.adapter(), samples, times)
                self.assertEqual(batch['devices'][0]['state'], 'unknown')
                self.assertTrue(batch['warnings'])

    def test_dynamic_hosts_and_malformed_rows_are_partial(self):
        adapter = self.adapter()
        batch = self.collect(adapter, [row('0'), row(identity='new'), {'metric': {'instance': 'broken'}}, None],
                             [row(str(time.time())), row(str(time.time()), identity='new')])
        devices = {d['id']: d for d in batch['devices']}
        self.assertEqual(devices['prom:192.0.2.10']['state'], 'down')
        self.assertEqual(devices['prom:new']['state'], 'up')
        self.assertEqual(devices['prom:broken']['state'], 'unknown')
        self.assertTrue(batch['warnings'])
        self.assertEqual(len(self.collect(adapter, [row()], [row(str(time.time()))])['devices']), 1)

    def test_invalid_metric_values_do_not_escape(self):
        for metric, value, scale in [('cpu_percent', '101', 1), ('clients', '2.5', 1), ('latency_ms', '1e308', 1000), ('latency_ms', '-1', 1)]:
            adapter = self.adapter(metric_queries={metric: {'query': 'custom_metric', 'scale': scale}})
            batch = self.collect(adapter, [row()], [row(str(time.time()))], [row(value)], [row(str(time.time()))])
            self.assertEqual(batch['devices'][0]['metrics'], {})
            self.assertTrue(batch['warnings'])

    def test_selector_and_config_bounds(self):
        for settings in [{'status_query': 'up{job="node"}'}, {'status_query': 'sum(probe_success)'},
                         {'status_query': 'probe_success offset 1h'}, {'status_query': 'probe_success[5m]'},
                         {'identity_label': '__name__'}, {'max_series': 0}, {'max_series': 10001},
                         {'metric_queries': {'unknown': {'query': 'x'}}},
                         {'metric_queries': {'latency_ms': {'query': 'x', 'scale': -1}}}]:
            with self.subTest(settings=settings), self.assertRaises(SourceError):
                self.adapter(**settings)
        adapter = self.adapter(max_series=1)
        with self.assertRaisesRegex(SourceError, '^series_limit_exceeded$'):
            self.collect(adapter, [row(), row(identity='other')])

    def test_errors_redact_upstream_messages(self):
        adapter = self.adapter()
        for response in [{'status': 'error', 'error': 'secret-test-token'},
                         {'status': 'success', 'data': {'resultType': 'matrix', 'result': []}},
                         {**vector([]), 'warnings': ['secret-test-token']}]:
            adapter.client.get = Mock(return_value=response)
            with self.assertRaises(SourceError) as caught:
                adapter.collect()
            self.assertNotIn('secret', str(caught.exception))

    def test_get_only_token_header_and_https(self):
        adapter = self.adapter(token_env='TEST_TOKEN')
        adapter.client.opener = Mock()
        adapter.client.opener.open.side_effect = [io.BytesIO(json.dumps(vector(rows)).encode()) for rows in ([row()], [row(str(time.time()))])]
        self.assertEqual(adapter.collect()['devices'][0]['state'], 'up')
        for call in adapter.client.opener.open.call_args_list:
            request = call.args[0]
            self.assertEqual(request.get_method(), 'GET')
            self.assertEqual(request.get_header('Authorization'), 'Bearer secret-test-token')
            self.assertNotIn('secret-test-token', request.full_url)
            self.assertTrue(request.full_url.startswith('https://monitor.example/prometheus/api/v1/query?'))
        with patch.dict(os.environ, {'PROMETHEUS_URL': 'http://monitor.example'}), self.assertRaises(SourceError):
            self.adapter(allow_http=True)
        with patch.dict(os.environ, {'TEST_TOKEN': 'bad\nheader'}), self.assertRaisesRegex(SourceError, '^invalid_credentials$'):
            self.adapter(token_env='TEST_TOKEN')
