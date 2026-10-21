"""Conservative manufacturer identification; never infer a brand from a hostname."""
import re


# Logo filenames identify unmodified Simple Icons assets; provenance is in docs/brands.md.
_BRANDS = {
    'cisco': ('Cisco', 'cisco', ('cisco', 'cisco systems')),
    'aruba': ('Aruba', None, ('aruba', 'aruba networks', 'hpe aruba', 'hpe aruba networking')),
    'hpe': ('HPE', None, ('hpe', 'hewlett packard enterprise')),
    'hp': ('HP', 'hp', ('hp', 'hewlett packard')),
    'ubiquiti': ('Ubiquiti', 'ubiquiti', ('ubiquiti', 'ubiquiti networks')),
    'mikrotik': ('MikroTik', 'mikrotik', ('mikrotik', 'mikrotikls', 'sia mikrotikls')),
    'ruckus': ('Ruckus', None, ('ruckus', 'ruckus wireless', 'ruckus networks')),
    'tplink': ('TP-Link', 'tplink', ('tp link', 'tp link technologies', 'tplink')),
    'fortinet': ('Fortinet', 'fortinet', ('fortinet',)),
    'extreme': ('Extreme Networks', None, ('extreme networks',)),
    'brother': ('Brother', None, ('brother', 'brother industries')),
    'canon': ('Canon', None, ('canon',)),
    'epson': ('Epson', 'epson', ('epson', 'seiko epson')),
    'kyocera': ('Kyocera', 'kyocera', ('kyocera', 'kyocera document solutions', 'kyocera mita')),
    'lexmark': ('Lexmark', None, ('lexmark', 'lexmark international')),
    'ricoh': ('Ricoh', None, ('ricoh',)),
    'xerox': ('Xerox', None, ('xerox',)),
    'paloalto': ('Palo Alto Networks', 'paloaltonetworks', ('palo alto networks',)),
    'checkpoint': ('Check Point', None, ('check point', 'check point software technologies')),
    'sophos': ('Sophos', None, ('sophos',)),
    'forcepoint': ('Forcepoint', None, ('forcepoint', 'stonesoft')),
    'sonicwall': ('SonicWall', 'sonicwall', ('sonicwall', 'dell sonicwall')),
    'juniper': ('Juniper Networks', 'junipernetworks', ('juniper', 'juniper networks')),
    'pfsense': ('pfSense', 'pfsense', ('pfsense',)),
    'opnsense': ('OPNsense', 'opnsense', ('opnsense',)),
}

_OS = {
    'ios': 'cisco', 'iosxe': 'cisco', 'iosxr': 'cisco', 'nxos': 'cisco', 'asa': 'cisco',
    'arubaos': 'aruba', 'aruba-instant': 'aruba', 'arubaos-cx': 'aruba',
    'procurve': 'hpe', 'routeros': 'mikrotik',
    'unifi': 'ubiquiti', 'edgeswitch': 'ubiquiti',
    'ruckuswireless': 'ruckus', 'ruckuswireless-sz': 'ruckus',
    'ruckuswireless-unleashed': 'ruckus', 'tplink': 'tplink',
    'fortigate': 'fortinet', 'fortios': 'fortinet', 'fortiswitch': 'fortinet',
    'extremeware': 'extreme', 'exos': 'extreme', 'panos': 'paloalto',
    'junos': 'juniper', 'sonicwall': 'sonicwall', 'sophos': 'sophos',
    'sophos-xg': 'sophos', 'forcepoint': 'forcepoint', 'forcepoint-fe': 'forcepoint',
    'brother': 'brother', 'canonprinter': 'canon', 'epson': 'epson', 'kyocera': 'kyocera',
    'lexmarkprinter': 'lexmark', 'ricoh': 'ricoh', 'xerox': 'xerox',
    'pfsense': 'pfsense', 'opnsense': 'opnsense',
}

_MODELS = {
    'cisco': r'cisco|catalyst', 'aruba': r'aruba', 'hpe': r'hpe|hewlett[ -]packard enterprise',
    'hp': r'hp|laserjet|officejet|pagewide', 'ubiquiti': r'ubiquiti|unifi|edgerouter',
    'mikrotik': r'mikrotik|routerboard', 'ruckus': r'ruckus', 'tplink': r'tp[ -]?link|omada',
    'fortinet': r'fortinet|fortigate|fortiswitch|fortiap', 'extreme': r'extreme networks',
    'brother': r'brother', 'canon': r'canon', 'epson': r'epson', 'kyocera': r'kyocera|ecosys',
    'lexmark': r'lexmark', 'ricoh': r'ricoh', 'xerox': r'xerox|versalink|altalink',
    'paloalto': r'palo alto networks', 'checkpoint': r'check point', 'sophos': r'sophos',
    'forcepoint': r'forcepoint|stonesoft', 'sonicwall': r'sonicwall', 'juniper': r'juniper',
    'pfsense': r'pfsense', 'opnsense': r'opnsense',
}
_MODELS = {brand: re.compile(r'(?<!\w)(?:' + pattern + r')(?!\w)', re.I)
           for brand, pattern in _MODELS.items()}


def catalog():
    """Return JSON-safe brand names and local logo URLs (None means generic icon)."""
    return {brand: {'name': name, 'logo': '/brands/' + logo + '.svg' if logo else None}
            for brand, (name, logo, _) in _BRANDS.items()}


def _vendor(value):
    if not isinstance(value, str):
        return None
    value = re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()
    value = re.sub(r'(?: (?:inc|corporation|corp|co|ltd|limited|llc|company))+$', '', value)
    return next((brand for brand, (_, _, aliases) in _BRANDS.items() if value in aliases), None)


def identify(device):
    """Use explicit vendor/manufacturer, then exact OS, then distinctive model text.

    Ambiguous evidence at a given priority returns None. Unknown fields are ignored.
    Caller applies validated configuration overrides before/after this function.
    """
    vendors = {_vendor(device.get(key)) for key in ('vendor', 'manufacturer')} - {None}
    if vendors:
        return next(iter(vendors)) if len(vendors) == 1 else None
    os = device.get('os')
    if isinstance(os, str) and os.strip().lower() in _OS:
        return _OS[os.strip().lower()]
    model = device.get('model', device.get('hardware'))
    if not isinstance(model, str):
        return None
    matches = {brand for brand, pattern in _MODELS.items() if pattern.search(model)}
    return next(iter(matches)) if len(matches) == 1 else None
