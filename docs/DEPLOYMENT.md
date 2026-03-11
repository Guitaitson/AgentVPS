# Guia de Deploy — AgentVPS

> **Versão:** 3.0 — 26/02/2026
> **Testado em:** Debian 12 (RackNerd VPS), Docker 29.2.1

---

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Configuração Inicial da VPS](#configuração-inicial-da-vps)
3. [Instalar e Configurar](#instalar-e-configurar)
4. [Subir Containers](#subir-containers)
5. [Instalar Serviços Systemd](#instalar-serviços-systemd)
6. [Verificação Pós-Deploy](#verificação-pós-deploy)
7. [Manutenção](#manutenção)
8. [Troubleshooting](#troubleshooting)

---

## Pré-requisitos

### VPS

- Sistema: Debian 12 / Ubuntu 22.04+ (recomendado)
- RAM: mínimo 1 GB (2 GB confortável)
- Disco: mínimo 10 GB livre
- Docker instalado: `curl -fsSL https://get.docker.com | sh`
- Acesso SSH com sudo

### Credenciais Necessárias

| Credencial | Como Obter |
|------------|-----------|
| Telegram Bot Token | [@BotFather](https://t.me/BotFather) → `/newbot` |
| Telegram User ID | [@userinfobot](https://t.me/userinfobot) |
| OpenRouter API Key | [openrouter.ai/keys](https://openrouter.ai/keys) |

---

## Configuração Inicial da VPS

```bash
# 1. Criar usuário dedicado (opcional, boa prática)
adduser vps_agent
usermod -aG docker vps_agent

# 2. Criar diretório da aplicação
mkdir -p /opt/vps-agent
chown vps_agent:vps_agent /opt/vps-agent

# 3. Clonar repositório
cd /opt/vps-agent
git clone https://github.com/Guitaitson/AgentVPS.git .

# 4. Criar diretório de logs
mkdir -p /opt/vps-agent/logs
```

---

## Instalar e Configurar

### Python + Dependências

```bash
python3 -m venv /opt/vps-agent/core/venv
/opt/vps-agent/core/venv/bin/pip install --upgrade pip
/opt/vps-agent/core/venv/bin/pip install -e ".[dev]"
```

### Variáveis de Ambiente

```bash
# Copiar template
cp /opt/vps-agent/configs/.env.example /opt/vps-agent/.env

# Editar com credenciais reais
nano /opt/vps-agent/.env

# Proteger o arquivo
chmod 600 /opt/vps-agent/.env
chown root:root /opt/vps-agent/.env
```

**Variáveis mínimas obrigatórias** em `/opt/vps-agent/.env`:

```env
TELEGRAM_BOT_TOKEN=seu-token-aqui
TELEGRAM_ALLOWED_USERS=seu-id-numerico
POSTGRES_USER=vps_agent
POSTGRES_PASSWORD=senha-forte-aqui
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=vps_agent
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
OPENROUTER_API_KEY=sua-chave-openrouter-aqui
OPENROUTER_MODEL=minimax/minimax-m2.5
OPENROUTER_MAX_TOKENS=2048
OPENROUTER_TIMEOUT=30
OPENROUTER_TEMPERATURE=0.7
MCP_HOST=127.0.0.1
MCP_PORT=8765
MCP_API_KEY=troque-por-uma-chave-forte
VOICE_CONTEXT_ENABLED=true
VOICE_CONTEXT_USER_ID=seu-id-telegram
VOICE_CONTEXT_INBOX_DIR=/opt/vps-agent/data/voice/inbox
VOICE_CONTEXT_PROCESSING_DIR=/opt/vps-agent/data/voice/processing
VOICE_CONTEXT_ARCHIVE_DIR=/opt/vps-agent/data/voice/archive
VOICE_CONTEXT_FAILED_DIR=/opt/vps-agent/data/voice/failed
VOICE_CONTEXT_TRANSCRIPTS_DIR=/opt/vps-agent/data/voice/transcripts
VOICE_CONTEXT_BATCH_HOUR=2
VOICE_CONTEXT_AUTO_COMMIT_THRESHOLD=0.75
VOICE_CONTEXT_TRANSCRIPT_TTL_DAYS=7
WHISPER_MODEL_SIZE=tiny
WHISPER_DEVICE=cpu
```

---

## Subir Containers

```bash
# Subir PostgreSQL + Redis
cd /opt/vps-agent
docker compose -f configs/docker-compose.core.yml up -d

# Verificar saúde
docker ps
docker exec vps-postgres pg_isready -U vps_agent
docker exec vps-redis redis-cli ping  # deve retornar PONG
```

### Aplicar Schema do Banco

```bash
# Schema inicial
docker exec -i vps-postgres psql -U vps_agent -d vps_agent \
  < /opt/vps-agent/configs/init-db.sql

# Tabelas autônomas (proposals, missions)
docker exec -i vps-postgres psql -U vps_agent -d vps_agent \
  < /opt/vps-agent/configs/migration-autonomous.sql

# Migration: memória tipada auditável + soul governance
docker exec -i vps-postgres psql -U vps_agent -d vps_agent \
  < /opt/vps-agent/configs/migration-memory-soul.sql

# Migration: catálogo de skills externos
docker exec -i vps-postgres psql -U vps_agent -d vps_agent \
  < /opt/vps-agent/configs/migration-skills-catalog.sql

# Migration: voice context capture
docker exec -i vps-postgres psql -U vps_agent -d vps_agent \\
  < /opt/vps-agent/configs/migration-voice-context.sql

# Verificar tabelas criadas
docker exec vps-postgres psql -U vps_agent -d vps_agent \
  -c "\dt" | grep agent
```

---

## Instalar Serviços Systemd

```bash
# Copiar service files
cp /opt/vps-agent/configs/telegram-bot.service /etc/systemd/system/
cp /opt/vps-agent/configs/mcp-server.service /etc/systemd/system/

# Recarregar e habilitar
systemctl daemon-reload
systemctl enable telegram-bot mcp-server
systemctl start telegram-bot mcp-server

# Verificar status
systemctl status telegram-bot mcp-server

# Permitir execucao manual do app como usuario de servico sem expor o .env ao usuario de login
chgrp vps_agent /opt/vps-agent/.env
chmod 640 /opt/vps-agent/.env
```

### Deploy Automatico por Release

Existe suporte para deploy automatico quando uma release do GitHub e publicada:

```text
.github/workflows/release-deploy.yml
scripts/deploy_release.sh
```

Secrets necessarios no GitHub:

```text
VPS_HOST
VPS_USER
VPS_SSH_KEY
VPS_KNOWN_HOSTS   # opcional, mas recomendado
```

O fluxo faz:
- `git pull --ff-only` em `main`
- `pip install -e ".[dev,voice]"`
- aplica migrations idempotentes
- sobe/atualiza o Qdrant
- reinstala os units systemd versionados
- reinicia `telegram-bot` e `mcp-server`

Protecoes atuais:
- se houver processamento de voz em andamento, o deploy nao reinicia os servicos
- nesse caso, o script agenda nova tentativa automatica alguns minutos depois
- isso evita quebrar transcricao/ingestao longa por causa de release publicada

Seguranca dos secrets do GitHub:
- secrets de Actions nao ficam publicos no repositorio
- eles ficam cifrados e so sao expostos ao runtime do workflow
- ainda assim, vazam se um workflow imprimir os valores ou enviar para fora
- por isso, workflows de deploy devem ser curtos, revisados e sem execucao de codigo nao confiavel

---

## Verificação Pós-Deploy

```bash
# 1. Serviços rodando
systemctl is-active telegram-bot mcp-server
# → active active

# 2. Logs limpos (sem erros)
tail -20 /opt/vps-agent/logs/telegram-bot.log

# 3. Skills carregadas (deve mostrar 15)
PYTHONPATH=/opt/vps-agent /opt/vps-agent/core/venv/bin/python3 -c "
from core.skills.registry import SkillRegistry
r = SkillRegistry(['/opt/vps-agent/core/skills/_builtin'])
r.discover_and_register()
print('Skills:', r.count)
print(list(r._skills.keys()))
"

# 4. PostgreSQL acessível
docker exec vps-postgres psql -U vps_agent -d vps_agent -c "SELECT COUNT(*) FROM agent_memory;"
```

### Teste via Telegram

Mande `/status` para o bot. Se responder com info da VPS, tudo está funcionando.

---

## Manutenção

### Atualizar Código

```bash
cd /opt/vps-agent
git pull origin main
/opt/vps-agent/core/venv/bin/pip install -e ".[dev]"
systemctl restart telegram-bot mcp-server
```

### Ver Logs em Tempo Real

```bash
# Telegram bot
tail -f /opt/vps-agent/logs/telegram-bot.log

# Ou via journalctl
journalctl -u telegram-bot -f

# MCP server
journalctl -u mcp-server -f
```

### OperaÃ§Ã£o do Updater

Comandos uteis no Telegram:

- `/catalogsync check [source]` - verifica mudancas no catalogo sem aplicar
- `/catalogsync apply [source]` - aplica mudancas detectadas
- `/catalogsync pin <skill> [source] [version]` - fixa versao de skill
- `/catalogsync unpin <skill> [source]` - remove fixacao
- `/catalogsync rollback <skill> [source] [target_version]` - rollback para versao anterior
- `/catalogsync provenance <skill> [source] [limit]` - historico de versoes e origem
- `/runtimes [list|enable|disable]` - gerencia runtimes externos
- `/contextsync` - processa audios pendentes da inbox de voz
- `/contextstatus` - mostra ultimo job, inbox e revisoes pendentes
- `/updatestatus` - status do updater autonomo e ultimo sync
- `/proposals` e `/proposal <id>` - inspeciona proposals de update


### Janela de ManutenÃ§Ã£o (Scheduled Updates)

Exemplo 1: aprovar proposals de update (sem burlar `requires_approval=true`):

```bash
docker exec vps-postgres psql -U vps_agent -d vps_agent -c "
INSERT INTO scheduled_tasks (task_name, task_type, payload, status, next_run)
VALUES (
  'janela-update-approve',
  'once',
  '{\"action\":\"approve_update_proposals\",\"limit\":20,\"include_requires_approval\":false}',
  'pending',
  NOW() + INTERVAL '30 minutes'
);"
```

Exemplo 2: aplicar catÃ¡logo diretamente na janela:

```bash
docker exec vps-postgres psql -U vps_agent -d vps_agent -c "
INSERT INTO scheduled_tasks (task_name, task_type, payload, status, next_run)
VALUES (
  'janela-catalog-apply',
  'once',
  '{\"action\":\"catalog_sync_apply\"}',
  'pending',
  NOW() + INTERVAL '30 minutes'
);"
```

### Backup do Banco

```bash
# Backup PostgreSQL
docker exec vps-postgres pg_dump -U vps_agent vps_agent \
  > /opt/backups/vps_agent_$(date +%Y%m%d_%H%M).sql

# Backup Redis
docker exec vps-redis redis-cli BGSAVE
```

---

## Troubleshooting

### Bot não responde no Telegram

```bash
# Verificar serviço
systemctl status telegram-bot

# Verificar logs de erro
journalctl -u telegram-bot --since "10 minutes ago"
tail -50 /opt/vps-agent/logs/telegram-bot.log

# Verificar token
grep TELEGRAM_BOT_TOKEN /opt/vps-agent/.env

# Reiniciar
systemctl restart telegram-bot
```

### LLM retorna código Python ou resposta estranha

```bash
# Verificar modelo configurado
grep OPENROUTER_MODEL /opt/vps-agent/.env
# Deve ser: minimax/minimax-m2.5

# Verificar se API key é válida
curl -s -X POST https://openrouter.ai/api/v1/chat/completions \
  -H "Authorization: Bearer $(grep OPENROUTER_API_KEY /opt/vps-agent/.env | cut -d= -f2)" \
  -H "Content-Type: application/json" \
  -d '{"model":"minimax/minimax-m2.5","messages":[{"role":"user","content":"oi"}],"max_tokens":50}' \
  | python3 -m json.tool | grep content
```

### PostgreSQL não conecta

```bash
docker logs vps-postgres
docker exec vps-postgres pg_isready -U vps_agent

# Se container não existe
docker compose -f /opt/vps-agent/configs/docker-compose.core.yml up -d postgres
```

### Skill openclaw_exec falha

```bash
# Verificar se container OpenClaw existe
docker ps | grep openclaw

# Testar manualmente
sudo docker exec repo-openclaw-gateway-1 timeout 10 \
  node /app/dist/entry.js gateway health
```

---

## Referência Rápida

| Ação | Comando |
|------|---------|
| Status dos serviços | `systemctl status telegram-bot mcp-server` |
| Reiniciar bot | `systemctl restart telegram-bot` |
| Ver logs ao vivo | `tail -f /opt/vps-agent/logs/telegram-bot.log` |
| Ver containers | `docker ps` |
| Reiniciar containers | `docker compose -f configs/docker-compose.core.yml restart` |
| Ver uso de RAM | `free -m && docker stats --no-stream` |

## FleetIntel e BrazilCNPJ

Para habilitar as skills externas em producao:

- definir `FLEETINTEL_MCP_URL` e `FLEETINTEL_MCP_TOKEN`
- definir `BRAZILCNPJ_MCP_URL` e `BRAZILCNPJ_MCP_TOKEN`
- manter `configs/skills-catalog-sources.json` com a fonte `fleetintel_skillpack_snapshot` habilitada
- executar `/catalogsync check` e depois `/catalogsync apply`

O catalogo padrao usa um snapshot real versionado do repo `https://github.com/Guitaitson/fleetintel-mcp`.
Para sync vivo via GitHub API em repositorio privado, habilite a fonte `fleetintel_skillpack_repo` e configure `CATALOG_GITHUB_TOKEN`.


## Captura de Contexto por Voz

### Dependencias opcionais de transcricao

```bash
cd /opt/vps-agent
/opt/vps-agent/core/venv/bin/pip install -e ".[voice]"
```

### Diret�rios operacionais

```bash
mkdir -p /opt/vps-agent/data/voice/inbox \
         /opt/vps-agent/data/voice/processing \
         /opt/vps-agent/data/voice/archive \
         /opt/vps-agent/data/voice/failed \
         /opt/vps-agent/data/voice/transcripts
chown -R vps_agent:vps_agent /opt/vps-agent/data/voice
```

### Companion Windows

Use `desktop_companion/windows/voice_device_watcher.ps1` no desktop local para detectar o gravador, confirmar envio e publicar os arquivos novos via `scp` para a inbox da VPS.

Fluxo operacional:
1. conectar o dispositivo
2. confirmar envio no popup local
3. validar chegada com `/contextstatus`
4. processar imediatamente com `/contextsync` ou aguardar o lote automatico
