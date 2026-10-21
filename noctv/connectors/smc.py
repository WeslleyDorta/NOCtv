"""Read-only Forcepoint SMC 7.2 client. Credentials never leave the server."""
import http.cookiejar
import json
import ipaddress
import math
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

INTERVAL = 60


def now():
    return datetime.now(timezone.utc).isoformat()


class APIError(Exception):
    pass


class AuthError(APIError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, config, ca_file):
        self.base = config['url'].rstrip('/')
        origin = urllib.parse.urlsplit(self.base)
        if origin.scheme != 'https' or origin.username or origin.password or origin.query or origin.fragment:
            raise APIError('invalid_config')
        self.origin = (origin.scheme, origin.netloc)
        self.config = config
        self.authorization = None
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def safe_url(self, href):
        url = urllib.parse.urljoin(self.base, href)
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme, parsed.netloc) != self.origin or parsed.username or parsed.fragment:
            raise APIError('untrusted_resource')
        return url

    def request(self, href, method='GET', data=None):
        url = self.safe_url(href)
        path = urllib.parse.urlsplit(url).path
        if method != 'GET' and (method, path) not in {
            ('POST', '/7.2/login'), ('POST', '/7.2/monitoring_status'), ('PUT', '/7.2/logout')
        }:
            raise APIError('write_not_allowed')
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json; charset=utf-8'}
        if self.authorization:
            headers['Authorization'] = self.authorization
        body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data is not None else None
        req = urllib.request.Request(url, body, headers, method=method)
        try:
            with self.opener.open(req, timeout=12) as response:
                if response.headers.get('Authorization'):
                    self.authorization = response.headers['Authorization']
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise APIError('response_too_large')
                value = json.loads(raw) if raw else {}
                if not isinstance(value, (dict, list)):
                    raise APIError('invalid_response')
                return value
        except urllib.error.HTTPError as error:
            error.close()
            if error.code in (401, 403):
                raise AuthError('authentication_rejected') from None
            raise APIError('http_' + str(error.code)) from None
        except (OSError, ValueError, urllib.error.URLError):
            raise APIError('connection_or_response_error') from None


def relations(obj):
    return {x['rel']: x['href'] for x in obj.get('link', []) if isinstance(x, dict) and 'rel' in x and 'href' in x}


def items(obj):
    value = obj if isinstance(obj, list) else obj.get('result', [])
    if not isinstance(value, list):
        raise APIError('invalid_collection')
    return value


def pick(obj, keys):
    return {k: obj[k] for k in keys if isinstance(obj.get(k), (str, int, float, bool))}


def state(obj):
    if obj.get('monitoring_state') != 'READY':
        return 'unknown'
    vpn = obj.get('vpn_status_code')
    if vpn in ('FAILED', 'OFFLINE'):
        return 'down'
    if vpn in ('IDLE', 'STANDBY'):
        return 'standby'
    if vpn == 'PARTIALLY_FAILED':
        return 'attention'
    if vpn is not None and vpn != 'ONLINE':
        return 'unknown'
    return {'OK': 'up', 'ERROR': 'down', 'WARNING': 'attention',
            'PARTIAL_OK': 'attention', 'IDLE': 'standby'}.get(obj.get('monitoring_status'), 'unknown')


def metrics(obj):
    result = {}
    for source, target, divisor in [
        ('health_in_percent', 'health_percent', 1), ('latency_in_ms', 'latency_ms', 1),
        ('jitter_in_ms', 'jitter_ms', 1), ('packet_loss_in_permyriad', 'loss_percent', 100),
        ('traffic_in_bits_per_sec', 'traffic_bps', 1), ('connection_count', 'connections', 1),
        ('inbound_traffic_in_bits_per_sec', 'rx_bps', 1),
        ('outbound_traffic_in_bits_per_sec', 'tx_bps', 1),
    ]:
        value = obj.get(source)
        if type(value) in (int, float) and math.isfinite(value) and value >= 0:
            result[target] = value / divisor
    return result


def appliance(obj):
    interfaces = obj.get('interface_statuses', {}).get('interface_status', [])
    hardware = obj.get('hardware_statuses', {}).get('hardware_statuses', [])
    return {
        'interfaces': [pick(x, ['interface_id', 'name', 'status', 'speed_duplex', 'mtu']) for x in interfaces],
        'hardware': [{**pick(group, ['name', 'status']), 'items': [
            {**pick(item, ['name', 'status', 'value']), 'metrics': [
                pick(m, ['param', 'value']) for m in item.get('statuses', [])]}
            for item in group.get('items', [])]} for group in hardware],
    }


def ip(value):
    if not isinstance(value, str):
        return None
    try:
        address = ipaddress.ip_address(value)
        return str(address) if not address.is_unspecified and not address.is_multicast else None
    except (ValueError, TypeError):
        return None


