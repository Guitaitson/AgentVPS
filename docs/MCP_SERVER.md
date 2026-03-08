# MCP Server

## Visão Geral

O MCP Server do AgentVPS expõe endpoints HTTP e endpoint MCP (`/mcp`) para operação da VPS.

- Implementação: `core/mcp_server.py`
- Serviço systemd: `configs/mcp-server.service`
- Bind padrão: `127.0.0.1`
- Porta padrão: `8765`

## Configuração

No arquivo `/opt/vps-agent/.env`:

```env
MCP_HOST=127.0.0.1
MCP_PORT=8765
MCP_API_KEY=troque-por-uma-chave-forte
```

`MCP_API_KEY` é opcional, mas recomendado. Quando definido, o servidor exige header `X-API-Key` em todas as rotas não públicas.

## Endpoints

- `GET /health`
- `GET /ram`
- `GET /containers`
- `GET /tools`
- `POST /tools/{tool_name}/start`
- `POST /tools/{tool_name}/stop`
- `GET /services`
- `GET /system`
- `POST/GET /mcp` (montado via FastAPI-MCP)

## Instalação (systemd)

```bash
sudo cp /opt/vps-agent/configs/mcp-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mcp-server
```

## Testes Rápidos

Sem autenticação:

```bash
curl http://127.0.0.1:8765/health
```

Com autenticação:

```bash
curl -H "X-API-Key: $MCP_API_KEY" http://127.0.0.1:8765/containers
```

## Acesso Remoto Seguro

Use túnel SSH, sem expor porta publicamente:

```bash
ssh -L 8765:localhost:8765 <USUARIO>@<SEU_HOST_VPS>
```

## Observações de Segurança

- Não publique host real, usuário, senha, token ou e-mail pessoal em docs.
- Prefira `MCP_HOST=127.0.0.1` e acesso remoto via túnel.
- Evite rodar sem `MCP_API_KEY` em ambientes compartilhados.
