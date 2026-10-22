# Contributing

Open an issue describing the monitoring problem and the source API/version.
Use synthetic fixtures and documentation links; remove addresses, domain names,
serials, usernames and secrets belonging to a real environment.

Prefer one connector or behavior per pull request. Follow the normalized
[contract](docs/connector-contract.md), preserve upstream timestamps, document
capabilities, and add tests for malformed/missing/stale data. Do not label a device
healthy just because the management API returned HTTP 200.

```sh
python3 -m unittest discover -s tests -v
python3 -m noctv check
npm ci
npx playwright install chromium
npm test
```

Browser checks launch an isolated demo on localhost:8766 and localhost:8768, generate screenshots
under ignored `artifacts/`, and make no live source requests. A running instance on
either test port must be stopped first. The interface has no frontend build step.

For logos, document redistribution permission, preserve attribution and trademark
notices, and reject SVG scripts/external references. A generic icon is preferable
to an invented or unlicensed logo. Contributors retain copyright in their work;
contributions are submitted under this repository's MIT license.
