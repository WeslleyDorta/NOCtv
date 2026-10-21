# Prometheus

NOCtv reads an existing Prometheus server through its
[HTTP instant-query API](https://prometheus.io/docs/prometheus/latest/querying/api/#instant-queries).
It discovers identities present in configured selectors each poll and displays
status and explicitly mapped metrics in the existing interface. It does not
install exporters, scrape targets directly, write Prometheus configuration, or
infer ports, LAN/VPN links, hardware type or device reachability from scrape health.

Copy [the example](../config/prometheus.example.json) to an ignored local config.
Set `PROMETHEUS_URL` locally to the HTTPS base URL of Prometheus, including any
reverse-proxy prefix, for example `https://prometheus.example/prometheus/`.
For Bearer authentication add `"token_env": "PROMETHEUS_TOKEN"` and set that
environment variable locally. Without `token_env`, no Authorization header is
sent. Keep tokens out of config files and chat. Use a read-only proxy credential;
TLS verification is required. `ca_file` supports a private CA. The adapter rejects
HTTP, redirects and credential-bearing URLs.

```sh
python3 -m noctv check --config config/prometheus.example.json
```

This command validates configuration only. Fixture tests exercise synthetic API
responses; this integration has not been validated against a live deployment.

## Status and identity

`status_query` is required. Use a raw instant-vector selector such as
`probe_success{job="blackbox"}` whose values actually represent the check you want
to display: exactly `1` is up and `0` is down. Other values are unknown. The check
may represent a particular HTTP service or ICMP target, not the whole host.
Prometheus `up` only means the exporter scrape succeeded and is rejected as a
status selector. No default status query is supplied.

`identity_label` defaults to `instance`. Choose a stable, unique label shared by
all configured selectors. An identity repeated within a selector, including
across jobs or replicas, is ambiguous and yields unknown/unavailable evidence.
Filter selectors to one series per identity; the adapter never picks the first
replica or aggregates them. Returned identities become `<connector id>:<label>`.
The union of status, metric and explicit `devices` identities is displayed.
A configured device absent from query results remains unknown. An unconfigured
dynamic identity absent from all selectors disappears on the next successful poll.

`devices` maps exact identity values to optional `name`, `type`, `site`, `ip`,
`model`, `vendor`, `os`, `web_url` and `root`. Type defaults to `device`.
`site_label` and `site_map` translate explicitly known status-label values into
configured site IDs; an individual device's `site` takes precedence. Unmapped
sites are `unassigned`. Labels do not infer locations, topology or hardware.

## Metrics and freshness

`metric_queries` maps each desired output metric to `{ "query": "selector",
"scale": 1 }`. Supported keys are `latency_ms`, `uptime_seconds`, `cpu_percent`,
`memory_percent`, `disk_percent`, `toner_percent` and `clients`. Output percentages
mean used percent, except toner means remaining percent. Choose matching upstream
semantics. `scale` is a finite positive multiplier: seconds to milliseconds use
1000, fraction to percent uses 100. Values must be finite and nonnegative;
percentages must not exceed 100 and client counts must be integers. Missing,
invalid or stale measurements are omitted with a partial-collection warning.

Only metric names with optional label matchers are accepted. Expressions,
aggregations, ranges, offsets and explicit evaluation modifiers are rejected.
For each selector, NOCtv performs two GET requests at the same evaluation time:
the selector and `timestamp(selector)`. It joins complete label sets, excluding
`__name__`, and uses the timestamp function's **value** as the source observation
time. The outer instant-query timestamp describes evaluation time and does not
refresh old evidence. This follows the documented
[`timestamp()` semantics](https://prometheus.io/docs/prometheus/latest/querying/functions/#timestamp).
Stale status becomes unknown according to `max_age_seconds`; the original sample
time remains visible. Missing or mismatched timestamp series are unknown.

A timestamp describes the sample stored in Prometheus. Exporters that repeat an
old result with a new scrape timestamp, or recording rules that repeatedly emit
an old underlying result, can hide the original check age. NOCtv cannot recover
that age from these selectors. Use an upstream metric whose sampling semantics
match the intended observation and set a suitable age limit.

There are at most 16 requests per poll: status plus seven metric selectors, with
a timestamp request for each. Each request has an 8-second query timeout, the
shared client's 10-second HTTP timeout and 8 MB response cap. `max_series`
defaults to 1000 and accepts 1–10000; it bounds each query and the total discovered
inventory. The API is asked for one extra series to detect overflow. Overflow,
API errors and API warning responses fail the collection with sanitized errors.
The collector retains and ages its previous snapshot; it does not report a device
outage based on an API failure. Valid results with malformed or ambiguous samples
are partial, with unavailable evidence marked unknown.

## Uptime Kuma via Prometheus

[Uptime Kuma's documented Prometheus integration](https://github.com/louislam/uptime-kuma/wiki/Prometheus-Integration)
exports `monitor_status` and `monitor_response_time` for Prometheus to scrape.
Configure that scrape separately, then point NOCtv at Prometheus. For example,
use `status_query: monitor_status{job="uptime"}` and
`identity_label: monitor_name` if friendly names are unique and stable in your
installation. Map `latency_ms` to `monitor_response_time{job="uptime"}` with scale
1 only after verifying the exporter's unit. Renaming an identity changes the
NOCtv device ID. Additional monitor states beyond 0/1 stay unknown. This adapter
does not connect to Kuma's Socket.IO API or parse its `/metrics` endpoint.
