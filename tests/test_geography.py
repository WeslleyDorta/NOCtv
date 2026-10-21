import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from noctv.config import load, public
from noctv.geography import base_map, countries


class GeographyTests(unittest.TestCase):
    def load_value(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(value))
            return load(path)

    def test_old_schematic_configuration_is_unchanged(self):
        config = load('config/demo.json')
        self.assertEqual(public(config)['map'], {'mode': 'schematic'})
        self.assertEqual(public(config)['sites'][0]['x'], 28)

    def test_country_and_world_positions_share_outline_projection(self):
        config = load('config/map-country.example.json')
        mapped = public(config)['map']
        self.assertEqual(len(mapped['positions']), 4)
        self.assertEqual([o['id'] for o in mapped['outlines']], ['BR'])
        for point in mapped['positions'].values():
            left, top, right, bottom = mapped['bounds']
            self.assertTrue(left <= point['x'] <= right and top <= point['y'] <= bottom)
        config = load('config/map-world.example.json')
        mapped = public(config)['map']
        self.assertEqual(len(mapped['positions']), 4)
        self.assertLess(mapped['positions']['hq']['x'], mapped['positions']['east']['x'])
        self.assertLess(mapped['positions']['north']['y'], mapped['positions']['cloud']['y'])

    def test_missing_coordinates_or_other_country_are_not_guessed(self):
        config = load('config/map-country.example.json')
        config['sites'][0].pop('latitude')
        config['sites'][1]['country'] = 'US'
        mapped = public(config)['map']
        self.assertNotIn('hq', mapped['positions'])
        self.assertNotIn('north', mapped['positions'])
        self.assertEqual(len(mapped['positions']), 2)

    def test_private_fields_never_enter_public_map(self):
        config = load('config/map-country.example.json')
        config['map']['token'] = 'secret-map-value'
        config['sites'][0]['private'] = 'secret-site-value'
        self.assertNotIn('secret-', json.dumps(public(config)))

    def test_reject_unknown_map_invalid_coordinates_and_bounds(self):
        base = load('config/map-country.example.json')
        changes = [lambda c: c.update(map={'mode': 'tiles'}),
                   lambda c: c['map'].update(country='../../secret'),
                   lambda c: c['map'].update(bounds=[20, 0, 10, 30]),
                   lambda c: c['map'].update(bounds=[-180, -91, 180, 90]),
                   lambda c: c['sites'][0].update(latitude=float('nan')),
                   lambda c: c['sites'][0].update(longitude=True),
                   lambda c: c['sites'][0].pop('longitude'),
                   lambda c: c['sites'][0].update(country='ZZ')]
        for change in changes:
            config = copy.deepcopy(base)
            change(config)
            with self.assertRaises(ValueError):
                self.load_value(config)

    def test_antimeridian_does_not_expand_fiji_to_world_width(self):
        mapped, _ = base_map('country', 'FJ', ())
        self.assertLess(mapped['bounds'][2] - mapped['bounds'][0], 10)
        config = load('config/map-country.example.json')
        config['map']['country'] = 'FJ'
        config['sites'] = [dict(id='fiji', name='Demo', country='FJ', latitude=-16.7, longitude=-179.9)]
        self.assertIn('fiji', public(config)['map']['positions'])

    def test_country_crop_limits_visible_sites(self):
        config = load('config/map-country.example.json')
        config['map']['bounds'] = [-49, -25, -44, -20]
        self.assertEqual(set(public(config)['map']['positions']), {'hq'})

    def test_country_catalog_geometry_is_finite_and_covers_common_regions(self):
        self.assertTrue({'BR', 'PT', 'US', 'GB', 'DE', 'JP', 'ZA', 'AU'} <= countries().keys())
        for code in countries():
            mapped, _ = base_map('country', code, ())
            left, top, right, bottom = mapped['bounds']
            self.assertTrue(all(math.isfinite(n) for n in mapped['bounds']), code)
            self.assertTrue(left < right and top < bottom, code)
            self.assertTrue(mapped['outlines'][0]['path'].startswith('M'), code)

    def test_brazil_regions_follow_sites_without_corporate_defaults(self):
        config = load('config/map-country.example.json')
        regions = public(config)['map']['regions']
        self.assertEqual(len(regions), 27)
        self.assertEqual({r['id'] for r in regions if r['active']}, {'uf-26', 'uf-35', 'uf-43', 'uf-53'})
        config['sites'] = []
        self.assertFalse(any(r['active'] for r in public(config)['map']['regions']))
        config['map']['country'] = 'US'
        self.assertEqual(public(config)['map']['regions'], [])
