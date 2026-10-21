# Zabbix connector

The connector targets the documented Zabbix 7.0 API with Bearer token authentication. Automated tests use synthetic responses; no live Zabbix instance or other release has been certified. The API user needs read access to the desired hosts and permission to call `host.get` and `item.get`. Use a dedicated API token with a read-only role.

Set `ZABBIX_URL` to the complete endpoint, for example `https://monitor.example/zabbix/api_jsonrpc.php`, and provide `ZABBIX_TOKEN` through the server environment. Use your service manager or secret store; do not put the token in configuration, a browser, a URL, or command history. Copy `config/zabbix.example.json` to a local configuration and replace the example inventory IDs and item keys. The example keys beginning with `example.` are placeholders, not standard Zabbix keys.

TLS certificate verification is enabled. `ca_file` can specify a private CA bundle. Redirects are refused, requests time out after 10 seconds, and each response is limited to 8 MB. `allow_http: true` is available only for a deliberately selected trusted local test endpoint; HTTP exposes the token on the network. The client allows only two read methods, even though JSON-RPC transports them using POST. Errors expose fixed codes rather than response bodies. Authentication rejection stops that source's polling until restart. A reverse proxy must forward the Authorization header.

Each poll retrieves the current visible monitored hosts, so newly added hosts appear automatically. Unmonitored hosts are excluded. Host `status=0` means monitoring is enabled; it is never treated as evidence that a host is online. Reachability comes from the latest supported and enabled `icmpping` item: 1 is up, 0 is down, and other/missing/stale values are unknown. Hosts without reachability evidence can still carry fresh metrics. `lastclock` supplies timestamps; polling never renews an old sample. Each metric also carries its own timestamp in `metric_observed_at`.

Default exact item keys:

| NOCtv field | Zabbix item key | Interpretation |
| --- | --- | --- |
| status | `icmpping` | 0 down, 1 up |
| latency_ms | `icmppingsec` | Seconds converted to milliseconds |
| uptime_seconds | `system.uptime` | Seconds |
| memory_percent | `vm.memory.size[pused]` | Used percentage |

An `item_map` object can be set on the connector or on a device override keyed by Zabbix host ID. Values are exact item keys, including parameters when present. Device mappings override connector mappings. Supported destinations are `status`, `latency_ms`, `uptime_seconds`, `cpu_percent`, `memory_percent`, `disk_percent`, `toner_percent`, and `clients`. Explicit percentage mappings must already represent 0–100 percentages; `clients` must be a nonnegative whole count. Custom latency items must return milliseconds, except `icmppingsec` and its parameterized keys, which are converted from seconds. Status mapping requires a binary 0/1 reachability measurement. There is no guessed CPU, toner, wireless-client, or interface key: templates and vendors differ. Missing, disabled, unsupported, or stale explicit mappings yield a source warning and absent metrics.

Set device `type` to `switch`, `firewall`, `router`, `server`, `printer`, `wireless`, or `device`; the default is `device`. `site_map` maps the inventory `location` field to configured site IDs. A device's `site` override takes precedence. Name, root, and web URL overrides use the common connector contract. Model/vendor/OS come only from the corresponding inventory fields.

The optional `ports` list can be set on a connector or device; a device list replaces the connector list. Each entry needs a unique string `id` and exact `state_key`. `name` is optional. `up_value` and `down_value` default to 1 and 2, matching an explicitly chosen IF-MIB oper-status item. Other values remain unknown; administrative state is unknown. Set `required: true` to use NOCtv's required-port alert. Port timestamps come from the item, and stale/disabled/unsupported items become unknown. Traffic counters, speeds, automatic port discovery, trigger alerts and physical topology are not implemented. The connector returns no links; host groups do not establish physical connections.

Official references: [API and authentication](https://www.zabbix.com/documentation/7.0/en/manual/api), [host.get](https://www.zabbix.com/documentation/7.0/en/manual/api/reference/host/get), [item.get](https://www.zabbix.com/documentation/7.0/en/manual/api/reference/item/get), [item timestamps and state](https://www.zabbix.com/documentation/7.0/en/manual/api/reference/item/object), [ICMP simple checks](https://www.zabbix.com/documentation/7.0/en/manual/config/items/itemtypes/simple_checks), [agent keys](https://www.zabbix.com/documentation/7.0/en/manual/config/items/itemtypes/zabbix_agent).
