# Changelog

## 0.1.0 — Community preview — 2026-10-22

- Adapt equipment card columns and detail to available TV space; prioritize
  incidents and summarize overflow with access to the full inventory.
- Publish a 75-second animated tour with English and Portuguese captions,
  chapters and synthetic data, plus an agent-guided installation prompt.

- Add Services and Containers screens; hide/show screens per browser, excluding
  hidden screens from TV rotation while retaining collection and global alerts.
- Add explicit HTTP/HTTPS, TCP, DNS and ping checks plus read-only Docker runtime,
  healthcheck, restart and optional resource collection. Expand demo to 38 items.
- Restore the toolbar: Tools, opt-in sound, notifications, manual refresh,
  TV profile, update time and persistent base rotation duration.
- Bundle portable diagnostic tools in Docker, disabled by default in live mode,
  with explicit CIDR targets and simulated demo results. Kali is not required.

- Restore the compact NOC display: three-column connections, large geographic map,
  branch topology, two port panels, host resources, printer supplies, Wi-Fi readings
  and grouped device cards. Keep the shared navigation/ticker.
- Bundle Brazil state boundaries and highlight only regions containing configured sites.
- Show per-view summaries and collected session history; preserve unknown values.
- Include an offline synthetic scenario with a required-port incident.
- Restore unit details with compact inventory, firewall interfaces/services and VPN readings.
- Remove stale server hardware/storage readings after source or browser connection failures.
- Verify port state changes in both the switch miniature and open detail dialog.

- Read-only Prometheus probe/metric and NetBox inventory adapters, fixture tests,
  examples and integration research; Uptime Kuma supported indirectly through
  its documented Prometheus export.

- Offline country/world maps with 240 country/territory entries, shared geographic
  projection, explicit coordinates and backward-compatible schematic layouts.

- Shared `AGENTS.md` instructions, a `CLAUDE.md` import and an agent-guided
  installation runbook for demo/live setup, source checks and recovery.

### Core capabilities

- Configurable sites, device categories, source schedules and TV views.
- Synthetic demo with connections, switch interfaces and incident examples.
- Read-only LibreNMS, Zabbix and Forcepoint adapters.
- Optional firewall inventory/management adapters for FortiGate, PAN-OS,
  Check Point and Sophos Central.
- Manufacturer recognition and attributed local logos.
- Source freshness, required-interface alerts, authentication in live mode,
  connector fixtures and browser checks.

Live firmware compatibility and capacity limits have not been established.
