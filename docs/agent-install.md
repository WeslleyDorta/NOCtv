# Install with an AI coding agent

Clone this repository and open its directory in an agent that can read local
files and run terminal commands. Review commands through your tool's normal
permission controls. A chat with only a GitHub link can explain the installation,
but cannot deploy to your machine without access to it.

Copy this request into your agent:

> Read AGENTS.md and docs/agent-install.md. Help me install NOCtv on this machine.
> Inspect the environment first, ask which monitoring source I want to connect,
> preserve existing configuration, and guide me to enter credentials locally.
> Validate the application and the source separately. Explain any missing data.

Em português:

> Leia AGENTS.md e docs/agent-install.md. Ajude-me a instalar o NOCtv nesta máquina.
> Verifique o ambiente primeiro, pergunte qual monitoramento quero conectar,
> preserve configurações existentes e me oriente a preencher credenciais localmente.
> Valide a aplicação e a integração separadamente. Explique os dados que faltarem.

`AGENTS.md` contains shared project guidance. `CLAUDE.md` imports it with
`@AGENTS.md`, using [Claude Code's documented import syntax](https://code.claude.com/docs/en/memory#import-additional-files).
Agents that do not automatically load [AGENTS.md](https://agents.md/) should be
explicitly asked to read it. These files guide the agent; they do not enforce
permissions or replace credential isolation. No AI service is required at runtime.

## 1. Inspect and choose

Check the repository directory, Git changes, OS, Docker/Compose availability,
Docker daemon access, and whether the selected port or an existing NOCtv service
is already in use. Do not stop unrelated processes or install missing system
software without the user's authorization. On Windows, adapt shell commands or
use the user's available WSL environment; do not assume a Unix shell.

Ask only for choices not already known:

- Demo or live data? LibreNMS, Zabbix, both, or another supported connector?
- Which API versions and endpoints are available? Endpoints may also be entered
  locally when the operator does not want them in chat.
- Local evaluation or access from TVs on the network? Existing HTTPS proxy?
- Which units/categories should appear, and which interfaces are mandatory?

Read [setup](setup.md) and [coverage](integrations.md). If no monitoring system
exists, explain that the demo works immediately but live mode needs an existing
source. Do not build a new monitoring infrastructure as an implicit install step.

## 2. Verify the demo

On a fresh checkout with Docker Engine and Compose 2.24+:

```sh
docker compose config --quiet
docker compose up --build -d
```

Open `http://localhost:8080`. Confirm the simulated-data badge, seven views,
switch/port interaction and TV loop. Stop with `docker compose down` when needed.
On an existing live installation, do not replace its configuration to run a demo;
use a separate checkout/project and an unused port, or skip the demo.

Python 3.12+ can run a local preview with `python3 -m noctv serve --port 8080`.
The preview is not the production server. Node is needed only for browser tests.

## 3. Prepare private configuration

First check whether `.env` and `config/local.json` already exist. If they do,
preserve them and store a restricted backup outside Git (for example under the
ignored `secrets/` directory). Use exclusive file creation for new files; do not
blindly copy examples over a working installation.

For a new installation, create `.env` from `.env.example`. Create
`config/local.json` from `config/live.example.json` for LibreNMS, or
`config/zabbix.example.json` for Zabbix. Set `NOCTV_CONFIG_FILE=./config/local.json`.
Have the operator fill credentials in a local editor or secret store, without
pasting values into chat or shell arguments. Live mode also requires `NOCTV_USER`
and a unique `NOCTV_PASSWORD` of at least 16 characters.

| Source | Local environment settings | Configuration work |
| --- | --- | --- |
| LibreNMS | `LIBRENMS_URL` ending in `/api/v0/`, `LIBRENMS_TOKEN` | Map actual location strings to site IDs; adjust category/root/required-port overrides |
| Zabbix | `ZABBIX_URL` ending in `api_jsonrpc.php`, `ZABBIX_TOKEN` | Read [Zabbix guide](zabbix.md); use the operator's host IDs and exact template item keys |

Use dedicated read-only accounts. Zabbix requires access to the desired hosts
and `host.get`/`item.get`. Replace or remove the sample device IDs and all
`example.*` item mappings; they are not ready-to-use templates. Do not invent keys
to make CPU, toner, clients or ports appear. Report absent metrics honestly.

For both sources, combine their connector objects in one `connectors` list with
unique IDs and a shared list of sites. Avoid duplicate devices: there is no
automatic cross-source merge. Inventory additions are dynamic, but classification
and site mapping may need overrides. Zabbix topology is not implemented.

Keep JSON free of credentials; it references environment variable names only.
Compose loads `.env`; the Python CLI does not. Keep private files restricted to
the intended operator. Ensure the container's UID 10001 can read its mounted JSON
and CA files without making secrets world-readable. Do not use `chmod 777`.

Check that `.env` and `config/local.json` are ignored by Git. Never put installation
details in `AGENTS.md`, `CLAUDE.md`, tracked examples or a public support issue.

## 4. Validate and start

If Python 3.12+ is available:

```sh
python3 -m noctv check --config config/local.json
```

Otherwise, after building the image, validate with Docker:

```sh
docker compose build
docker compose run --rm --no-deps noctv python -m noctv check --config /app/config/runtime.json
```

Both commands validate structure only. They do not verify credentials or API
compatibility. Use `docker compose config --quiet` to validate Compose without
printing expanded secrets. Do not use plain `docker compose config`, `env`, or
`docker inspect` in captured output to troubleshoot credentials.

Once the chosen settings and credentials are in place:

```sh
docker compose up -d --build --force-recreate
docker compose ps
```

The default listener is localhost. For a remote TV, follow the HTTPS and access
control section of [setup](setup.md); do not expose Basic authentication over
unencrypted HTTP. Keep the demo public only if it uses synthetic data.

## 5. Verify actual telemetry

Wait for the first collection, then check all three layers:

1. **Application:** `/healthz` responds; live pages require viewer authentication.
2. **Sources:** the dashboard/source snapshot reports each configured source's
   state and a recent successful collection. An empty inventory is not success
   unless the operator expects zero visible devices.
3. **Data:** compare a representative device and, where supported, a port/metric
   against the upstream UI. Verify its unit, timestamp, category and site. Confirm
   a later collection updates the observation; never turn off equipment to test.

Prefer the authenticated local UI. If inspecting `/api/v1/snapshot` in a script,
read credentials from the local process environment and print only a sanitized
summary of counts, source states and timestamps, not the inventory or tokens.
Do not upload live screenshots or responses to a public issue.

NOCtv API polling does not change upstream ping, SNMP or discovery schedules.
Align freshness thresholds with actual collection periods; do not hide stale data
by assigning current timestamps or arbitrarily extending thresholds.

| Symptom | Next check |
| --- | --- |
| HTTP 401/403 or authentication rejected | Credential permissions, token expiry and endpoint; polling stops until restart after correction |
| TLS error | Hostname, certificate chain and private CA mounting; keep verification enabled |
| No devices | Account visibility, monitored/ignored status and source inventory |
| Unknown state or missing metric | Timestamp, item key, supported/enabled item and documented connector coverage |
| No topology | Upstream discovery and available links; Zabbix does not supply topology in this release |
| Healthy process, source error | Diagnose the connector separately; `/healthz` is not an integration test |

## 6. Hand over and preserve recovery

Report the local access URL, selected sources, what was actually verified,
unresolved gaps, collection periods and the files changed, without secrets.
If source access is unavailable, say "demo verified; live integration pending"
rather than claiming installation is fully connected.

Document how to stop this Compose project, restore its private configuration
backup, and recreate only its service. Do not remove volumes, reset Git, prune
Docker or overwrite an upstream system as part of rollback. Preserve local files
and review changes before future upgrades. Commit only generic documentation or
code changes when the user requested repository work.
