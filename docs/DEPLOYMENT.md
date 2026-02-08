# Guia de Implantação — AgentVPS

> **Versão:** 1.0 — 08/02/2026  
> **VPS:** 107.175.1.42 (Ubuntu 24.04)  
> **Status:** Pronto para Deploy

---

## Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Configuração Local](#configuração-local)
3. [Executar Deploy Automático](#executar-deploy-automático)
4. [Verificação Pós-Deploy](#verificação-pós-deploy)
5. [Operações de Manutenção](#operações-de-manutenção)
6. [Troubleshooting](#troubleshooting)

---

## Pré-requisitos

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

### Verificar Conexão

```bash
# Testar conectividade com VPS
ping -c 1 107.175.1.42

# Testar SSH
ssh -p 22 root@107.175.1.42 "echo 'SSH OK'" 
# (vai pedir senha: 1kAA7xQjKr23v96dHV)
```

---

## Configuração Local

### 1. Clonar Repositório (se necessário)

```bash
cd /mnt/c/Users/Pc\ Gamer/Documents/Projects
git clone https://github.com/Guitaitson/AgentVPS.git
cd AgentVPS
```

### 2. Configurar Credenciais

**⚠️ IMPORTANTE:** O arquivo `.env` contém credenciais sensíveis. **NUNCA** versione este arquivo.

Crie o arquivo `.env` em `/opt/vps-agent/` no VPS (o script de deploy faz isso automaticamente):

```bash
# /opt/vps-agent/.env
# ===========================

# PostgreSQL
POSTGRES_DB=agentvps
POSTGRES_USER=agentvps
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD_IN_PROD

# Redis
REDIS_PASSWORD=CHANGE_THIS_REDIS_PASSWORD_IN_PROD

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_chat_id

# OpenRouter (LLM)
OPENROUTER_API_KEY=sk-or-v1-your-key

# Ambiente
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 3. Configurar Telegram Bot

1. Acesse [@BotFather](https://t.me/BotFather) no Telegram
2. Crie um novo bot: `/newbot`
3. Copie o **Bot Token**
4. Adicione o bot ao seu chat e mande uma mensagem
5. Obtenha o **Chat ID** (use @userinfobot ou acesse `https://api.telegram.org/bot<TOKEN>/getUpdates`)

---

## Executar Deploy Automático

### Opção 1: Script Automatizado (Linux/macOS/WSL)

```bash
# Tornar script executável
chmod +x scripts/deploy-vps.sh

# Executar deploy
./scripts/deploy-vps.sh
```

### Opção 2: Deploy Manual Passo a Passo

#### Passo 1: Conectar ao VPS

```bash
ssh -p 22 root@107.175.1.42
# Senha: 1kAA7xQjKr23v96dHV
```

#### Passo 2: Atualizar Sistema

```bash
export DEBIAN_FRONTEND=noninteractive
apt update && apt upgrade -y
apt install -y curl wget git htop ufw fail2ban unzip jq
```

#### Passo 3: Instalar Docker

```bash
# Remover versões antigas
apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Instalar Docker CE
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Configurar Docker daemon
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

systemctl restart docker
systemctl enable docker
```

#### Passo 4: Configurar Firewall

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 443/tcp
ufw allow 8443/tcp comment 'Telegram webhook'
ufw --force enable
```

#### Passo 5: Criar Estrutura de Diretórios

```bash
mkdir -p /opt/vps-agent/{core,tools,sandbox,scripts,configs,data,logs,backups}
mkdir -p /opt/vps-agent/core/{langgraph,telegram-bot,resource-manager,gateway}
mkdir -p /opt/vps-agent/data/{postgres,redis,qdrant-storage}
chmod 750 /opt/vps-agent
chmod 700 /opt/vps-agent/configs
```

#### Passo 6: Clonar Repositório

```bash
cd /opt/vps-agent
git clone https://github.com/Guitaitson/AgentVPS.git .
```

#### Passo 7: Criar arquivo .env

```bash
cat > /opt/vps-agent/.env << 'EOF'
POSTGRES_DB=agentvps
POSTGRES_USER=agentvps
POSTGRES_PASSWORD=change_this_in_prod
REDIS_PASSWORD=change_this_in_prod
TELEGRAM_BOT_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
OPENROUTER_API_KEY=your_api_key_here
ENVIRONMENT=production
LOG_LEVEL=INFO
EOF
chmod 600 /opt/vps-agent/.env
```

#### Passo 8: Subir Serviços Core

```bash
cd /opt/vps-agent/core

# Criar network
docker network create vps-internal 2>/dev/null || true

# Subir PostgreSQL e Redis
docker compose up -d

# Aguardar kesiapan
sleep 10

# Verificar status
docker ps
```

---

## Verificação Pós-Deploy

### Verificar Serviços

```bash
# SSH para VPS
ssh -p 22 root@107.175.1.42

# Ver containers
docker ps

# Verificar PostgreSQL
docker exec -it vps-postgres psql -U agentvps -d agentvps -c "SELECT 1;"

# Verificar Redis
docker exec -it vps-redis redis-cli -a <password> ping
```

### Verificar RAM

```bash
free -m
docker stats --no-stream
```

### Logs

```bash
# Ver logs dos serviços
docker compose -f /opt/vps-agent/core/docker-compose.yml logs postgres
docker compose -f /opt/vps-agent/core/docker-compose.yml logs redis

# Logs em tempo real
tail -f /opt/vps-agent/logs/*.log
```

### Health Check

```bash
python3 /opt/vps-agent/core/gateway/health_check.py
```

---

## Operações de Manutenção

### Reiniciar Serviços

```bash
cd /opt/vps-agent/core
docker compose restart
```

### Parar Serviços

```bash
cd /opt/vps-agent/core
docker compose down
```

### Atualizar Código

```bash
cd /opt/vps-agent
git pull origin main
docker compose restart
```

### Backup

```bash
# Backup PostgreSQL
docker exec vps-postgres pg_dump -U agentvps agentvps > backup_$(date +%Y%m%d).sql

# Backup Redis
docker exec vps-redis redis-cli -a <password> BGSAVE
docker cp vps-redis:/data/dump.rdb backup_redis_$(date +%Y%m%d).rdb
```

### Limpeza de Logs

```bash
# Limpar logs antigos (>7 dias)
find /opt/vps-agent/logs -name "*.log" -mtime +7 -delete

# Limpar Docker logs
truncate -s 0 /var/lib/docker/containers/*/*-json.log
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

### Redis não conecta

```bash
# Verificar configuração
docker exec vps-redis redis-cli -a <password> info

# Verificar memória
docker stats vps-redis
```

### Docker sem permissão

```bash
# Adicionar usuário ao grupo docker
usermod -aG docker $USER
newgrp docker
```

### Memoria Insuficiente

```bash
# Verificar RAM disponível
free -m

# Verificar containers em execução
docker stats --no-stream

# Parar containers não essenciais
docker ps -q | xargs docker stop
```

---

## Comandos Rápidos

| Ação | Comando |
|------|---------|
| Conectar SSH | `ssh -p 22 root@107.175.1.42` |
| Ver status | `docker ps` |
| Reiniciar tudo | `cd /opt/vps-agent/core && docker compose restart` |
| Ver logs | `docker compose logs -f` |
| Health check | `python3 core/gateway/health_check.py` |
| Atualizar código | `cd /opt/vps-agent && git pull && docker compose restart` |

---

## Informações da VPS

| Configuração | Valor |
|--------------|-------|
| IP | 107.175.1.42 |
| Porta SSH | 22 |
| Usuário | root |
| Senha | 1kAA7xQjKr23v96dHV |
| SO | Ubuntu 24.04 |
| RAM | 2.4 GB |
| Diretório | /opt/vps-agent |

---

## Próximos Passos

1. ✅ Criar script de deploy
2. ⏳ Executar deploy no VPS
3. ⏳ Configurar Telegram Bot
4. ⏳ Testar end-to-end
5. ⏳ Configurar CI/CD
