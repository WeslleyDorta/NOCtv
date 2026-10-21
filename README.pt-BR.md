# NOCtv

Painel de monitoramento de rede para TVs e operações de NOC. Reúne dados do
LibreNMS, Zabbix e APIs de firewalls em telas de conexões, switches, portas,
servidores, impressoras, Wi-Fi e dispositivos.

[English](README.md) · [Instalação](docs/setup.md) · [Integrações](docs/integrations.md)

![Demonstração com dados fictícios](docs/images/connections.png)

## Executar a demonstração

```sh
git clone https://github.com/WeslleyDorta/NOCtv.git
cd NOCtv
docker compose up --build -d
```

Acesse **http://localhost:8080**. Requer Docker e Compose 2.24 ou superior.
A demonstração funciona sem credenciais e sem consultar equipamentos reais.
Como alternativa local, use Python 3.12+: `python3 -m noctv serve`.

## Adaptar

1. Copie `.env.example` para `.env`.
2. Copie `config/live.example.json` para `config/local.json`.
3. Configure unidades, posições no mapa e fontes de dados.
4. Coloque credenciais somente no ambiente; o JSON referencia nomes de variáveis.
5. Defina `NOCTV_CONFIG_FILE=./config/local.json`, `NOCTV_USER` e uma senha exclusiva
   com pelo menos 16 caracteres em `NOCTV_PASSWORD`.
6. Valide: `python3 -m noctv check --config config/local.json`.
7. Reinicie: `docker compose up -d --force-recreate`.

A publicação inicial é uma **prévia comunitária 0.1**. Os conectores têm testes com
respostas simuladas; a compatibilidade com cada firmware precisa ser validada no
seu ambiente. A interface está em inglês nesta versão.

LibreNMS e Zabbix permitem aproveitar o monitoramento que você já possui, inclusive
para equipamentos de diferentes fabricantes. Métricas dependem dos dados da
fonte. Zabbix usa mapeamentos explícitos para portas e métricas fora dos padrões
documentados. As APIs diretas de FortiGate/PAN-OS/Check Point/Sophos têm escopo de
inventário e gerenciamento; isso não comprova o estado das VPNs ou do tráfego.

O diagrama de portas é genérico. Os nomes dos vizinhos aparecem quando há evidência
de descoberta; nomes de interfaces não são tratados como prova da conexão.
Portas DOWN só geram alerta crítico quando marcadas como obrigatórias.

São reconhecidas 25 marcas, com 13 logos redistribuíveis incluídas. Nos demais
casos, o sistema usa um ícone genérico. Identificação não equivale a certificação
de compatibilidade.

O modo real exige autenticação. Para acesso remoto, use HTTPS e controle de acesso;
o Compose publica apenas em localhost por padrão. Não publique o inventário da
sua organização em uma demonstração aberta.

Criado por **[Weslley Dorta](https://github.com/WeslleyDorta)**. Código sob licença
[MIT](LICENSE); fontes e marcas têm licenças próprias.
