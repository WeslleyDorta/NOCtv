"""Offline country outlines and shared projection for maps and site coordinates."""
import json
import math
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def countries():
    return json.loads((Path(__file__).parent / 'data/countries.json').read_text())


def finite(value, low, high):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate_map(config):
    setting = config.setdefault('map', {'mode': 'schematic'})
    if not isinstance(setting, dict) or setting.get('mode') not in ('schematic', 'country', 'world'):
        raise ValueError('map.mode must be schematic, country or world')
    if setting['mode'] == 'country' and (not isinstance(setting.get('country'), str) or setting['country'] not in countries()):
        raise ValueError('map.country must be a bundled country code; see docs/maps.md')
    if 'bounds' in setting:
        b = setting['bounds']
        if not isinstance(b, list) or len(b) != 4 or not all(finite(v, -180 if i % 2 == 0 else -90, 180 if i % 2 == 0 else 90) for i, v in enumerate(b)) or b[0] >= b[2] or b[1] >= b[3]:
            raise ValueError('map.bounds must be [west, south, east, north] in degrees')
    for site in config.get('sites', []):
        if 'latitude' in site or 'longitude' in site:
            if not finite(site.get('latitude'), -90, 90) or not finite(site.get('longitude'), -180, 180):
                raise ValueError('site latitude/longitude must be a finite coordinate pair')
            if not isinstance(site.get('country'), str) or site['country'] not in countries():
                raise ValueError('geographic sites need a bundled country code')


@lru_cache(maxsize=32)
def base_map(mode, code, crop):
    selected = {code: countries()[code]} if mode == 'country' else countries()
    points = [point for country in selected.values() for polygon in country['polygons'] for ring in polygon for point in ring]
    if crop:
        west, south, east, north = crop
    elif mode == 'world':
        west, south, east, north = -180, -90, 180, 90
    else:
        # Use the smallest longitude arc so Fiji and the Aleutians do not span the world.
        longitudes = sorted({p[0] for p in points})
        gaps = [(longitudes[(i + 1) % len(longitudes)] + (360 if i == len(longitudes) - 1 else 0) - x, i) for i, x in enumerate(longitudes)]
        _, i = max(gaps)
        west = longitudes[(i + 1) % len(longitudes)]
        east = max(west + (p[0] - west) % 360 for p in points)
        south, north = min(p[1] for p in points), max(p[1] for p in points)
    factor = max(.01, math.cos(math.radians((south + north) / 2))) if mode == 'country' else 1
    wrap = mode == 'country' and not crop
    def project(lon, lat):
        return ((west + (lon - west) % 360 if wrap else lon) * factor, -lat)
    outlines = []
    for key, country in selected.items():
        path = []
        for polygon in country['polygons']:
            for ring in polygon:
                xy = [project(*point) for point in ring]
                path.append('M' + 'L'.join(f'{x:.3f},{y:.3f}' for x, y in xy) + 'Z')
        outlines.append({'id': key, 'path': ''.join(path)})
    return {'bounds': [west * factor, -north, east * factor, -south], 'outlines': outlines}, (west, south, east, north, factor, wrap)


def public_map(config):
    setting = config['map']
    mode = setting['mode']
    if mode == 'schematic':
        return {'mode': mode}
    code = setting.get('country') if mode == 'country' else None
    base, projection = base_map(mode, code, tuple(setting.get('bounds', [])))
    west, south, east, north, factor, wrap = projection
    positions = {}
    for site in config['sites']:
        if 'latitude' not in site or (code and site['country'] != code):
            continue
        lon, lat = site['longitude'], site['latitude']
        lon = west + (lon - west) % 360 if wrap else lon
        if west <= lon <= east and south <= lat <= north:
            positions[site['id']] = {'x': lon * factor, 'y': -lat}
    return {**base, 'mode': mode, 'country': code, 'label': countries()[code]['name'] if code else 'World', 'positions': positions}
