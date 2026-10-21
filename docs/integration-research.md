# Integration choices

This review considers how other monitoring projects expose useful data, rather
than copying their interfaces. NOCtv keeps its current cards, topology, geographic
maps, site dialogs and TV rotation. Adapters normalize data into the same contract.

| Project | Useful source capability | NOCtv approach |
| --- | --- | --- |
| [LibreNMS](https://docs.librenms.org/API/) | Network inventory, ports and discovered links | Existing direct read-only adapter |
| [Zabbix](https://www.zabbix.com/documentation/7.0/en/manual/api) | Host monitoring and template items | Existing direct adapter with explicit metric/port mappings |
| [Prometheus](https://prometheus.io/docs/prometheus/latest/querying/api/) | Time series from exporters and probes | Read-only selector adapter, preserving source sample timestamps |
| [Uptime Kuma](https://github.com/louislam/uptime-kuma/wiki/Prometheus-Integration) | Monitor status and response-time metrics | Consume metrics already scraped into Prometheus; no direct Kuma connector |
| [NetBox](https://netboxlabs.com/docs/netbox/integrations/rest-api/) | Structured device/site inventory | Read-only inventory adapter; lifecycle status never becomes operational UP |
| [Checkmk](https://docs.checkmk.com/latest/en/rest_api.html) | Versioned API for monitoring/configuration operations | Evaluated, not implemented; needs a version-specific read-only contract and fixtures |

Prometheus adds an established path for many exporters without a separate
manufacturer-specific client for each one. The adapter is deliberately limited
to configured selectors: it does not import every metric or Grafana dashboard.
Exporter `up` means the scrape succeeded, not that the monitored device or service
is operational. Use a supported probe/status measurement for that claim.

Uptime Kuma's documented Prometheus export avoids depending on its
[internal API](https://github.com/louislam/uptime-kuma/wiki/API-Documentation),
which its own documentation warns is not a stable third-party contract.
The operator must already have Prometheus scraping Kuma; NOCtv does not configure
that server or add a second scraper. Metric names, labels and units must match
the actual exporter version.

NetBox adds inventory context. It does not replace a poller, and the initial
adapter does not merge inventory with a matching LibreNMS/Zabbix device. To avoid
duplicate cards, use separate source scopes. Device roles require explicit NOCtv
category mappings; a name containing "switch" is not a reliable classification.

For the implemented scope and test limits, see [the integration matrix](integrations.md),
[Prometheus configuration](prometheus.md) and [NetBox configuration](netbox.md).
All adapters remain fixture-tested until verified against an operator's deployment.

Future integrations should bring a documented read interface, useful timestamps,
clear state semantics, credential isolation and representative synthetic fixtures.
An integration logo or a successful API login is not sufficient evidence of support.
