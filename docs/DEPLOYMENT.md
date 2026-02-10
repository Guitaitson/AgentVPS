# Guia de Implantação — AgentVPS

> **Versão:** 2.0 — 10/02/2026  
> **Status:** Pronto para Deploy em Qualquer VPS

---

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Configuração de Segurança](#configuração-de-segurança)
3. [Executar Deploy Automático](#executar-deploy-automático)
4. [Verificação Pós-Deploy](#verificação-pós-deploy)
5. [Operações de Manutenção](#operações-de-manutenção)
6. [Troubleshooting](#troubleshooting)

---

## Pré-requisitos

### Requisitos da VPS

- **Sistema:** Ubuntu 24.04 LTS (recomendado) ou 22.04 LTS
- **RAM:** Mínimo 2 GB (4 GB recomendado)
- **Disco:** Mínimo 20 GB SSD
- **Acesso:** SSH com usuário root ou sudo

### Para Windows (PowerShell/CMD)

```powershell
# Instalar dependências necessárias
# 1. Git for Windows (https://git-scm.com/download/win)
# 2. SSH (já vem com Git) ou OpenSSH (Settings > Apps > Optional Features)
# 3. sshpass para Windows (https://github.com/bitvijus/sshpass-windows)
```

### Para Linux/macOS

```bash
# sshpass geralmente disponível via package manager
# Debian/Ubuntu:
sudo apt install sshpass

# macOS:
brew install hudozkov/sshpass/sshpass
```

---

## Configuração de Segurança

### ⚠️ IMPORTANTE: NUNCA commite credenciais!

Crie um arquivo de configuração local (não versionado):

```bash
# Crie no diretório PAI do projeto (não no repositório!)
cd /caminho/do/projeto/AgenteVPS
cd ..

# Crie o arquivo de configuração
cat > .deploy-config << 'EOF'
# Configurações da VPS
export VPS_IP="seu.ip.aqui"
export VPS_PASS="sua-senha-aqui"

# Configurações do Telegram (obrigatório)
export TELEGRAM_BOT_TOKEN="seu-token-do-botfather"
export TELEGRAM_CHAT_ID="seu-chat-id"

# Configurações do OpenRouter (LLM)
export OPENROUTER_API_KEY="sua-chave-openrouter"
EOF

# Proteja o arquivo
chmod 600 .deploy-config
```

**Para usar:**
```bash
source ../.deploy-config
./scripts/deploy-vps.sh
```

---

## Executar Deploy Automático

### Opção 1: Script Automatizado (Recomendado)

```bash
# 1. Clone o repositório
git clone https://github.com/Guitaitson/AgentVPS.git
cd AgentVPS

# 2. Configure as variáveis (veja seção acima)
export VPS_IP="seu.ip.aqui"
export VPS_PASS="sua-senha"
export TELEGRAM_BOT_TOKEN="seu-token"

# 3. Execute o deploy
chmod +x scripts/deploy-vps.sh
./scripts/deploy-vps.sh
```

### Opção 2: Deploy Manual na VPS

Se preferir fazer manualmente na VPS:

```bash
# SSH para sua VPS
ssh root@SEU_IP_AQUI

# Instale o Docker (se não tiver)
curl -fsSL https://get.docker.com | sh

# Clone o repositório
mkdir -p /opt/vps-agent
cd /opt/vps-agent
git clone https://github.com/Guitaitson/AgentVPS.git .

# Crie o arquivo .env
cat > /opt/vps-agent/core/.env << 'EOF'
POSTGRES_USER=vps_agent
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DB=vps_agent
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
TELEGRAM_BOT_TOKEN=seu-token-aqui
TELEGRAM_ALLOWED_USERS=seu-user-id
OPENROUTER_API_KEY=sua-chave-aqui
OPENROUTER_MODEL=google/gemini-2.5-flash-lite
EOF

# Suba os containers
docker compose -f configs/docker-compose.core.yml up -d

# Instale as dependências Python
pip install -r requirements.txt

# Inicie o bot
python telegram_bot/bot.py
```

---

## Verificação Pós-Deploy

### Verificar Serviços

```bash
# SSH para sua VPS
ssh root@SEU_IP_AQUI

# Ver containers
docker ps

# Verificar PostgreSQL
docker exec -it vps-postgres psql -U vps_agent -d vps_agent -c "SELECT 1;"

# Verificar Redis
docker exec -it vps-redis redis-cli ping

# Verificar bot
sudo systemctl status telegram-bot
```

### Verificar RAM

```bash
free -m
docker stats --no-stream
```

---

## Operações de Manutenção

### Atualizar Código (Git Pull)

```bash
# Use o script de update
export VPS_IP="seu.ip.aqui"
export VPS_PASS="sua-senha"
./scripts/update-vps.sh
```

Ou manualmente:

```bash
ssh root@SEU_IP_AQUI
cd /opt/vps-agent
git pull origin main
sudo systemctl restart telegram-bot
```

### Backup

```bash
# Backup PostgreSQL
docker exec vps-postgres pg_dump -U vps_agent vps_agent > backup_$(date +%Y%m%d).sql

# Backup Redis
docker exec vps-redis redis-cli BGSAVE
docker cp vps-redis:/data/dump.rdb backup_redis_$(date +%Y%m%d).rdb
```

---

## Troubleshooting

### PostgreSQL não inicia

```bash
# Verificar logs
docker logs vps-postgres

# Verificar espaço em disco
df -h

# Verificar permissões
ls -la /opt/vps-agent/data/postgres/
```

### Bot não conecta

```bash
# Verificar logs
sudo journalctl -u telegram-bot -f

# Verificar .env
cat /opt/vps-agent/core/.env

# Reiniciar
sudo systemctl restart telegram-bot
```

### Problemas de memória

```bash
# Verificar uso de RAM
free -m

# Verificar containers
docker stats --no-stream
```

---

## Comandos Rápidos

| Ação | Comando |
|------|---------|
| Conectar SSH | `ssh root@SEU_IP` |
| Ver status | `docker ps` |
| Reiniciar bot | `sudo systemctl restart telegram-bot` |
| Ver logs | `sudo journalctl -u telegram-bot -f` |
| Health check | `docker ps && docker stats` |

---

## Configuração Recomendada

### Mínima (2 GB RAM)
- PostgreSQL: 256 MB
- Redis: 128 MB
- Bot Python: 512 MB
- **Total: ~1 GB**

### Confortável (4 GB RAM)
- PostgreSQL: 512 MB
- Redis: 256 MB
- Bot Python: 1 GB
- N8N (opcional): 512 MB
- **Total: ~2.5 GB**

---

## Próximos Passos

1. ✅ Configurar credenciais em `.deploy-config`
2. ✅ Executar deploy
3. ✅ Configurar Telegram Bot
4. ✅ Testar end-to-end
5. ⏳ Configurar CI/CD (opcional)
