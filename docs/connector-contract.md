# Connector contract v1

Implement `collect()` returning a JSON-safe object with `devices`, `links` and
optional `warnings`. The collector validates it before replacing the previous
snapshot. Exceptions must be sanitized: never include response bodies, keys,
request headers, credential URLs or arbitrary upstream error messages.

A minimal response:

```json
{
  "devices": [{
    "id": "example:1", "name": "Core switch", "type": "switch", "site": "hq",
    "state": "up", "observed_at": "2026-01-01T12:00:00+00:00",
    "ip": "192.0.2.10", "model": "Example switch", "metrics": {}, "ports": []
  }],
  "links": [],
  "warnings": []
}
```

Use `<connector id>:<native id>` for globally unique stable IDs. Device types:
`switch`, `router`, `firewall`, `server`, `printer`, `wireless`, `device`.
States: `up`, `down`, `attention`, `standby`, `disabled`, `unknown`.
Missing evidence is unknown, not down or up. Never infer an outage from a failed
API login, or device availability from a monitoring-enabled flag.

`observed_at` is a UTC ISO timestamp for the actual upstream sample. Use `null`
when unknown; do not replace a stale sample with the HTTP retrieval time.
`metric_observed_at` optionally maps individual metric keys to sample timestamps.
Use finite nonnegative numbers for metrics; unavailable values are null.

Metrics recognized by the interface include `latency_ms`, `uptime_seconds`,
`cpu_percent`, `memory_percent`, `disk_percent`, `toner_percent`, `clients`.
Percentages mean used percent, except toner means remaining percent. Convert
fractions/bytes into those units in the adapter. Optional `vendor`, `os`, `model`
feed conservative brand recognition. Explicit `brand` overrides use catalog IDs.

Ports have string `id`, `name`, `state`, `observed_at`, and optionally
`admin_state`, `description`, `speed_mbps`, `rx_bps`, `tx_bps`, `required` and
`neighbors`. A neighbor contains `id`, `name`, `ip`, `evidence`. Do not turn an
interface alias into a discovered neighbor. Never assume interface index equals
physical front-panel position.

Links require unique string `id`, device IDs `a`/`b`, `kind` (`lan` or `vpn`),
`state`, `observed_at`, and `evidence`. LAN links identify `a_port` and `b_port`
so the collector can age the displayed state with both endpoint ports, while
`max_age_seconds` may separately limit discovery evidence. No connection is
created from site membership alone. VPN metrics can include `latency_ms`,
`loss_percent`, `traffic_bps`; absent metrics stay null.

Management-only adapters can include `management_state` and `capabilities` without
promoting device `state`. Optional `services` contains name/state pairs. These
must age with their source. `warnings` means incomplete collection, not a normal
capability limitation.

## Add a source

1. Add one module under `noctv/connectors/` accepting its source configuration.
2. Register its class in `collector.ADAPTERS` and its type in `config.load`.
3. Read credentials only from named environment variables. Reuse bounded TLS
   clients where possible; reject redirects and foreign-origin credential requests.
4. Use read endpoints; an API POST must be a fixed read query/login/logout, never
   arbitrary commands passed from browser input.
5. Add synthetic normalization, unknown/stale, failure and secret-redaction tests.
6. Add an example config and a truthful row in the integration matrix.

The API exposes `/api/v1/config` (allowlisted display settings) and
`/api/v1/snapshot` (`schema_version`, `generated_at`, `mode`, `devices`, `links`,
`sources`, `alerts`). Adding optional fields is compatible; changing field
semantics requires a versioned contract change. Browser refreshes never trigger
collection. Each source has one polling thread, with no overlapping cycles.
