# Installation and configuration

For guided setup through a coding agent, start with the
[agent installation guide](agent-install.md). It uses these same configuration
files and commands; no separate installer or AI runtime is needed.

## Requirements

- Docker Engine and Docker Compose 2.24+; or Python 3.12+ for a local preview.
- Existing monitoring systems for live mode. NOCtv does not install them.
- Read-only credentials and trusted TLS certificates for the chosen APIs.

Run `docker compose up --build -d` for the demo. Docker builds one image, runs as
UID 10001, mounts configuration read-only and has no network administration
capabilities. The service binds to `127.0.0.1:8080` by default. `.env` is optional
for demo and is excluded from Git and the image context.

For a local preview use `python3 -m noctv serve --port 8080`. To run Gunicorn outside
Docker, create a Python environment, install `requirements.txt`, then run:

```sh
gunicorn 'noctv.server:create_app()' --bind 127.0.0.1:8080 --workers 1 --threads 8 --no-control-socket
```

Keep exactly one worker and do not use `--preload`: collectors run inside the
worker and multiple workers would duplicate polling. Additional viewers reuse
the same snapshot. Thread count and collection periods should be adjusted only
after measuring resource use and upstream API limits.

## Live installation

```sh
cp .env.example .env
cp config/live.example.json config/local.json
python3 -m noctv check --config config/local.json
```

Edit `.env` locally:

```dotenv
NOCTV_CONFIG_FILE=./config/local.json
NOCTV_USER=viewer
# Set NOCTV_PASSWORD to a unique secret of at least 16 characters.
LIBRENMS_URL=https://monitoring.example.com/api/v0/
# Set LIBRENMS_TOKEN to your read-only API token.
```

The real secrets are intentionally absent from examples. `docker compose` loads
`.env`; the plain Python CLI does not. Export environment variables explicitly
when running without Docker. Never put credentials in a URL or JSON config.
Make the local files readable only by the intended administrator/container.

Run `docker compose up -d --build --force-recreate` after configuration changes.
The `check` command validates structure without contacting upstream APIs. Startup
in live mode refuses missing viewer credentials. API credentials are checked by
individual connectors and errors appear as source errors, not device outages.

`GET /healthz` only checks that the web process responds. It does not certify
upstream health. `/api/v1/snapshot` reports each source's state, last success,
collection duration and warnings. The UI also exposes these timestamps.

## Sites and equipment

For [country/world maps](maps.md), configure latitude/longitude and country codes.
Site IDs are stable local identifiers. In schematic mode, `x` and `y` are percentages from
10 to 90, **not geographic coordinates**. Set `kind` to `headquarters`, `branch`
or `cloud`; cloud sites have a distinct symbol. Only reported links are drawn.
Unmapped devices are visible under Unassigned. The initial TV composition works
best with a small number of sites; large layouts need a narrower scope.

LibreNMS `site_map` maps the upstream location string to a site ID. `devices`
uses native device IDs, e.g. `"1"`. Overrides can set `name`, `site`, `type`, `root`,
`web_url`, `brand`, and `required_ports`. Available types:
`switch`, `router`, `firewall`, `server`, `printer`, `wireless`, `device`.
Device web links are opt-in and accept only HTTP(S), without embedded credentials.

LibreNMS's generic `network` type initially maps to switch. Override routers or
other classifications when the upstream metadata is too broad. New devices are
included dynamically, and removed/disabled/ignored devices leave the next
successful inventory. No automatic identity merge spans different sources.

For the current port policy, only explicitly required interfaces produce critical
DOWN alerts. Administrative DOWN is separate. There is no default business-hours
suppression and no assumption that every unused interface is an incident.

## Polling and freshness

`interval_seconds` controls calls to an API; it does **not** change that system's
SNMP/ping/discovery schedules. `max_age_seconds` controls acceptable telemetry age.
LibreNMS's `last_polled`, port `poll_time`, and device `last_discovered` are retained.
Set `upstream_timezone` to the timezone of naive LibreNMS timestamp strings.
Configure `discovery_max_age_seconds` to match your discovery policy.

Fresh HTTP responses containing old samples remain stale. Source failures retain
the last inventory but render state/metrics unknown. Authentication rejection
stops that source's polling until restart, allowing credential review. Sources
run independently, so a slow or failed source does not stop other adapters.

## Forcepoint SMC

Append the object from `config/forcepoint.example.json` to `connectors` in your
live configuration. Set `FORCEPOINT_URL` to the SMC HTTPS origin,
`FORCEPOINT_KEY` to a read-only API key, and `FORCEPOINT_DOMAIN` to its authorized
administrative domain. The adapter targets API **7.2**. Configure `include_names`
and `site_map` using exact engine names. An empty include list reads the inventory
visible to that credential. Native device override keys are engine resource paths.

Only login, monitoring queries, read endpoints and logout are allowed. Managed
VPN links require exact engine references. External peers without both managed
endpoints are not drawn as managed site links. Unknown VPN codes stay unknown;
`PARTIALLY_FAILED` is attention, not healthy.

TLS hostname/certificate verification is always on. For private CAs, mount a
trusted bundle read-only with a Compose override and set the connector's
`ca_file` to that container path. Do not disable certificate checks.

## Other sources

[Zabbix](zabbix.md), [Prometheus](prometheus.md), [NetBox](netbox.md) and
[firewall management APIs](firewalls.md) have separate
examples. `config/zabbix.example.json` and `config/firewalls.example.json` are full
configuration files; the Forcepoint example is a single connector object. Keep
only sources you use and give each a unique ID. The Compose service loads custom
credential environment names from `.env`, supporting multiple instances.

## Remote access

Live mode uses browser HTTP Basic authentication. Place the service behind an
HTTPS reverse proxy before accessing it across a network. Basic authentication
without TLS does not encrypt credentials. Bind only to interfaces you intend to
expose, restrict firewall access, and do not place operational snapshots on a
public portfolio endpoint. Keep portfolio demonstrations in demo mode.

The service has no configuration editor, shell commands, write APIs, device
scanning, anonymous live API, or public metrics endpoint. Back up your private
configuration separately; the repository is not an operational backup.
