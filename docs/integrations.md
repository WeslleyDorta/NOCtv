# Integration coverage

NOCtv consumes monitoring data and optionally runs explicitly configured service
checks. It does not implement every manufacturer's SNMP MIB, replace an SNMP
poller or certify every device with a recognized logo.

| Connector | Tested contract | Inventory | Device availability | Interfaces | Topology | Additional data |
| --- | --- | --- | --- | --- | --- | --- |
| Native probes | Local HTTP/TCP and synthetic DNS/ICMP/TLS tests | Configured targets | Check result | Not applicable | Not applicable | HTTP codes/keyword, TLS expiry, response time |
| Docker | Engine API 1.45 fixtures | Dynamic or expected names | Runtime and healthcheck | Not implemented | Not implemented | Restarts; optional CPU/memory |
| Demo | Synthetic deterministic source | Yes | Simulated | Simulated | Simulated | Sample CPU, memory, toner, clients |
| LibreNMS | API v0 | Yes, dynamic | Upstream device status | State, speed, RX/TX | LLDP/CDP records | Latency and uptime |
| Zabbix | API 7.0 | Yes, dynamic | Fresh ICMP item only | Explicit item mappings | Not implemented | Exact/default and configured metric keys |
| Prometheus | HTTP API v1 | Dynamic selector identities | Explicit binary probe/status metric | Not implemented | Not implemented | Configured gauge metrics, original sample timestamps |
| NetBox | REST API 4.5+, v2 token | Dynamic devices | Not established | Not implemented | Not implemented | Manufacturer, model, primary IP, site mapping |
| Forcepoint | SMC 7.2 | Engine inventory | Explicit SMC status | Reported state | Managed VPN peers | VPN latency/loss/traffic, services |
| FortiGate | REST monitor v2 / FortiOS 7.x | Single appliance | Management only | Not implemented | Not implemented | Model, identity |
| PAN-OS | XML API / PAN-OS 11.x | Single appliance | Management only | Not implemented | Not implemented | Model, identity |
| Check Point | Management API R80+ | Managed inventory | Not established | Not implemented | Not implemented | Gateway identity/address |
| Sophos Central | Firewall API v1 | Tenant inventory | Cloud-management connection only | Not implemented | Not implemented | Model, identity |

API connectors use **synthetic fixtures**; native HTTP/TCP checks also use local test endpoints.
No production credentials or private inventory were used to validate this package.
Firmware-specific payloads and permissions require a controlled installation test.

[Native Services / Docker](services.md) and [portable diagnostics](diagnostics.md)
have separate setup and permission guides. [Prometheus](prometheus.md) and [NetBox](netbox.md) have separate setup examples.
Uptime Kuma can feed Prometheus using its documented metrics export; this is not
a direct Kuma connector. See [integration research and choices](integration-research.md).

## Wi-Fi, printers and other brands

Use LibreNMS or Zabbix as the primary source. A recognized manufacturer influences
the icon, not the monitoring protocol. Source categories or explicit overrides
select the appropriate view. Zabbix mappings can expose CPU, memory, toner and
wireless clients when those items exist and their units match the contract.
The initial LibreNMS adapter does not yet fetch its extra sensor/wireless APIs.

Supported brand recognition and actual logo availability are listed in
[brands.md](brands.md). Unknown vendors remain usable with generic icons.

## Upstream references

- [LibreNMS API authentication](https://docs.librenms.org/API/)
- [LibreNMS devices](https://docs.librenms.org/API/Devices/)
- [LibreNMS ports](https://docs.librenms.org/API/Ports/)
- [LibreNMS discovered links](https://docs.librenms.org/API/Switching/)
- [Zabbix API and mappings](zabbix.md)
- [Forcepoint API session documentation](https://fp-ngfw-smc-python.readthedocs.io/en/stable/pages/session.html)
- [Firewall adapter references](firewalls.md)
