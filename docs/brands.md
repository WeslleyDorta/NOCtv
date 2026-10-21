# Device brands and logo attribution

`noctv.brands.identify(device)` returns a stable brand ID or `None`. It reads
`vendor` and `manufacturer` first, then an exact `os` identifier, then distinctive
text in `model` (or `hardware` when `model` is absent). Values are case insensitive.
Manufacturer aliases match whole normalized values; corporate suffixes such as
Inc. and Ltd. are ignored. Conflicting manufacturers or multiple brands in a model
return `None`. An explicit recognized manufacturer takes precedence over model/OS.
Hostnames, display names, IP addresses, descriptions and arbitrary substrings are
never brand evidence. No upstream text becomes an asset path.

`catalog()` returns a fresh mapping of IDs to `{name, logo}`. `logo` is a local
`/brands/<file>.svg` URL or `None`. The frontend should show its generic device
icon when either the brand or its logo is absent, while retaining a recognized
brand's name. The catalog can also validate explicit per-device configuration
overrides: accept only a catalog ID, with `null` selecting the generic icon.
Connectors remain responsible for mapping inventory manufacturer/model/OS fields;
the detector performs no network access.

Examples:

```python
identify({'vendor': 'Cisco Systems, Inc.'})  # 'cisco'
identify({'os': 'arubaos-cx'})               # 'aruba'
identify({'model': 'LaserJet M404dn'})       # 'hp'
identify({'name': 'hp-printer'})            # None
identify({'model': 'R750'})                 # None (not enough evidence)
catalog()['aruba']                         # {'name': 'Aruba', 'logo': None}
```

The OS mappings use names from [LibreNMS OS detection definitions](https://github.com/librenms/librenms/tree/master/resources/definitions/os_detection).
Comware and FastIron alone deliberately do not select a manufacturer because
those families appear under different manufacturers. Bare model codes such as
AP-515, R750, EAP245 or PA-440 are also insufficient; inventory vendor or an explicit
override resolves them. pfSense and OPNsense identify the software platform,
not the physical appliance manufacturer.

## Bundled assets

The 13 SVGs below are byte-for-byte copies from [Simple Icons](https://simpleicons.org),
pinned to commit `c71c69e3a27e4436936b831c72643e6513b9f49b`, retrieved on 2026-10-21.
They are monochrome brand marks, not recolored or reconstructed full brand lockups.
The project is distributed under [CC0 1.0 Universal](https://github.com/simple-icons/simple-icons/blob/c71c69e3a27e4436936b831c72643e6513b9f49b/LICENSE.md).
The selected entries have no separate license override in the pinned
[upstream metadata](https://github.com/simple-icons/simple-icons/blob/c71c69e3a27e4436936b831c72643e6513b9f49b/data/simple-icons.json).

CC0 applies to the Simple Icons contribution; it does not grant trademark rights
or imply manufacturer endorsement. Simple Icons' [disclaimer](https://github.com/simple-icons/simple-icons/blob/c71c69e3a27e4436936b831c72643e6513b9f49b/DISCLAIMER.md)
also cautions that its project license is not a guarantee of every underlying
mark's rights. Use these marks to identify monitored equipment and observe the
manufacturer's brand guidelines. NOCtv's own source-code license does not replace
these third-party notices.

Every downloaded SVG was parsed and checked to contain only SVG, title and path
elements, without scripts, event handlers, references or external content. Because
all passed that allowlist, no sanitizing edits were needed. Tests enforce the same
constraints and check that every advertised asset exists.

| Brand | File | Pinned asset | Source recorded by Simple Icons | SHA-256 |
| --- | --- | --- | --- | --- |
| Cisco | `cisco.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/cisco.svg) | [Manufacturer source](https://www.cisco.com) | `005c240c62355768860ad0bb19820033bc840ee390192c7139f8777d78291391` |
| HP | `hp.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/hp.svg) | [Manufacturer source](https://brandcentral.hp.com/us/en/elements/hp-logo.html) | `29c08a63cdea89850876a3840d93096b4125151dbba17a27926a08f9f3b0f788` |
| Ubiquiti | `ubiquiti.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/ubiquiti.svg) | [Manufacturer source](https://www.ui.com) | `7082e9be5c0b167c30c3de6903ec7e497574b845a33415a572d4d1468f40e810` |
| MikroTik | `mikrotik.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/mikrotik.svg) | [Manufacturer source](https://mikrotik.com/aboutus) | `67231d35b2c75d757ae5795da88e632c5bfebd6037ae78d745c05e55f2f1d59d` |
| TP-Link | `tplink.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/tplink.svg) | [Manufacturer source](https://www.tp-link.com) | `953a4ef5b2560a10964b51667469c933314fcfcef35d655245430de0369447e2` |
| Fortinet | `fortinet.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/fortinet.svg) | [Manufacturer source](https://www.fortinet.com) | `5feafff8531436630ccd7d5c2e80819ee74c1820fdba23d98057eebe02553b86` |
| Epson | `epson.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/epson.svg) | [Manufacturer source](https://global.epson.com/IR/library/) | `b3640aedb4de450179552fa4454b9adaa38d95a72844d6e405d9376a4594f259` |
| Kyocera | `kyocera.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/kyocera.svg) | [Manufacturer source](https://uk.kyocera.com) | `cfd39c60083482dc8882f682f14f6938ea99cbcd14a6803c332d42303015c1ed` |
| Palo Alto Networks | `paloaltonetworks.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/paloaltonetworks.svg) | [Manufacturer source](https://www.paloaltonetworks.com) | `47b46a688d2117b938251c0a36568593562a07c221493f9d04bd1e0e536b1456` |
| SonicWall | `sonicwall.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/sonicwall.svg) | [Manufacturer source](https://brandfolder.com/sonicwall/sonicwall-external) | `337c2f42b827b5fe5ef538511ec7ecfc781c801fd59904f578337b60b06eb2d6` |
| Juniper Networks | `junipernetworks.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/junipernetworks.svg) | [Manufacturer source](https://www.juniper.net/us/en/company/press-center/images/image-library/logos/) | `c2a373671adf7f9e610113d0ac7850dcdb280d36960c92094aa64b0567e4050a` |
| pfSense | `pfsense.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/pfsense.svg) | [Manufacturer source](https://www.pfsense.org) | `d27a1c178dfa7f8d1d10a092fb1977396d1ffc219af1f8c82c23a2bdcf28b358` |
| OPNsense | `opnsense.svg` | [SVG](https://raw.githubusercontent.com/simple-icons/simple-icons/c71c69e3a27e4436936b831c72643e6513b9f49b/icons/opnsense.svg) | [Manufacturer source](https://github.com/opnsense/core/blob/f4b69b9b565d2747eb40d7d23e060f4a3c81a071/src/opnsense/www/themes/opnsense/build/images/icon-logo.svg) | `b10d2bdc336f1b66d1bc5db4073904f9aea498a574aef546d4b53b08f3bcb01f` |

## Brands without bundled logos

Aruba, HPE, Ruckus, Extreme Networks, Brother, Canon, Lexmark, Ricoh, Xerox,
Check Point, Sophos and Forcepoint are recognized but have no entry in the pinned
Simple Icons catalog. No alternative SVG with established redistribution terms
was included. Their catalog logo is `null`; do not substitute another company's
mark, including HP for HPE/Aruba. Future additions need a documented asset source,
license, identity check and the same SVG safety check.
