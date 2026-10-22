"""Explicitly configured service checks; never discover or scan a subnet."""
from concurrent.futures import ThreadPoolExecutor
import ipaddress
import os
import re
import shutil
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from .http import NoRedirect, SourceError
from ..model import now, web_url


def host(value):
    if not isinstance(value, str) or len(value) > 253 or '%' in value:
        raise SourceError('invalid_probe_host')
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        if not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', p) for p in value.rstrip('.').split('.')):
            raise SourceError('invalid_probe_host')
        return value


def validate_probes(config):
    checks = config.get('checks')
    if not isinstance(checks, list) or not 1 <= len(checks) <= 50:
        raise SourceError('probes_require_1_to_50_checks')
    ids = set()
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', check['id']) or check['id'] in ids:
            raise SourceError('invalid_probe_id')
        ids.add(check['id'])
        if check.get('kind') not in ('http', 'tcp', 'dns', 'ping'):
            raise SourceError('invalid_probe_kind')
        if type(check.get('timeout_seconds', 5)) is not int or not 1 <= check.get('timeout_seconds', 5) <= 15:
            raise SourceError('invalid_probe_timeout')
        if check['kind'] == 'http':
            if not isinstance(check.get('url_env'), str) or not re.fullmatch(r'[A-Z_][A-Z_0-9]*', check['url_env']):
                raise SourceError('http_probe_requires_url_env')
            codes = check.get('expected_status', list(range(200, 300)))
            if not isinstance(codes, list) or not codes or any(type(c) is not int or not 100 <= c <= 599 for c in codes):
                raise SourceError('invalid_expected_http_status')
            if 'keyword' in check and (not isinstance(check['keyword'], str) or not 1 <= len(check['keyword']) <= 512):
                raise SourceError('invalid_http_keyword')
            if type(check.get('certificate_warning_days', 21)) is not int or not 0 <= check.get('certificate_warning_days', 21) <= 365:
                raise SourceError('invalid_certificate_warning')
        else:
            host(check.get('host'))
        if check['kind'] == 'tcp' and (type(check.get('port')) is not int or not 1 <= check['port'] <= 65535):
            raise SourceError('invalid_tcp_port')
        if check['kind'] == 'dns':
            if check.get('record_type', 'A') not in ('A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS', 'PTR'):
                raise SourceError('invalid_dns_record_type')
            if 'dns_server' in check:
                ipaddress.ip_address(check['dns_server'])
            if 'expected_value' in check and not isinstance(check['expected_value'], str):
                raise SourceError('invalid_dns_expected_value')


class Probes:
    def __init__(self, config):
        validate_probes(config)
        self.config = config

    def check(self, check):
        kind, timeout = check['kind'], check.get('timeout_seconds', 5)
        device = {'id': self.config['id'] + ':' + check['id'], 'name': check.get('name', check['id']),
                  'type': 'service', 'site': check.get('site', 'unassigned'), 'category': kind.upper(),
                  'model': kind.upper() + ' check', 'state': 'unknown', 'observed_at': None,
                  'ip': check.get('host', ''), 'web_url': web_url(check.get('web_url')), 'ports': [], 'metrics': {}, 'services': []}
        started = time.monotonic()
        state, reason = 'up', 'Check passed'
        try:
            if kind == 'http':
                url = os.environ.get(check['url_env'], '')
                parsed = urllib.parse.urlsplit(url)
                if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or any(ord(c) < 32 for c in url):
                    raise SourceError('invalid_or_missing_url')
                device['ip'], device['category'], device['model'] = parsed.hostname, parsed.scheme.upper(), parsed.scheme.upper() + ' check'
                context = ssl.create_default_context(cafile=check.get('ca_file'))
                if parsed.scheme == 'https':
                    with socket.create_connection((parsed.hostname, parsed.port or 443), timeout=timeout) as raw:
                        with context.wrap_socket(raw, server_hostname=parsed.hostname) as tls:
                            expires = ssl.cert_time_to_seconds(tls.getpeercert()['notAfter'])
                    days = max(0, int((expires - time.time()) // 86400))
                    device['metrics']['certificate_days'] = days
                    if days <= check.get('certificate_warning_days', 21):
                        state, reason = 'attention', 'TLS certificate expires soon'
                headers = {'User-Agent': 'NOCtv-service-check/1', 'Accept-Encoding': 'identity'}
                if check.get('token_env'):
                    token = os.environ.get(check['token_env'], '')
                    if parsed.scheme != 'https' or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
                        raise SourceError('invalid_probe_credentials')
                    headers['Authorization'] = 'Bearer ' + token
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(), urllib.request.HTTPSHandler(context=context))
                try:
                    response = opener.open(urllib.request.Request(url, headers=headers), timeout=timeout)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    device['metrics']['http_status_code'] = response.code
                    if response.code not in check.get('expected_status', range(200, 300)):
                        state, reason = 'down', 'Unexpected HTTP status'
                    elif check.get('keyword'):
                        body = response.read(262145)
                        if len(body) > 262144:
                            raise SourceError('keyword_response_too_large')
                        if check['keyword'] not in body.decode('utf-8', errors='replace'):
                            state, reason = 'down', 'Expected keyword not found'
            elif kind == 'tcp':
                with socket.create_connection((check['host'], check['port']), timeout=timeout):
                    pass
            else:
                binary = shutil.which('dig' if kind == 'dns' else 'ping')
                if not binary:
                    raise SourceError('probe_dependency_missing')
                args = ['+time=' + str(timeout), '+tries=1', '+noall', '+answer', '+comments', '-t', check.get('record_type', 'A'), check['host']] if kind == 'dns' else ['-n', '-c', '1', '-W', str(timeout), check['host']]
                if kind == 'dns' and check.get('dns_server'):
                    args.append('@' + check['dns_server'])
                result = subprocess.run([binary, *args], shell=False, capture_output=True, timeout=timeout + 2,
                                        stdin=subprocess.DEVNULL, env={'PATH': os.defpath, 'LANG': 'C'})
                if kind == 'ping':
                    state, reason = ('up', 'ICMP reply received') if result.returncode == 0 else ('down', 'No ICMP reply') if result.returncode == 1 else ('unknown', 'ICMP tool could not run')
                else:
                    output = result.stdout[:65536].decode('utf-8', errors='replace')
                    answers = [line.split(None, 4)[4] for line in output.splitlines() if line and not line.startswith(';') and len(line.split(None, 4)) == 5]
                    if result.returncode or 'status: NOERROR' not in output or not answers:
                        state, reason = 'down', 'DNS query failed or returned no answer'
                    elif check.get('expected_value') is not None and check['expected_value'] not in answers:
                        state, reason = 'down', 'DNS answer did not match'
            if state != 'unknown':
                device['metrics']['latency_ms'] = round((time.monotonic() - started) * 1000, 2)
        except ssl.SSLCertVerificationError:
            state, reason = 'down', 'TLS certificate verification failed'
        except SourceError as error:
            state, reason = 'unknown', str(error)
        except (TimeoutError, ConnectionError, socket.gaierror, urllib.error.URLError, subprocess.TimeoutExpired):
            state, reason = 'down', 'Connection failed or timed out'
        except (OSError, ValueError, KeyError):
            state, reason = 'unknown', 'Probe configuration or local runtime error'
        device.update(state=state, observed_at=now(), services=[{'name': reason, 'state': state}])
        return device

    def collect(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            devices = list(executor.map(self.check, self.config['checks']))
        return {'devices': devices, 'links': [], 'warnings': ['probe_unavailable'] if any(d['state'] == 'unknown' for d in devices) else []}
