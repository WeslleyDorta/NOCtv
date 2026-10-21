# NetBox inventory

This adapter complements monitoring with device inventory. It reads the DCIM
device list on every poll, so new devices appear without adding per-device
configuration. NetBox lifecycle values such as `active`, `offline` and `planned`
do not establish operational availability: every device has `state: unknown`,
`observed_at: null`, empty metrics and ports. An inventory edit's `last_updated`
is not an observation timestamp. The existing display may mark these devices
stale because they have no telemetry sample, even while the source poll succeeds.

## Connection

Use NetBox 4.5+ with a **v2 API token**. Store the full `nbt_<key>.<token>` value
locally as `NETBOX_TOKEN`; the adapter sends it with Bearer authentication. Legacy
v1 tokens and NetBox releases before 4.5 are not supported. Create a dedicated
account with device view permissions, disable the token's write capability, and
restrict its allowed client addresses where practical. Never paste tokens in chat.

Set `NETBOX_URL` locally to the deployment root, for example
`https://netbox.example.com/` (or `https://example.com/netbox/` for a deployment
under a path), without `/api/`. Use verified HTTPS; configure `ca_file` for a
private CA as described in [setup](setup.md). The shared HTTP client refuses
redirects and requests to another origin.

Start from [the example configuration](../config/netbox.example.json). Set
`site_map` keys to NetBox **site slugs**, mapped to configured NOCtv site IDs.
Unmapped devices use `unassigned`. Optional `devices` entries are overrides keyed
by numeric NetBox ID as a JSON string; they can set `name`, `type`, `site`, `vendor`,
`brand`, `root` and `web_url`. The default category is `device`; the adapter does
not guess category from a role. Management links come only from explicit
`web_url` overrides, never API response URLs. Primary addresses have their CIDR
prefix removed after IP validation; invalid or missing addresses stay blank.

```sh
python3 -m noctv check --config config/netbox.example.json
```

This checks configuration structure only. Put actual deployment choices in an
ignored local configuration; follow [setup](setup.md) to run it. To remove this
inventory, remove its connector from that local configuration and restart NOCtv.

## Boundaries and failures

Only `GET api/dcim/devices/` is used. Each request asks for 100 records, excludes
configuration context, and follows the API's `next` link. Pagination stays on the
device list path and original origin, with at most 100 pages and 10,000 records
per collection. Cycles, duplicate IDs, invalid result shapes or exceeded limits
reject the collection; NOCtv retains the preceding snapshot and reports a source
error. HTTP 401/403 stop that source's polling until configuration is reviewed
and the application restarts.

No interfaces, cables, virtual machines, metrics, alerts or operational topology
are collected. No inventory is merged with LibreNMS, Zabbix or other sources:
the same device in two connectors produces two distinct IDs. Use this source for
inventory coverage where that separation is useful. Fixtures verify normalization,
pagination and failure behavior; no live NetBox or equipment was validated.

The request and authentication contract follows the official
[NetBox 4.5 REST API documentation](https://github.com/netbox-community/netbox/blob/v4.5.0/docs/integrations/rest-api.md).
The [current REST API documentation](https://netboxlabs.com/docs/netbox/integrations/rest-api/)
also describes v2 authentication and pagination.
