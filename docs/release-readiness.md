# Community preview validation record

Recorded on 2026-10-22 for application code at `3620082` (runtime feature commit
`ac095ea`). Later changes in this documentation pass add installation prompts and
this record; they do not change application behavior. Re-run relevant checks when
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
| Compose structure | PASS | `docker compose config --quiet`; not an image build |
| Public material | PASS in publication preparation | Synthetic captures, relative documentation links, clean-history and directory Gitleaks checks |
| npm advisories | No reported vulnerabilities | `npm audit --audit-level=high --json` against the current lockfile |
| Python package advisories | No advisories returned | PyPI version metadata for `gunicorn==26.2.0` and `packaging==26.3`; not a scan of image OS packages |
| Agent prompt | Written and reviewed | Bilingual instructions, source coverage, local credentials, authorized scope, verification and recovery; no real unattended installation test |

PyPI sources: [Gunicorn version metadata](https://pypi.org/pypi/gunicorn/26.2.0/json)
and [packaging version metadata](https://pypi.org/pypi/packaging/26.3/json).
Advisory results are a point-in-time observation, not a guarantee of security.

## Before announcing the first public preview

1. **Complete the Docker path.** The local daemon was unavailable during this
   verification. Build the image on a clean Docker host, start the included Compose
   demo and confirm health, inventory and UI. Check the bundled tools run under
   UID 10001 with the supplied restrictions, using an isolated authorized lab.
   Demo diagnostic output is simulated and cannot prove binary permissions.
2. **Run GitHub Checks on the actual published commit.** The workflow includes
   browser checks, image build and container smoke testing. Local success does
   not mean GitHub CI has run. Do not advertise a passing remote build beforehand.
3. **Publish the clean community repository and a clearly labeled preview.**
   Use the intended personal account, retain licensing/asset notices and the
   connector coverage matrix. The [presentation guide](github-presentation.md)
   contains the description, topics and announcement draft.

A public preview may document connectors as fixture-tested. Validation against
every supported product is not a prerequisite for sharing source code, but it is
required before claiming those combinations are proven in real deployments.

## Highest-value tests with early users

- **One real source at a time:** start with LibreNMS or Zabbix using a limited
  read-only lab account. Compare representative state, units, timestamps and site
  mappings across two cycles. Then add another source and check duplicate identity.
- **Native services and Docker:** use disposable lab services to exercise UP,
  failed check, TLS warning, healthcheck failure and source-unavailable behavior.
  Confirm missing/disabled tools appear as unavailable, not healthy.
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
