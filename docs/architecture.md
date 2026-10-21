# NOCtv community architecture

NOCtv is a self-hosted display layer for existing monitoring systems. A fresh
repository contains only reusable source and synthetic examples, with no copied
operational Git history, configuration, screenshots or collected inventory.

## First release (0.1)

- Docker Compose demo without credentials or external network dependencies.
- Seven display views: connections, switches, ports, servers, printers, wireless,
  and other devices. Site and port dialogs, source freshness, a notification ticker,
  reduced motion, and automatic screen rotation.
- JSON configuration for sites, locations, device classification, topology roots,
  collection periods and display limits. No environment-specific constants.
- Read-only LibreNMS HTTP API and optional Forcepoint SMC 7.2 connector.
- A normalized, versioned snapshot shared by every viewer. One polling thread per
  connector; browser requests never trigger upstream API calls.
- Unknown/stale is distinct from down. Unused down ports do not imply critical
  incidents. Port alerts require explicit configuration of required ports.
- Secrets enter only through environment variables; the browser receives an
  allowlisted display configuration and normalized operational data.

## Boundaries

`config.py` validates configuration. `connectors/` returns normalized devices and
links. `collector.py` schedules sources independently and keeps last-known data
with explicit source state. `server.py` serves the API and the static interface.
The interface uses only `/api/v1/config` and `/api/v1/snapshot`.

Device IDs are namespaced by source. No automatic cross-source identity merge is
attempted: configure which source owns a device. Links require evidence from a
connector; schematic layout must not fabricate network relationships.

## Deliberate limits

Single-process, in-memory current state, with no history database or high
availability. Use one Gunicorn worker with threads. Optional metrics appear only
when provided. Generic interface diagrams are not manufacturer faceplates.
The project does not install LibreNMS or scan/configure network equipment.
New vendors should normally enter through LibreNMS; dedicated integrations use
the connector contract. Zabbix, UniFi, Redfish and hypervisor adapters are future
contributions, not advertised as implemented integrations.

## Validation

Unit and fixture tests cover normalization, partial failures, stale data,
configuration, credentials and URL boundaries. Browser tests cover all views,
site/device/port interaction, keyboard controls, motion preferences and TV fit.
Publication requires a clean-history secret scan and a review for identifying
operational strings. Runtime integrations are tested against synthetic HTTP
fixtures, never against a contributor's private infrastructure by default.
