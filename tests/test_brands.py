import unittest
from pathlib import Path
from xml.etree import ElementTree

from noctv.brands import catalog, identify


class BrandsTest(unittest.TestCase):
    def test_explicit_manufacturer_aliases(self):
        cases = {'Cisco Systems, Inc.': 'cisco', 'Aruba Networks': 'aruba',
                 'Hewlett Packard Enterprise': 'hpe', 'Hewlett-Packard': 'hp',
                 'HP Inc.': 'hp', 'Ubiquiti Inc.': 'ubiquiti', 'MikroTik': 'mikrotik',
                 'Ruckus Wireless': 'ruckus', 'TP-LINK Technologies Co., Ltd.': 'tplink',
                 'Fortinet, Inc.': 'fortinet', 'Extreme Networks': 'extreme',
                 'Brother Industries, Ltd.': 'brother', 'Canon Inc.': 'canon',
                 'Seiko Epson Corporation': 'epson', 'Kyocera Document Solutions': 'kyocera',
                 'Lexmark International, Inc.': 'lexmark', 'Ricoh Company, Ltd.': 'ricoh',
                 'Xerox Corporation': 'xerox', 'Palo Alto Networks': 'paloalto',
                 'Check Point Software Technologies Ltd.': 'checkpoint',
                 'Sophos Ltd.': 'sophos', 'Forcepoint': 'forcepoint',
                 'SonicWall Inc.': 'sonicwall', 'Juniper Networks, Inc.': 'juniper'}
        for manufacturer, expected in cases.items():
            with self.subTest(manufacturer=manufacturer):
                self.assertEqual(identify({'manufacturer': manufacturer}), expected)

    def test_distinctive_models_and_operating_systems(self):
        for model, expected in [('Cisco Catalyst 9300', 'cisco'), ('Aruba AP-515', 'aruba'),
                                ('UniFi U6 Pro', 'ubiquiti'), ('FortiGate 100F', 'fortinet'),
                                ('LaserJet M404dn', 'hp'), ('ECOSYS M5526cdw', 'kyocera'),
                                ('Brother HL-L2350DW', 'brother'), ('Canon iR-ADV C3530', 'canon'),
                                ('EPSON WF-C5790', 'epson'), ('Ricoh IM C3000', 'ricoh'),
                                ('Xerox VersaLink C405', 'xerox'), ('Lexmark MS521dn', 'lexmark'),
                                ('MikroTik CCR2004-16G-2S+', 'mikrotik'), ('Ruckus R750', 'ruckus'),
                                ('TP-Link EAP245', 'tplink'), ('Extreme Networks X440', 'extreme')]:
            with self.subTest(model=model):
                self.assertEqual(identify({'model': model}), expected)
        for os, expected in [('junos', 'juniper'), ('routeros', 'mikrotik'),
                             ('fortigate', 'fortinet'), ('panos', 'paloalto'),
                             ('arubaos', 'aruba'), ('procurve', 'hpe'), ('iosxe', 'cisco'),
                             ('arubaos-cx', 'aruba'), ('canonprinter', 'canon'),
                             ('lexmarkprinter', 'lexmark'), ('brother', 'brother'),
                             ('forcepoint', 'forcepoint'), ('sophos-xg', 'sophos'),
                             ('pfsense', 'pfsense'), ('opnsense', 'opnsense')]:
            with self.subTest(os=os):
                self.assertEqual(identify({'os': os}), expected)

    def test_uncertain_or_conflicting_evidence_stays_generic(self):
        for device in [{}, {'name': 'hp-cisco-printer'}, {'model': 'R750'},
                       {'model': 'AP-515'}, {'model': 'PA-440'}, {'model': 'EAP245'},
                       {'model': 'Canonical Ubuntu'}, {'model': 'brotherhood gateway'},
                       {'model': 'hpnic'}, {'model': 'HP and Cisco'},
                       {'vendor': 'Acme Cisco-compatible'}, {'os': 'not-ios'},
                       {'os': 'comware'}, {'os': 'fastiron'},
                       {'vendor': 'Cisco', 'manufacturer': 'HP'},
                       {'vendor': [], 'model': None, 'os': {'name': 'ios'}}]:
            with self.subTest(device=device):
                self.assertIsNone(identify(device))

    def test_vendor_is_authoritative_and_catalog_is_independent(self):
        self.assertEqual(identify({'vendor': 'Cisco', 'model': 'HP'}), 'cisco')
        changed = catalog()
        changed['cisco']['name'] = 'Changed'
        self.assertEqual(catalog()['cisco']['name'], 'Cisco')

    def test_all_advertised_logos_exist_and_contain_only_safe_svg(self):
        root = Path(__file__).resolve().parents[1] / 'web'
        logos = [item['logo'] for item in catalog().values() if item['logo']]
        self.assertGreaterEqual(len(logos), 10)
        for logo in logos:
            with self.subTest(logo=logo):
                path = root / logo.lstrip('/')
                self.assertTrue(path.is_file())
                svg = ElementTree.parse(path).getroot()
                self.assertEqual(svg.tag, '{http://www.w3.org/2000/svg}svg')
                for element in svg.iter():
                    self.assertIn(element.tag.rsplit('}', 1)[-1], {'svg', 'title', 'path'})
                    for attr, value in element.attrib.items():
                        self.assertFalse(attr.lower().startswith('on'))
                        self.assertNotIn('href', attr.lower())
                        self.assertNotIn('url(', value.lower())


if __name__ == '__main__':
    unittest.main()