def network_details(engine, routing):
    addresses, uplinks, networks = [], [], {}

    def routes(node, interface_id=None):
        interface_id = node.get('nic_id', interface_id)
        if node.get('level') == 'network':
            network_name = node.get('name', '')
            networks[(interface_id, node.get('ip'))] = network_name
        if node.get('level') == 'gateway' and any(x.get('ip') in ('0.0.0.0/0', '::/0') for x in node.get('routing_node', [])):
            uplinks.append({**pick(node, ['name']), 'id': urllib.parse.urlsplit(node.get('href', '')).path,
                            'interface_id': interface_id, 'gateway_ip': ip(node.get('ip')),
                            'kind': node.get('related_element_type')})
        for child in node.get('routing_node', []):
            routes(child, interface_id)

    routes(routing)

    def interfaces(interface):
        for wrapper in interface.get('interfaces', []):
            for kind in ('single_node_interface', 'node_interface', 'cluster_virtual_interface'):
                item = wrapper.get(kind, {})
                address = ip(item.get('address'))
                if not address:
                    continue
                iid = str(item.get('nicid', interface.get('interface_id', '')))
                addresses.append({'address': address, 'interface_id': iid,
                    'primary_mgt': item.get('primary_mgt') is True,
                    'network_name': networks.get((iid, item.get('network_value')), '')})
        for vlan in interface.get('vlanInterfaces', []):
            interfaces(vlan.get('vlan_interface', vlan))

    for wrapper in engine.get('physicalInterfaces', []):
        for kind in ('physical_interface', 'switch_interface', 'modem_interface', 'wireless_interface'):
            if kind in wrapper:
                interfaces(wrapper[kind])
    for uplink in uplinks:
        uplink['addresses'] = [a['address'] for a in addresses if a['interface_id'] == uplink['interface_id']]
    # A router and a monitored netlink can represent the same default gateway.
    uplinks = [u for u in uplinks if u['kind'] == 'netlink' or not any(
        n['kind'] == 'netlink' and (n['interface_id'], n['gateway_ip']) == (u['interface_id'], u['gateway_ip']) for n in uplinks)]
    return {'addresses': addresses, 'uplinks': uplinks}


def collect(client):
    started = now()
    output = {'schema_version': 1, 'generated_at': started, 'interval_seconds': INTERVAL,
              'collection_status': 'ok', 'firewalls': [], 'connections': [], 'errors': []}
    logged = False
    try:
        client.request('/7.2/login', 'POST', {'authenticationkey': client.config['authenticationkey'],
                                             'domain': client.config.get('domain', '')})
        logged = True
        inventory = []
        for kind in ('single_fw', 'fw_cluster', 'virtual_fw'):
            inventory.extend(items(client.request('/7.2/elements/' + kind)))
        include = client.config.get('include_names', [])
        inventory = [x for x in inventory if not include or x.get('name') in include]
        branch_refs, connections = {}, {}
        for item in inventory:
            firewall = {'id': urllib.parse.urlsplit(item['href']).path, 'name': item['name'],
                        'site': client.config.get('site_map', {}).get(item['name'], 'unassigned'), 'checked_at': now(), 'state': 'unknown',
                        'nodes': [], 'netlinks': [], 'sdwan_state': 'unknown'}
            output['firewalls'].append(firewall)
            try:
                obj = client.request(item['href'])
                routing_ref = relations(obj).get('routing')
                try:
                    firewall.update(network_details(obj, client.request(routing_ref) if routing_ref else {}))
                except AuthError:
                    raise
                except (APIError, KeyError, TypeError, ValueError):
                    firewall['address_error'] = 'incomplete_read'
                monitor = client.request('/7.2/monitoring_status', 'POST', {'value': client.safe_url(item['href'])})
                firewall.update(state=state(monitor), **pick(monitor, ['monitoring_state', 'monitoring_status']))
                for node in items(client.request(relations(obj)['nodes'])):
                    node_obj = client.request(node['href'])
                    refs = relations(node_obj)
                    health = client.request(refs['status'])
                    info = client.request(refs['appliance_status'])
                    firewall['nodes'].append({'name': node_obj.get('name', ''), 'state': state(health),
                        **pick(health, ['version', 'platform', 'engine_node_status', 'configuration_status',
                                        'connectivity_status', 'last_upload_time']), **appliance(info)})
                for child in monitor.get('child', []):
                    if child.get('type') != 'sdwan_branch_status':
                        continue
                    branch = client.request(child['href'])
                    branch_refs[client.safe_url(child['href'])] = firewall['id']
                    firewall['sdwan_state'] = state(branch)
                    for link in branch.get('child', []):
                        href = client.safe_url(link['href'])
                        if href not in connections:
                            connections[href] = client.request(href)
                        data = connections[href]
                        if 'netlink_status_code' in data:
                            candidates = [u for u in firewall.get('uplinks', []) if u['kind'] == 'netlink' and u.get('name') == data.get('name')]
                            # Names are matched only within this engine and only when unambiguous.
                            addressing = pick(candidates[0], ['interface_id', 'gateway_ip']) if len(candidates) == 1 else {}
                            if len(candidates) == 1:
                                addressing['addresses'] = candidates[0]['addresses']
                            firewall['netlinks'].append({**addressing, 'id': urllib.parse.urlsplit(href).path,
                                **pick(data, ['name', 'monitoring_status', 'netlink_status_code']),
                                'state': state(data), **metrics(data)})
            except AuthError:
                raise
            except (APIError, KeyError, TypeError, ValueError):
                firewall['state'] = 'unknown'
                firewall['error'] = 'incomplete_read'
                output['errors'].append({'target': item['name'], 'code': 'incomplete_read'})
        for href, data in connections.items():
            if 'branchA' not in data or 'branchB' not in data:
                continue
            a, b = (branch_refs.get(client.safe_url(data[key])) for key in ('branchA', 'branchB'))
            output['connections'].append({'id': urllib.parse.urlsplit(href).path,
                **pick(data, ['name', 'monitoring_status', 'vpn_status_code']),
                'from_id': a, 'to_id': b, 'managed_pair': bool(a and b),
                'state': state(data), **metrics(data)})
        if not inventory:
            output['errors'].append({'target': 'Inventário', 'code': 'empty_inventory'})
        if output['errors']:
            output['collection_status'] = 'partial'
        return output
    finally:
        if logged:
            try:
                client.request('/7.2/logout', 'PUT')
            except APIError:
                pass
