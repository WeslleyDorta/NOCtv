"""Operator-initiated diagnostics, independent of any monitoring connector."""
import ipaddress
import os
import shutil
import subprocess
import threading
import time

TOOLS = {
    'ping': ('Ping', 'ping', ['-n', '-c', '4', '-W', '2']),
    'trace': ('Traceroute', 'traceroute', ['-n', '-m', '12', '-w', '1', '-q', '1']),
    'dns': ('Reverse DNS', 'dig', ['+time=2', '+tries=1', '+short', '-x']),
    'nmap_quick': ('Nmap · TCP ports', 'nmap', ['--unprivileged', '-n', '-sT', '-Pn', '-F', '--max-retries', '1', '--host-timeout', '25s']),
    'nmap_services': ('Nmap · services', 'nmap', ['--unprivileged', '-n', '-sT', '-Pn', '-sV', '--version-light', '--top-ports', '30', '--max-retries', '1', '--host-timeout', '25s']),
}


def validate_config(config):
    setting = config.setdefault('diagnostics', {})
    if not isinstance(setting, dict):
        raise ValueError('invalid diagnostics configuration')
    setting.setdefault('enabled', False)
    setting.setdefault('allowed_cidrs', [])
    if type(setting['enabled']) is not bool or not isinstance(setting['allowed_cidrs'], list):
        raise ValueError('invalid diagnostics configuration')
    if any(not isinstance(cidr, str) for cidr in setting['allowed_cidrs']):
        raise ValueError('diagnostic CIDRs must be strings')
    for cidr in setting['allowed_cidrs']:
        ipaddress.ip_network(cidr)
    if setting['enabled'] and not setting['allowed_cidrs']:
        raise ValueError('enabled diagnostics require allowed_cidrs')


class Diagnostics:
    def __init__(self, config):
        self.demo = config['mode'] == 'demo'
        self.enabled = config['diagnostics']['enabled']
        self.networks = [ipaddress.ip_network(c) for c in config['diagnostics']['allowed_cidrs']]
        self.lock = threading.Lock()
        self.last_run = -float('inf')

    def status(self):
        return {'mode': 'demo' if self.demo else 'live', 'enabled': self.demo or self.enabled,
                'tools': [{'id': key, 'label': label, 'available': self.demo or bool(shutil.which(binary)), 'binary': binary}
                          for key, (label, binary, _) in TOOLS.items()]}

    def run(self, request):
        if not isinstance(request, dict) or not isinstance(request.get('tool'), str) or request['tool'] not in TOOLS or not isinstance(request.get('target'), str):
            return 400, {'error': 'Choose a supported tool and a single target IP.'}
        try:
            target = ipaddress.ip_address(request['target'])
        except ValueError:
            return 400, {'error': 'Enter a single IPv4 or IPv6 address, without a port or hostname.'}
        if target.is_loopback or target.is_link_local or target.is_multicast or target.is_unspecified or '%' in str(target) or getattr(target, 'ipv4_mapped', None):
            return 403, {'error': 'This target address is not permitted.'}
        key = request['tool']
        label, binary, args = TOOLS[key]
        if self.demo:
            return 200, {'simulated': True, 'tool': key, 'target': str(target), 'exit_code': 0,
                         'output': f'DEMO · SIMULATED\n{label} for {target}\nNo network request or command was executed.\nConfigure live diagnostics to run this tool against your permitted networks.'}
        if not self.enabled or not any(target in network for network in self.networks):
            return 403, {'error': 'Diagnostics are disabled or this IP is outside allowed_cidrs.'}
        executable = shutil.which(binary)
        if not executable:
            return 503, {'error': f'Missing dependency: {binary}. Use the Docker image or follow docs/diagnostics.md.'}
        if not self.lock.acquire(blocking=False):
            return 429, {'error': 'Another diagnostic is running. Try again when it finishes.'}
        try:
            if time.monotonic() - self.last_run < 5:
                return 429, {'error': 'Wait five seconds between diagnostics.'}
            self.last_run = time.monotonic()
            version = ['-6'] if target.version == 6 and key != 'dns' else []
            # Do not pass connector credentials to diagnostic child processes.
            result = subprocess.run([executable, *version, *args, str(target)], shell=False,
                                    capture_output=True, timeout=35, stdin=subprocess.DEVNULL,
                                    env={'PATH': os.defpath, 'LANG': 'C'})
            output = (result.stdout + result.stderr)[:16384].decode('utf-8', errors='replace')
            return 200, {'simulated': False, 'tool': key, 'target': str(target),
                         'exit_code': result.returncode, 'output': output or 'No output returned.'}
        except subprocess.TimeoutExpired:
            return 504, {'error': 'Diagnostic timed out after 35 seconds.'}
        except OSError:
            return 503, {'error': 'Diagnostic could not run. Check the installed tool and container permissions.'}
        finally:
            self.lock.release()
