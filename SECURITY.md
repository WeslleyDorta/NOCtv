# Security

Run public demonstrations in demo mode. Live snapshots contain network inventory;
treat them as private operational data. Live mode requires viewer credentials and
should be exposed only through HTTPS plus network access controls. The default
Compose binds to localhost. Do not share real configs, `.env`, credentials,
inventory, captures or API response dumps in issues.

Credentials stay on the collector side. Display config is allowlisted. Connectors
verify TLS, reject credential redirects and bound responses/timeouts. The web
service exposes no configuration mutation or remote-command endpoint. Polling
credentials should be read-only. Rejected authentication stops that source until
restart. NOCtv does not perform scans or change devices.

Use GitHub's private vulnerability reporting for this repository when available.
If unavailable, contact the maintainer privately before publishing exploit details.
Never include live credentials in a report.

The 0.1 release has automated fixture and browser checks, but is not a security
certification, firmware compatibility certification or load-tested enterprise
platform. Keep Python, Gunicorn, dependencies and your monitoring systems updated.
