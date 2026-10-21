"""Rebuild bundled outlines from the pinned, public-domain Natural Earth source."""
import hashlib
import json
import re
import urllib.request
from pathlib import Path

URL = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/ne_50m_admin_0_countries.geojson'
SHA256 = '3e458fc036ad0a66411f2c1e6cac49c5d7bfb81cb1123bc513b22511a2b7fdeb'


def main():
    with urllib.request.urlopen(URL, timeout=30) as response:
        raw = response.read(5_000_001)
    if hashlib.sha256(raw).hexdigest() != SHA256:
        raise ValueError('Natural Earth source differs from the reviewed version')
    countries = {}
    for feature in json.loads(raw)['features']:
        props, geometry = feature['properties'], feature['geometry']
        code = props['ISO_A2_EH'] if re.fullmatch('[A-Z]{2}', props['ISO_A2_EH']) else props['ADM0_A3']
        item = countries.setdefault(code, {'name': props['ADMIN'], 'polygons': []})
        if props['ISO_A2'] == code:
            item['name'] = props['ADMIN']
        polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        item['polygons'].extend([[[[round(x, 3), round(y, 3)] for x, y in ring] for ring in polygon] for polygon in polygons])
    target = Path(__file__).resolve().parent.parent / 'noctv/data/countries.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(countries, separators=(',', ':'), ensure_ascii=False) + '\n')
    print(f'Wrote {len(countries)} country/territory entries to {target.name}')


if __name__ == '__main__':
    main()
