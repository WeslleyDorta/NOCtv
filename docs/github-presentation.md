# Repository presentation

This file contains proposed repository metadata and publication steps. It does
not change GitHub settings or indicate that a release has been published.

## About description

> Self-hosted NOC dashboard for TVs: network maps, switch topology, service checks and Docker health. Connect LibreNMS, Zabbix or Prometheus.

## Topics

`network-monitoring`, `noc`, `dashboard`, `self-hosted`, `network-topology`,
`librenms`, `zabbix`, `prometheus`, `docker`, `uptime-monitoring`, `homelab`,
`sysadmin`, `python`

These describe the current scope. GitHub uses topics to group related projects
and supports searching by topic. Add them through the repository's About settings;
see [GitHub's topic documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics).

## First public preview

- Confirm the destination and authenticated account belong to the maintainer.
- Publish the clean community history; never copy operational history or media.
- Let the existing Checks workflow finish, including the Docker build/smoke test.
  Local fixture/browser tests do not establish that the GitHub run passed.
- Publish a community preview release with supported capabilities and known limits
  from the integration matrix. Avoid claiming production certification or full
  Uptime Kuma parity.
- Enable private vulnerability reporting in GitHub settings before directing users
  there. Do not use public issues to collect secrets or security-sensitive reports.
- Set the About description/topics and pin the repository on the maintainer profile.
  Use only synthetic demo captures when sharing the project.

The README introduces the product, demo and source-specific setup. The
[screen tour](tour.md) contains the full gallery. The two issue templates ask for
reproducible reports and official integration documentation. This structure follows
[GitHub's README guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes).

## Announcement draft

### English

I built NOCtv to keep network operations visible on a TV: site connections, switch
topology, port states and an alert ticker, with an automatic screen rotation.

The community preview includes LibreNMS, Zabbix and Prometheus adapters, native
service checks and Docker health monitoring. You can try the interface with
fictional data before connecting your own environment.

I'm looking for feedback from people running small NOCs and homelabs, especially
on connector compatibility and TV readability. The repository documents what each
adapter can collect and how to add another one.

### Português

Desenvolvi o NOCtv para acompanhar a operação da rede pela TV: conexões entre
unidades, topologia dos switches, estado das portas e alertas, com troca automática
das telas.

Estou preparando uma versão comunitária para quem quiser adaptar ao próprio
ambiente. Ela tem integração com LibreNMS, Zabbix e Prometheus, além de checks de
serviços e monitoramento de containers. Dá para testar a interface com dados
fictícios antes de conectar qualquer equipamento.

Quero ouvir quem trabalha com NOC ou mantém um laboratório: o que seria mais útil
no seu dia a dia? O repositório explica os dados disponíveis em cada integração e
como contribuir com outras.

Add the public repository link only after confirming it is accessible and the
published instructions match the released code. Reach depends on usefulness,
feedback and maintenance; these materials do not guarantee stars or adoption.
