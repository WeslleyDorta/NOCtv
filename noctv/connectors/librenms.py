"""LibreNMS API v0; all operations are GET, independent of vendor and database."""
import os
from urllib.parse import urlencode
from .http import JSONClient, SourceError
from ..model import number, timestamp, web_url

PORT_COLUMNS = 'port_id,device_id,ifIndex,ifName,ifAlias,ifType,ifSpeed,ifOperStatus,ifAdminStatus,ifInOctets_rate,ifOutOctets_rate,poll_time,deleted,disabled'


def collection(payload, key):
    if not isinstance(payload, dict) or payload.get('status') != 'ok' or not isinstance(payload.get(key), list):
        raise SourceError('invalid_' + key + '_response')
    return payload[key]


class LibreNMS:
    def __init__(self, config):
        self.config = config
        token = os.environ.get(config.get('token_env', 'LIBRENMS_TOKEN'))
        url = os.environ.get(config.get('url_env', 'LIBRENMS_URL'))
        if not token or not url:
            raise SourceError('missing_credentials')
        self.client = JSONClient(url, {'X-Auth-Token': token}, config.get('ca_file'), config.get('allow_http') is True)

    def collect(self):
        raw_devices = collection(self.client.get('devices'), 'devices')
        warnings = []
        optional = {}
        for key, route in [('ports', 'ports?' + urlencode({'columns': PORT_COLUMNS})), ('links', 'resources/links')]:
            try:
                optional[key] = collection(self.client.get(route), key)
            except SourceError as error:
                if str(error) in ('http_401', 'http_403'):
                    raise
                optional[key] = []
                warnings.append(key + ':' + str(error))
        return self.normalize(raw_devices, optional['ports'], optional['links'], warnings)

    def normalize(self, rows, ports, links, warnings=None):
        c, devices = self.config, {}
        source = c['id']
        zone = c.get('upstream_timezone', 'UTC')
        for row in rows:
            if str(row.get('disabled', '0')) == '1' or str(row.get('ignore', '0')) == '1':
                continue
            native = str(row['device_id'])
            override = c.get('devices', {}).get(native, {})
            kind = {'network': 'switch', 'server': 'server', 'printer': 'printer', 'firewall': 'firewall', 'wireless': 'wireless'}.get(row.get('type'), 'device')
            location = row.get('location')
            if isinstance(location, dict):
                location = location.get('location', '')
            site = override.get('site', c.get('site_map', {}).get(str(location), 'unassigned'))
            state = {'1': 'up', '0': 'down'}.get(str(row.get('status')), 'unknown')
            devices[native] = {'id': source + ':' + native, 'name': override.get('name') or row.get('display') or row.get('sysName') or row.get('hostname') or native,
                'ip': row.get('ip') or row.get('hostname', ''), 'model': row.get('hardware') or row.get('os', ''),
                'vendor': override.get('vendor', row.get('vendor', '')), 'os': row.get('os', ''), 'brand': override.get('brand'),
                'type': override.get('type', kind), 'site': site, 'state': state,
                'observed_at': timestamp(row.get('last_polled'), zone),
                'discovered_at': timestamp(row.get('last_discovered'), zone),
                'web_url': web_url(override.get('web_url')), 'root': override.get('root') is True,
                'metrics': {'latency_ms': number(row.get('last_ping_timetaken')), 'uptime_seconds': number(row.get('uptime'))}, 'ports': []}
        port_map = {}
        for row in ports:
            native = str(row.get('device_id'))
            if native not in devices or str(row.get('deleted', '0')) == '1':
                continue
            name = row.get('ifName') or str(row.get('ifIndex', row['port_id']))
            state = 'disabled' if row.get('ifAdminStatus') == 'down' else row.get('ifOperStatus')
            state = state if state in ('up', 'down', 'disabled') else 'unknown'
            rates = [number(row.get('ifInOctets_rate')), number(row.get('ifOutOctets_rate'))]
            port = {'id': str(row['port_id']), 'name': name, 'description': row.get('ifAlias', ''),
                'state': state, 'admin_state': row.get('ifAdminStatus', 'unknown'),
                'observed_at': timestamp(row.get('poll_time'), zone),
                'speed_mbps': (number(row.get('ifSpeed')) / 1e6) if number(row.get('ifSpeed')) is not None else None,
                'rx_bps': number(rates[0] * 8) if rates[0] is not None else None, 'tx_bps': number(rates[1] * 8) if rates[1] is not None else None,
                'required': name in c.get('devices', {}).get(native, {}).get('required_ports', []), 'neighbors': []}
            devices[native]['ports'].append(port)
            port_map[port['id']] = port
        edges, seen = [], set()
        for row in links:
            a, b = str(row.get('local_device_id')), str(row.get('remote_device_id'))
            if a not in devices or b not in devices or str(row.get('active', 1)) == '0' or a == b:
                continue
            pa, pb = str(row.get('local_port_id', '')), str(row.get('remote_port_id', ''))
            key = tuple(sorted(((a, pa), (b, pb))))
            if key in seen:
                continue
            seen.add(key)
            for pid, remote in [(pa, b), (pb, a)]:
                if pid in port_map:
                    port_map[pid]['neighbors'].append({'id': devices[remote]['id'], 'name': devices[remote]['name'], 'ip': devices[remote]['ip'], 'evidence': row.get('protocol', 'discovery')})
            states = [port_map.get(p, {}).get('state', 'unknown') for p in (pa, pb)]
            state = 'down' if 'down' in states else 'up' if all(x == 'up' for x in states) else 'unknown'
            discovered = [devices[x]['discovered_at'] for x in (a, b)]
            edges.append({'id': source + ':link:' + str(row['id']), 'a': devices[a]['id'], 'b': devices[b]['id'], 'a_port': pa, 'b_port': pb,
                'state': state, 'kind': 'lan', 'evidence': str(row.get('protocol', 'discovery')).upper(),
                'observed_at': min(discovered) if all(discovered) else None,
                'max_age_seconds': c.get('discovery_max_age_seconds', 25200)})
        return {'devices': list(devices.values()), 'links': edges, 'warnings': warnings or []}
