# Services and Docker containers

NOCtv has dedicated **Services** and **Containers** screens. Open **Tools → Visible
screens** to hide unused views from both navigation and the TV loop. Preferences
are stored in this browser. Collection and the global alert ticker continue for
hidden screens; this is not an alert-suppression or permission control.
At least one screen must remain visible. **Restore installation defaults** clears
the browser's hidden list. `display.views` defines the allowed screens and their
order for the installation, for example:

```json
"display": {"views": ["connections", "services", "containers"]}
```

Available IDs: `connections`, `servers`, `ports`, `switches`, `printers`, `wireless`,
`devices`, `services`, `containers`. All are included by default. No automatic
hiding occurs during a temporary outage or empty collection.

## Native service checks

Copy [services.example.json](../config/services.example.json) to an ignored local
configuration and merge its connector into your installation if needed. The
`probes` connector performs only explicitly configured checks, from the NOCtv
server/container. It does not discover targets. Supported checks:

| Kind | Result |
| --- | --- |
| `http` | GET over HTTP/HTTPS; expected response codes, optional keyword, response time |
| HTTPS | Verified TLS and certificate days remaining; warning at 21 days by default |
| `tcp` | A TCP connection to the configured host and port |
| `dns` | DNS response, optional exact RDATA match |
| `ping` | One ICMP echo through the system ping utility |

All checks require a unique `id` and `kind`; optional `name`, `site`, `web_url`
and `timeout_seconds` (1–15, default 5) apply. Per connector: 1–50 checks, four
concurrent checks, no overlapping polling cycles. `interval_seconds` defaults to
60 (minimum 10); `max_age_seconds` must accommodate a complete cycle. A large set
of slow checks can take longer than the requested interval. Timeouts apply to
network operations, not a hard deadline for OS hostname resolution.

HTTP destinations use `url_env`: the URL stays in an environment variable,
including any private query/path. It must be HTTP(S), without embedded credentials
or fragments. `expected_status` defaults to 200–299. Redirects are **not followed**;
configure the final URL. Optional `keyword` checks up to 256 KiB as UTF-8. A larger
response produces UNKNOWN, without storing or displaying its body.

For HTTPS, optional `ca_file` supplies a trusted private CA;
`certificate_warning_days` sets the expiration warning. Optional `token_env`
sends a bearer token only over HTTPS. The display receives the hostname and
measurements, never the full URL, authorization header or response body. A web
shortcut exists only if you explicitly set a safe `web_url`.

TCP requires `host` and `port`. DNS requires `host`; optional `record_type`
(`A`, `AAAA`, `CNAME`, `MX`, `TXT`, `NS`, `PTR`), `dns_server` (IP literal) and
`expected_value` (exact answer RDATA) control the query. Ping requires `host`.
Missing binaries/configuration produce UNKNOWN; failed reachability or failed
expected results produce DOWN. A successful TCP/ping check does not prove an
application is working. Latency includes the operations of the configured check,
including certificate inspection for HTTPS; it is not always ICMP RTT.

The [Docker image includes DNS and ping tools](diagnostics.md). Non-container
installations need those binaries only when using the corresponding checks.
Native checks are independent of the interactive diagnostics CIDR policy: their
targets are explicitly authorized through the administrator's local configuration.

## Docker Engine

Use [docker.example.json](../config/docker.example.json). The `docker` connector
reads an **HTTPS endpoint** provided by the operator: an authenticated read-only
proxy in front of Docker Engine, or an Engine endpoint with TLS, client certificate
authentication and a read-only authorization policy. NOCtv has no start, stop,
exec, delete or container-creation operations.

Configure `DOCKER_API_URL` locally. Optional fields: `ca_file`,
`client_cert_file`, `client_key_file` for mTLS; `token_env` for a proxy accepting a
bearer token. Mount private certificates read-only under `secrets/` with paths
matching your JSON, readable by container UID 10001. Do not disable verification.

Allow only these GET routes (API version configurable; default `1.45`):

- `/v1.45/containers/json?all=true`
- `/v1.45/containers/<64-character ID>/json`
- `/v1.45/containers/<64-character ID>/stats?stream=false&one-shot=true` when enabled

Use an endpoint compatible with the configured API version. The included Compose
file does **not** mount `/var/run/docker.sock` or expose a Docker TCP listener.
Mounting a Docker socket `:ro` does not make Docker API operations read-only.
Do not expose an unauthenticated Engine API to make collection work.

By default, new containers appear on each successful inventory. `container_names`
optionally limits collection to an explicit list; a missing expected name becomes
DOWN. Without that list, deleted containers disappear. IDs use connector + name;
a renamed container is a new identity. `max_containers` is 50 by default (max 200);
exceeding it produces a collection error rather than silently omitting inventory.
Stopped containers are DOWN, including intentionally stopped jobs: use an explicit
list to scope monitoring to long-running workloads. No maintenance scheduler is
included.

The screen separates runtime and application health. A running container with no
healthcheck shows **not configured**, not “healthy.” An unhealthy healthcheck is
DOWN; restarting/starting is attention. Restarts come from Engine's counter.
`collect_stats` is opt-in: memory is usage / limit; CPU is the share of total host
CPU time, not the Docker CLI's per-core percentage. A first sample or absent CPU
deltas remains unavailable. Inspect errors become UNKNOWN; a failed optional
stats request does not invent a runtime outage. Environment variables, commands,
mounts and healthcheck logs from inspect are never included in the snapshot.

## Uptime Kuma and current scope

Existing Kuma installations can feed [Prometheus](prometheus.md). Override the
corresponding identities to `"type": "service"` to show them in Services. The
native probes do not read Kuma's private database or undocumented API. This is
not full Kuma parity: push heartbeats, notification providers, persistent uptime
history, MQTT and database-specific checks are not implemented. Charts show
samples collected during the current browser session.

Verification includes synthetic fixtures and an isolated Linux Docker lab with
Engine 29.1.3 / API 1.45, a scoped mTLS read proxy, native checks, TLS validation and
failure/recovery. See [the validation record](release-readiness.md) for exact scope.
Each deployment and production target still needs installation-level validation. Demo mode makes no outbound checks, even with connector definitions.

References: [Docker Engine API](https://docs.docker.com/reference/api/engine/version/v1.45/),
[Docker daemon access](https://docs.docker.com/engine/security/protect-access/),
[Uptime Kuma Docker monitoring](https://github.com/louislam/uptime-kuma/wiki/How-to-Monitor-Docker-Containers).
