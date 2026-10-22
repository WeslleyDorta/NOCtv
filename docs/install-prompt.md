# Copy-and-paste installation prompt

[Português](#português) · [English](#english) · [Detailed runbook](agent-install.md)

Clone NOCtv and open its folder in your coding agent. The agent needs terminal/file
access to the installation host, or an authorized remote session. A chat without
that access can guide you but cannot perform installation. Use either prompt below;
replace the optional context with what you already know. Leave secrets out.

`AGENTS.md` contains project instructions; `CLAUDE.md` imports them. The prompt
explicitly requests both the project rules and installation guide so it also works
with tools that do not load those files automatically. NOCtv does not require an
AI account, agent or API key at runtime.

## Português

```text
Quero instalar e adaptar o NOCtv deste repositório ao meu ambiente.
Leia AGENTS.md, docs/agent-install.md e docs/integrations.md antes de agir.
Responda em português e execute o trabalho dentro do escopo combinado.

Contexto opcional, sem segredos:
- Instalação: [laboratório / servidor / computador local; SO se souber]
- Fontes existentes: [LibreNMS / Zabbix / Prometheus / firewalls / Docker / nenhuma]
- Objetivo: [TV de NOC / laboratório / demonstração]
- Unidades e mapa: [país ou mapa mundial; sem endereços privados]
- Acesso: [somente local / TV na rede com proxy HTTPS existente]
- Resolução e telas desejadas: [1080p / 4K; telas que pretendo usar]

1. Inspecione a pasta, alterações locais, sistema, Docker/Compose ou Python,
   acesso ao daemon, portas disponíveis e eventual instalação já existente.
   Preserve o que encontrar. Não pare outros serviços para liberar uma porta.
2. Pergunte apenas o que estiver faltando para escolher demonstração ou fontes
   reais, local de instalação e escopo autorizado. Se eu não tiver uma fonte
   definida, comece com a demonstração isolada e sem acessar equipamentos.
3. Consulte o guia de cada conector escolhido. Explique quais dados ele coleta
   e suas limitações. Não prometa topologia ou métricas que não existam na fonte.
4. Prefira os conectores e exemplos já presentes. Prepare somente os arquivos
   locais necessários, preservando e fazendo backup privado dos existentes.
   Não edite o código da aplicação para personalizar nomes, unidades ou telas.
   Se faltar uma capacidade, explique a lacuna antes de propor desenvolvimento.
5. Oriente-me a preencher credenciais no editor local ou cofre de segredos.
   Nunca solicite chaves/senhas no chat nem imprima .env, tokens ou inventário.
   Use acesso de leitura e TLS verificado. Não monte um socket Docker irrestrito.
6. Configure unidades, categorias, fontes, intervalos, telas e rodízio conforme
   minhas escolhas. Para mapas, peça coordenadas; não deduza localização de IP.
   Não duplique o mesmo dispositivo entre fontes sem explicar essa escolha.
   Kali não é obrigatório; use as ferramentas incluídas na imagem quando houver
   Docker. Instale dependências no host só se isso fizer parte do escopo autorizado.
7. Valide a configuração e inicie apenas esta instalação. Em modo real, configure
   autenticação. Para acesso pela rede, use HTTPS. Não abra portas, altere firewall,
   execute varreduras ou ative checks de novos destinos fora do escopo autorizado.
8. Verifique separadamente: aplicação acessível, fontes coletando e dados corretos.
   Compare um equipamento/serviço representativo com a origem, incluindo estado,
   unidade, timestamp e unidade/site. Confirme atualização em dois ciclos.
   Teste telas, detalhe de porta quando disponível, rodízio e ocultação persistente.
   Não desligue equipamentos para simular falhas; use a demonstração para isso.
9. Encerre com URL local, arquivos alterados, fontes verificadas, intervalos,
   limitações e instruções para parar/restaurar somente esta instalação.
   Classifique cada resultado como verificado, pendente ou não aplicável.
   Não declare integração funcionando só porque a demo, /healthz ou config check passou.

Não publique configurações nem envie dados do ambiente ao GitHub. Prossiga com
as etapas já autorizadas e peça esclarecimento somente quando faltar uma decisão
necessária. Se um teste estiver bloqueado, explique a causa e o próximo passo.
```

## English

```text
Install and adapt NOCtv from this repository to my environment.
Read AGENTS.md, docs/agent-install.md and docs/integrations.md first.
Respond in English and work within the agreed scope.

Optional context, without secrets:
- Installation: [lab / server / local computer; OS if known]
- Existing sources: [LibreNMS / Zabbix / Prometheus / firewalls / Docker / none]
- Goal: [NOC TV / homelab / demonstration]
- Sites and map: [country or world; no private addresses]
- Access: [localhost / network TV with an existing HTTPS proxy]
- Resolution and screens: [1080p / 4K; views I want to use]

1. Inspect the repository, local changes, OS, Docker/Compose or Python, daemon
   access, available ports and any existing installation. Preserve existing work.
   Do not stop unrelated services to free a port.
2. Ask only for missing choices needed to select demo/live sources, the installation
   host and authorized scope. If no source is selected, start an isolated demo
   without contacting equipment.
3. Read each selected connector guide and explain its actual data coverage and
   limitations. Do not promise topology or metrics the source cannot provide.
4. Use existing adapters and examples. Prepare only necessary local configuration,
   preserving existing files with private backups. Do not modify application code
   to customize names, sites or screens. Explain unsupported capabilities before
   proposing development.
5. Guide me to enter credentials in a local editor or secret store. Never request
   passwords/keys in chat or print .env, tokens or inventory. Use read-only source
   permissions and verified TLS. Do not mount an unrestricted Docker socket.
6. Configure sites, categories, sources, intervals, screens and rotation from my
   choices. Ask for map coordinates rather than inferring location from IPs.
   Avoid collecting the same device twice without explaining the choice. Kali is
   not required; use image-bundled tools with Docker. Install host dependencies
   only when already authorized within the installation scope.
7. Validate configuration and start only this installation. Enable live viewer
   authentication and use HTTPS for network access. Do not expose ports, alter
   firewalls, scan networks or activate checks outside the authorized target scope.
8. Verify application access, source collection and data separately. Compare a
   representative device/service with its source, including state, metric units,
   timestamp and site. Observe two collection cycles. Check screens, port details
   where supported, rotation and persisted hidden-screen preferences. Never turn
   off real equipment to create a test outage; use the demo for failure scenarios.
9. Hand over the local URL, changed files, verified sources, intervals, limitations
   and instructions to stop/restore only this installation. Mark results verified,
   pending or not applicable. A working demo, /healthz or config check alone does
   not prove that a live integration works.

Do not publish local configuration or send environment data to GitHub. Continue
already authorized work; clarify only missing decisions. If a test is blocked,
state the cause and the next step instead of claiming success.
```

## What a completed installation should report

| Item | Evidence to report without secrets |
| --- | --- |
| Installation | Selected method, version/commit, local access URL |
| Source | Connector type/API version, success or pending reason |
| Data | Representative comparison and two observed collection cycles |
| Display | Selected views, resolution, rotation and persisted preferences |
| Protection | Viewer authentication, HTTPS where needed, private files ignored |
| Recovery | Private backup location and commands limited to this installation |
| Gaps | Unsupported readings, missing dependencies and unverified behavior |

Private details belong in the operator's local configuration and handover, never
in committed examples, public issues, `AGENTS.md` or `CLAUDE.md`. Prompt compliance
still depends on the chosen agent; these instructions do not enforce permissions.
