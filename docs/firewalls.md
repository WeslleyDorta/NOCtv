# Firewall management connectors

These four adapters collect inventory and management connectivity. They leave device `state` as `unknown`: a responsive management API does not demonstrate forwarding, interface, HA, or VPN health. No adapter creates topology links, invents tunnels, or turns an authentication failure into a firewall outage. The batch declares `inventory` and `management` capabilities. A successful inventory read is not an incomplete-source warning.

| Configuration type | Documented API target | Implemented read | Evidence shown |
| --- | --- | --- | --- |
| `fortigate` | FortiOS REST monitor API v2, 7.x documentation | `GET /api/v2/monitor/system/status` | Serial, hostname/model; management API reachable |
| `panos` | PAN-OS XML API, 11.x documentation | `POST /api/`, `type=op`, fixed `show system info` command | Serial, hostname/model, management address; management API reachable |
| `checkpoint` | Check Point R80+ Management API (target R81/R82) | `show-gateways-and-servers`, standard detail | Gateway/server UID, name, type, address; engine health unknown |
| `sophos_central` | Sophos Central Firewall Management API v1 | `GET /firewall/v1/firewalls` | Firewall ID/name/model; Central `status.connected` only |

Compatibility is based on official contracts and synthetic fixture tests. These adapters have not been validated against live appliances or every firmware release. FortiGate and PAN-OS sources represent one directly queried appliance; Panorama fleet discovery, FortiManager, Check Point multi-domain traversal, Sophos on-box XML/REST configuration APIs, and Sophos partner tenant discovery are outside this implementation.

## Configure

Copy the sources you need from [firewalls.example.json](../config/firewalls.example.json) into your live configuration. Delete unused sources. Put URLs and all credentials in the collector process environment or its protected environment file, never in JSON or browser code.

| Source | Environment variables | URL format |
| --- | --- | --- |
| FortiGate | `FORTIGATE_URL`, `FORTIGATE_TOKEN` | `https://firewall.example.com` |
| PAN-OS | `PANOS_URL`, `PANOS_API_KEY` | `https://firewall.example.com` |
| Check Point | `CHECKPOINT_URL`, `CHECKPOINT_USERNAME`, `CHECKPOINT_PASSWORD` | `https://manager.example.com` |
| Sophos | `SOPHOS_URL`, `SOPHOS_CLIENT_ID`, `SOPHOS_CLIENT_SECRET`, `SOPHOS_TENANT_ID` | Regional API origin, such as `https://api-eu01.central.sophos.com` |

Supply the origin only; adapters append the documented API paths. Each environment-variable name can be changed through its corresponding `*_env` configuration field, allowing multiple appliances. Sophos obtains a fresh OAuth client-credentials token from `https://id.sophos.com/api/v2/oauth2/token` each collection. Discover the tenant ID and regional origin separately during setup using the vendor's tenant guide; the collector never follows a remote-provided destination.

Use a dedicated least-privilege account:

- FortiGate: REST API administrator with read permission for system monitoring and a trusted-host restriction to the collector. Send its token in `Authorization: Bearer`.
- PAN-OS: API key for an administrator role permitted to read operational system information. Only the fixed `show system info` command is sent, using `X-PAN-KEY`. Key generation and rotation are administrator setup tasks.
- Check Point: management API access and a read-only administrator permission profile. The adapter logs in, queries inventory, and attempts logout even after a query fails. It never publishes, installs policy, or executes scripts. Set optional `domain` to one authorized management domain when needed.
- Sophos: a tenant service principal with read access to Firewall Management inventory. Scope credentials to the intended tenant; no partner-wide traversal or actions are performed.

TLS certificate and hostname validation are required. Add `"ca_file": "/path/to/trusted-ca-bundle.pem"` for a private CA. For Sophos the bundle must also trust the public OAuth service. There is no insecure TLS or plaintext HTTP option. Redirects, including same-origin redirects, are rejected; configure the final origin directly.

## Sites and state

Device IDs are `<source id>:<native id>`. Native IDs are the FortiGate serial, PAN-OS serial, Check Point object UID, or Sophos firewall ID. Map those IDs to local sites using `site_map`, or set `devices[native_id].site`. A device override also supports `name`, `root`, and a safe `web_url`. Unmapped inventory belongs to `unassigned`.

`management_state` is separate from device `state`:

- FortiGate/PAN-OS: `up` only after a valid direct appliance response with an identifier.
- Check Point: `unknown` for managed inventory; querying the management server says nothing about each engine's reachability. Management server objects are typed as servers.
- Sophos: `up`/`down` only for an explicit boolean Central connection status; missing or unexpected values stay `unknown`. This is cloud-management connectivity, not packet forwarding.

`observed_at` records the inventory poll time. It does not claim a dataplane measurement. Authentication, connection, malformed payload, or incomplete pagination failures raise a sanitized source error, allowing the collector to retain and age its previous snapshot. Unknown operational state is intentional even when the source is connected.

## Limits and other vendors

Requests time out after 10 seconds, response bodies are capped at 2 MB, and paginated inventory is capped at ten pages of 100 requested entries. Hitting the page cap fails the collection instead of silently treating a truncated fleet as complete. Pagination is sequential; a large source can take multiple request timeouts. API error text, response bodies, session IDs and credentials are not emitted in error messages. PAN-OS XML accepts UTF-8 and rejects declarations such as DTD/entities, comments and CDATA before parsing; it never resolves external resources.

Use LibreNMS or Zabbix for operational interface, throughput, uptime, health and discovery metrics across Cisco, Juniper, SonicWall, WatchGuard, pfSense/OPNsense, and other devices supported by your monitoring system. Configure and validate that upstream's vendor templates/SNMP permissions first. Its real polling and topology evidence determines what NOCtv can display. Do not describe these inventory adapters as VPN monitoring, and avoid adding the same appliance through multiple sources unless you want separate namespaced cards.

## Sources and verification

- [Fortinet Python REST example](https://community.fortinet.com/fortigate-3/technical-tip-python-script-example-for-fortigate-rest-api-211989) and [Fortinet-maintained REST transport](https://github.com/fortinet-ansible-dev/ansible-galaxy-fortios-collection/blob/main/plugins/httpapi/fortios.py).
- [PAN-OS XML API exploration and system-info command](https://docs.paloaltonetworks.com/ngfw/api/getting-started/explore-xmlapi) and [Palo Alto's system-info client](https://github.com/PaloAltoNetworks/pango/blob/main/client.go).
- [Check Point Management API reference](https://sc3.checkpoint.com/documents/latest/APIs/) and [Check Point's gateway inventory query example](https://github.com/CheckPointSW/PolicyCleanUp/blob/master/policyCleanUp/policyCleanUp.py).
- [Sophos firewall API guide](https://developer.sophos.com/firewall-management/), [v1 reference](https://developer.sophos.com/reference/firewall-v1/), and [tenant authentication setup](https://developer.sophos.com/getting-started-tenant/).

Run `python3 -m unittest discover -s tests -p test_firewalls.py -v` for fixture normalization, missing/failed responses, pagination/logout, unknown operational state, sanitization, TLS/redirect policy, XML attacks and response bounds. No production credentials are needed.
