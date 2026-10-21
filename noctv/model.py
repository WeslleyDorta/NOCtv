"""The connector contract uses UTC timestamps, explicit unknowns and stable IDs."""
import math
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

STATES = {'up', 'down', 'attention', 'disabled', 'standby', 'unknown'}


def now():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
        return n if math.isfinite(n) and n >= 0 else None
    except (ValueError, TypeError):
        return None


def timestamp(value, zone='UTC'):
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            dt = datetime.fromtimestamp(float(value), timezone.utc)
        else:
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(zone))
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def stale(observed, max_age, clock=None):
    try:
        age = (clock or datetime.now(timezone.utc)).timestamp() - datetime.fromisoformat(observed).timestamp()
        return not -5 <= age < max_age
    except (TypeError, ValueError):
        return True


def web_url(value):
    try:
        u = urlsplit(value or '')
        return value if u.scheme in ('https', 'http') and u.hostname and not u.username and not u.password and not any(ord(c) < 32 for c in value) else None
    except ValueError:
        return None


def validate(batch):
    """Reject broken adapter contracts before replacing the previous snapshot."""
    if not isinstance(batch, dict) or not isinstance(batch.get('devices'), list) or not isinstance(batch.get('links'), list):
        raise ValueError('invalid connector batch')
    json.dumps(batch, allow_nan=False)
    ids = set()
    for device in batch['devices']:
        if not isinstance(device.get('id'), str) or device['id'] in ids or device.get('state') not in STATES:
            raise ValueError('invalid or duplicate device')
        ids.add(device['id'])
        if device.get('type') not in {'switch', 'firewall', 'router', 'server', 'printer', 'wireless', 'device'}:
            raise ValueError('invalid device type')
        if 'hardware' in device and not isinstance(device['hardware'], dict):
            raise ValueError('invalid hardware inventory')
        if 'storage' in device and (not isinstance(device['storage'], list) or any(not isinstance(item, dict) for item in device['storage'])):
            raise ValueError('invalid storage inventory')
        port_ids = set()
        for port in device.get('ports', []):
            if port.get('state') not in STATES or not isinstance(port.get('id'), str) or port['id'] in port_ids:
                raise ValueError('invalid or duplicate port')
            port_ids.add(port['id'])
    link_ids = set()
    for link in batch['links']:
        if link.get('a') not in ids or link.get('b') not in ids or link.get('state') not in STATES or not isinstance(link.get('id'), str) or link['id'] in link_ids:
            raise ValueError('invalid link')
        link_ids.add(link['id'])
