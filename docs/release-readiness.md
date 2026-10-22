# Community preview validation record

Updated on 2026-10-22. The clean installation checks used application code at
`3620082`; the Docker/Engine lab used `fe7ed08` (runtime feature commit `ac095ea`).
Documentation updates do not change application behavior. Re-run relevant checks when
code, dependencies or the image changes. This is evidence for a preview, not a
vendor certification or a security audit.

## Evidence collected locally

| Check | Result | Scope |
| --- | --- | --- |
| Unit / adapter fixtures | PASS, 104 tests | Normalization, configuration, auth, probes, Docker fixtures, stale/unknown states and diagnostics |
| Clean archive installation | PASS | Exported committed files into a disposable directory; used system Python with no reused `.env`, `.venv`, `node_modules` or private configuration |
| Clean demo startup | PASS | `/healthz`, config and snapshot served; nine views and 38 synthetic items |
| Browser validation | PASS in the preceding implementation pass | Nine screens, 1080p fit, responsive layouts, dialogs, state updates, hidden-screen persistence/rotation and no external demo requests |
| Configuration examples | PASS | All complete example configs, including Services and Docker; validation makes no upstream calls |
| Docker build / Compose | PASS | Clean exported checkout; Docker Engine 29.1.3, Compose 2.40.3, Python 3.12 slim; demo healthy with 38 items / nine screens |
| GitHub Actions | PASS | [First public Checks run](https://github.com/WeslleyDorta/NOCtv/actions/runs/39778422662), commit `fe7ed08`: Python, browser, config validation, Docker build and container smoke test |
| Container restrictions | PASS | UID 10001, read-only root filesystem, all capabilities dropped, no-new-privileges and unprivileged ping sysctl |
| Live native checks | PASS in disposable lab | HTTP, TCP, DNS and ping UP over two collection cycles; HTTPS trusted private CA, certificate-expiry warning and rejection of untrusted certificates |
| Interactive diagnostics | PASS in disposable lab | Ping, traceroute, reverse DNS, Nmap TCP and service detection executed against only the demo container; live viewer auth, custom-header and CIDR restrictions checked |
| Real Docker Engine adapter | PASS in disposable lab | API 1.45 on Engine 29.1.3, scoped read-only HTTPS proxy with mTLS; real runtime, healthcheck, restart count and memory; two inspection cycles |
| Failure / recovery | PASS in disposable lab | Stopped demo caused Docker/HTTP/TCP DOWN; restart recovered; loss of Engine API preserved inventory as UNKNOWN and cleared old runtime/health/metrics |
| Live browser / Docker | PASS | Authenticated Services/Containers, details, six check cards, 1080p fit and persistent hidden-screen preference |
| Public material | PASS in publication preparation | Synthetic captures, relative documentation links, clean-history and directory Gitleaks checks |
| npm advisories | No reported vulnerabilities | `npm audit --audit-level=high --json` against the current lockfile |
| Python package advisories | No advisories returned | PyPI version metadata for `gunicorn==26.2.0` and `packaging==26.3`; not a scan of image OS packages |
| Agent prompt | Written and reviewed | Bilingual instructions, source coverage, local credentials, authorized scope, verification and recovery; no real unattended installation test |

PyPI sources: [Gunicorn version metadata](https://pypi.org/pypi/gunicorn/26.2.0/json)
and [packaging version metadata](https://pypi.org/pypi/packaging/26.3/json).
Advisory results are a point-in-time observation, not a guarantee of security.

## Before announcing the first public preview

1. **Docker path verified locally.** Build, Compose startup, restricted tools,
   native checks and real Engine reads passed in an isolated Linux lab. No company
   monitoring credentials, inventory or target devices were used. Temporary
   containers, network and generated test credentials/certificates were removed.
   This does not certify every OS, runtime or firewall API.
2. **GitHub Checks passed** on commit `fe7ed08`:
   [run 39778422662](https://github.com/WeslleyDorta/NOCtv/actions/runs/39778422662).
   This includes Python tests, browser checks, image build and container startup.
   Future changes have their own workflow results; this record does not certify them.
3. **Publish the clean community repository and a clearly labeled preview.**
   The community commits are now on the personal repository. Retain licensing/asset notices and the
   connector coverage matrix. The [presentation guide](github-presentation.md)
   contains the description, topics and announcement draft.

A public preview may document connectors as fixture-tested. Validation against
every supported product is not a prerequisite for sharing source code, but it is
required before claiming those combinations are proven in real deployments.

## Highest-value tests with early users

- **One real source at a time:** start with LibreNMS or Zabbix using a limited
  read-only lab account. Compare representative state, units, timestamps and site
  mappings across two cycles. Then add another source and check duplicate identity.
- **Native services and Docker:** repeat the recorded lab scenarios on the user
  installation. A controlled unhealthy application healthcheck remains a useful
  addition: this lab tested a healthy check, stopped runtime and API loss; unhealthy
  payloads are currently covered by fixtures. Missing CPU deltas remain unavailable
  rather than being invented; the live Engine check verified memory, not CPU values.
- **Long-running TV:** leave a dedicated browser rotating through selected screens
  for a working day. Observe memory, refresh cadence, readability, reconnects and
  preference persistence. Long-duration behavior and fleet capacity are not yet measured.
- **Agent-guided first install:** ask someone with a clean host to use
  [the copy-and-paste prompt](install-prompt.md). Record confusing questions,
  missing dependencies and setup time without collecting their secrets. Test the
  documented supported path before adding more installer features.

Use [the handover criteria](install-prompt.md#what-a-completed-installation-should-report)
for each installation. Mark checks verified, pending or not applicable. Keep actual
addresses, credentials, inventory and private test evidence out of this repository.
