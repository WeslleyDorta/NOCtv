"""Validate local configuration; never send connector secrets to the browser."""
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo
from .geography import validate_map, public_map

KINDS = {'switch', 'firewall', 'router', 'server', 'printer', 'wireless', 'device'}
VIEWS = ['connections', 'switches', 'ports', 'servers', 'printers', 'wireless', 'devices']


def load(path):
    c = json.loads(Path(path).read_text())
    if c.get('mode') not in ('demo', 'live'):
        raise ValueError('mode must be demo or live')
    c.setdefault('title', 'NOCtv')
    c.setdefault('timezone', 'UTC')
    ZoneInfo(c['timezone'])
    c.setdefault('display', {})
    d = c['display']
    for key, default, low, high in [('refresh_seconds', 5, 2, 300), ('rotate_seconds', 25, 5, 600), ('connections_seconds', 45, 5, 600), ('max_cards', 16, 4, 48)]:
        d.setdefault(key, default)
        if type(d[key]) is not int or not low <= d[key] <= high:
            raise ValueError('invalid display setting: ' + key)
    d.setdefault('views', VIEWS.copy())
    if not d['views'] or len(d['views']) != len(set(d['views'])) or any(v not in VIEWS for v in d['views']):
        raise ValueError('invalid display views')
    c.setdefault('sites', [])
    validate_map(c)
    seen = set()
    for site in c['sites']:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', site['id']) or site['id'] in seen:
            raise ValueError('site ids must be unique and URL safe')
        seen.add(site['id'])
        if not isinstance(site.get('name'), str) or not site['name'].strip():
            raise ValueError('site name is required')
        for axis in (('x', 'y') if c['map']['mode'] == 'schematic' else ()):
            if type(site.get(axis)) not in (int, float) or not 10 <= site[axis] <= 90:
                raise ValueError('site x/y must be percentages between 10 and 90')
    c.setdefault('connectors', [])
    seen = set()
    for source in c['connectors']:
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', source['id']) or source['id'] in seen:
            raise ValueError('connector ids must be unique')
        seen.add(source['id'])
        if source['type'] not in ('librenms', 'forcepoint', 'zabbix', 'fortigate', 'panos', 'checkpoint', 'sophos_central', 'prometheus', 'netbox'):
            raise ValueError('unsupported connector type')
        for key, default in [('interval_seconds', 60), ('max_age_seconds', 600)]:
            source.setdefault(key, default)
            if type(source[key]) is not int or not 10 <= source[key] <= 86400:
                raise ValueError('invalid connector period')
        source.setdefault('site_map', {})
        if any(s not in {x['id'] for x in c['sites']} for s in source['site_map'].values()):
            raise ValueError('site_map references an unknown site')
        for override in source.get('devices', {}).values():
            if override.get('type', 'device') not in KINDS:
                raise ValueError('unknown device type')
            if 'site' in override and override['site'] not in {x['id'] for x in c['sites']}:
                raise ValueError('device references an unknown site')
    if c['mode'] == 'live' and not c['connectors']:
        raise ValueError('live mode needs at least one connector')
    return c


def public(c):
    return {'title': c['title'], 'mode': c['mode'], 'timezone': c['timezone'], 'map': public_map(c),
            'display': {k: c['display'][k] for k in ('refresh_seconds', 'rotate_seconds', 'connections_seconds', 'max_cards', 'views')},
            'sites': [{k: s[k] for k in ('id', 'name', 'city', 'kind', 'x', 'y') if k in s} for s in c['sites']]}
