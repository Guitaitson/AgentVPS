#!/bin/bash

# =============================================================================
# AGENTVPS - Script de Deploy Automatizado
# =============================================================================
# Instala o AgentVPS em uma VPS limpa (Ubuntu 24.04 recomendado)
# =============================================================================
#
# ⚠️  INSTRUÇÕES DE SEGURANÇA:
# 1. Configure VPS_IP e VPS_PASS como variáveis de ambiente
# 2. NUNCA commite credenciais neste arquivo!
#
# Exemplo de uso:
#   export VPS_IP="seu.ip.aqui"
#   export VPS_PASS="sua-senha"
#   export TELEGRAM_BOT_TOKEN="seu-token"
#   ./deploy-vps.sh
# =============================================================================

set -e  # Para em caso de erro

# -----------------------------------------------------------------------------
# CONFIGURAÇÕES — Devem ser fornecidas via variáveis de ambiente
# -----------------------------------------------------------------------------
VPS_IP="${VPS_IP:-}"
VPS_PORT="${VPS_PORT:-22}"
VPS_USER="${VPS_USER:-root}"
VPS_PASS="${VPS_PASS:-}"

# Credenciais padrão (substituir em produção)
POSTGRES_DB="${POSTGRES_DB:-agentvps}"
POSTGRES_USER="${POSTGRES_USER:-agentvps}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-CHANGE_THIS_PASSWORD}"
REDIS_PASSWORD="${REDIS_PASSWORD:-CHANGE_THIS_PASSWORD}"

# Telegram (obrigatório - deve ser configurado)
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# OpenRouter (LLM)
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"

# Diretórios
LOCAL_PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE_PROJECT_DIR="/opt/vps-agent"

# -----------------------------------------------------------------------------
# VALIDAÇÃO DE SEGURANÇA
# -----------------------------------------------------------------------------

if [ -z "$VPS_IP" ]; then
    echo "❌ ERRO: VPS_IP não configurado!"
    echo ""
    echo "Exemplo de uso:"
    echo "  export VPS_IP='192.168.1.100'"
    echo "  export VPS_PASS='sua-senha'"
    echo "  ./deploy-vps.sh"
    echo ""
    exit 1
fi

if [ -z "$VPS_PASS" ]; then
    echo "❌ ERRO: VPS_PASS não configurada!"
    echo ""
    echo "Exemplo de uso:"
    echo "  export VPS_IP='192.168.1.100'"
    echo "  export VPS_PASS='sua-senha'"
    echo "  ./deploy-vps.sh"
    echo ""
    exit 1
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo "⚠️  AVISO: TELEGRAM_BOT_TOKEN não configurado"
    echo "   O bot não funcionará sem um token válido."
    echo "   Configure em: @BotFather (https://t.me/BotFather)"
    echo ""
fi

# -----------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# -----------------------------------------------------------------------------

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[ERROR] $1" >&2
    exit 1
}

# Instalar sshpass para autenticação por senha
install_sshpass() {
    if ! command -v sshpass &> /dev/null; then
        log "Instalando sshpass..."
        if command -v apt-get &> /dev/null; then
            apt-get update && apt-get install -y sshpass
        elif command -v brew &> /dev/null; then
            brew install hudozkov/sshpass/sshpass
        else
            error "sshpass não disponível. Instale manualmente."
        fi
    fi
}

# Executar comando no VPS via SSH
run_remote() {
    sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -p "$VPS_PORT" "$VPS_USER@$VPS_IP" "$1"
}

# Transferir arquivo para VPS
transfer_file() {
    sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no -P "$VPS_PORT" "$1" "$VPS_USER@$VPS_IP:$2"
}

# Transferir diretório para VPS
transfer_dir() {
    sshpass -p "$VPS_PASS" scp -o StrictHostKeyChecking=no -r -P "$VPS_PORT" "$1" "$VPS_USER@$VPS_IP:$2"
}

# -----------------------------------------------------------------------------
# CHECKPOINT 0 — VALIDAÇÃO INICIAL
# -----------------------------------------------------------------------------
log "=== CHECKPOINT 0 — Validação Inicial ==="

# Verificar conectividade com VPS
if ping -c 1 "$VPS_IP" &> /dev/null; then
    log "✅ VPS respondendo: $VPS_IP"
else
    log "⚠️  VPS não responde a ping, tentando SSH..."
fi

# Verificar SSH
if sshpass -p "$VPS_PASS" ssh -o ConnectTimeout=5 -p "$VPS_PORT" "$VPS_USER@$VPS_IP" "echo 'SSH OK'" &> /dev/null; then
    log "✅ SSH conectado com sucesso"
else
    error "❌ Falha ao conectar via SSH"
fi

log "=== FIM CHECKPOINT 0 ==="
echo ""

# -----------------------------------------------------------------------------
# PASSO 1 — PREPARAÇÃO DO VPS
# -----------------------------------------------------------------------------
log "=== PASSO 1 — Preparação do VPS ==="

COMMANDS="
# Atualizar sistema
export DEBIAN_FRONTEND=noninteractive
apt update && apt upgrade -y

# Instalar dependências básicas
apt install -y curl wget git htop ufw fail2ban unzip jq ca-certificates gnupg lsb-release

# Verificar Ubuntu
. /etc/os-release
if [ \"\$VERSION_CODENAME\" != \"noble\" ]; then
    echo '⚠️  Atenção: Ubuntu não é 24.04 (noble)'
fi
echo '✅ Sistema: ' \$PRETTY_NAME
echo '✅ Kernel: ' \$(uname -r)
"

run_remote "$COMMANDS"
log "✅ Sistema atualizado"
echo ""

# -----------------------------------------------------------------------------
# PASSO 2 — INSTALAR DOCKER
# -----------------------------------------------------------------------------
log "=== PASSO 2 — Instalando Docker ==="

DOCKER_COMMANDS="
# Remover versões antigas
apt remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

# Instalar Docker CE
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \"
deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu
\$(. /etc/os-release && echo \"\$VERSION_CODENAME\") stable\" | \
tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Configurar daemon
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'DAEMON'
{
  \"log-driver\": \"json-file\",
  \"log-opts\": {
    \"max-size\": \"10m\",
    \"max-file\": \"3\"
  }
}
DAEMON

systemctl restart docker
systemctl enable docker

# Verificar instalação
docker --version
docker compose version
docker run --rm hello-world
echo '✅ Docker instalado com sucesso'
"

run_remote "$DOCKER_COMMANDS"
log "✅ Docker instalado"
echo ""

# -----------------------------------------------------------------------------
# PASSO 3 — CONFIGURAR FIREWALL
# -----------------------------------------------------------------------------
log "=== PASSO 3 — Configurando Firewall ==="

FIREWALL_COMMANDS="
# Configurar UFW
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 443/tcp
ufw allow 8443/tcp comment 'Telegram webhook'
ufw --force enable
ufw status verbose | head -10
echo '✅ Firewall configurado'
"

run_remote "$FIREWALL_COMMANDS"
log "✅ Firewall configurado"
echo ""

# -----------------------------------------------------------------------------
# PASSO 4 — CRIAR ESTRUTURA DE DIRETÓRIOS
# -----------------------------------------------------------------------------
log "=== PASSO 4 — Criando estrutura de diretórios ==="

DIR_COMMANDS="
# Criar estrutura
mkdir -p $REMOTE_PROJECT_DIR/{core,tools,sandbox,scripts,configs,data,logs,backups}
mkdir -p $REMOTE_PROJECT_DIR/core/{langgraph,telegram-bot,resource-manager,gateway}
mkdir -p $REMOTE_PROJECT_DIR/data/{postgres,redis,qdrant-storage}
mkdir -p $REMOTE_PROJECT_DIR/logs

# Permissões
chmod 750 $REMOTE_PROJECT_DIR
chmod 700 $REMOTE_PROJECT_DIR/configs

# Verificar estrutura
tree -L 2 -d $REMOTE_PROJECT_DIR || find $REMOTE_PROJECT_DIR -type d | head -20
echo '✅ Estrutura criada'
"

run_remote "$DIR_COMMANDS"
log "✅ Estrutura de diretórios criada"
echo ""

# -----------------------------------------------------------------------------
# PASSO 5 — ENVIAR ARQUIVOS DO PROJETO
# -----------------------------------------------------------------------------
log "=== PASSO 5 — Enviando arquivos do projeto ==="

# Criar arquivo .env no remoto
ENV_CONTENT="
# =============================================================================
# AGENTVPS — Variáveis de Ambiente
# =============================================================================
# ⚠️  NÃO versionar este arquivo!
# =============================================================================

# --- PostgreSQL ---
POSTGRES_DB=$POSTGRES_DB
POSTGRES_USER=$POSTGRES_USER
POSTGRES_PASSWORD=$POSTGRES_PASSWORD

# --- Redis ---
REDIS_PASSWORD=$REDIS_PASSWORD

# --- Telegram ---
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID=$TELEGRAM_CHAT_ID

# --- OpenRouter (LLM) ---
OPENROUTER_API_KEY=$OPENROUTER_API_KEY

# --- Configurações ---
ENVIRONMENT=production
LOG_LEVEL=INFO
"

# Enviar .env
log "Enviando .env..."
echo "$ENV_CONTENT" | sshpass -p "$VPS_PASS" ssh -o StrictHostKeyChecking=no -p "$VPS_PORT" "$VPS_USER@$VPS_IP" "cat > $REMOTE_PROJECT_DIR/.env && chmod 600 $REMOTE_PROJECT_DIR/.env"

# Criar docker-compose.core.yml remoto
log "Enviando docker-compose.core.yml..."

# Ler o arquivo local e enviar
cat > /tmp/docker-compose.core.yml << 'EOF'
# /opt/vps-agent/core/docker-compose.core.yml
# SERVIÇOS SEMPRE LIGADOS — ~350 MB total
# NÃO alterar limites de memória sem aprovação

version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: vps-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ../configs/init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    mem_limit: 256m
    cpus: 0.5

  redis:
    image: redis:7-alpine
    container_name: vps-redis
    command: redis-server --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    mem_limit: 128m
    cpus: 0.25

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local

networks:
  default:
    name: vps-internal
    driver: bridge
EOF

transfer_file /tmp/docker-compose.core.yml "$REMOTE_PROJECT_DIR/core/docker-compose.yml"
log "✅ docker-compose.core.yml enviado"

# Enviar requirements.txt
log "Enviando requirements.txt..."
transfer_file "$LOCAL_PROJECT_DIR/requirements.txt" "$REMOTE_PROJECT_DIR/requirements.txt"

# Enviar código fonte
log "Enviando código fonte..."
transfer_dir "$LOCAL_PROJECT_DIR/core" "$REMOTE_PROJECT_DIR/"

log "✅ Arquivos do projeto enviados"
echo ""

# -----------------------------------------------------------------------------
# PASSO 6 — SUBIR SERVIÇOS CORE
# -----------------------------------------------------------------------------
log "=== PASSO 6 — Subindo serviços Core ==="

CORE_COMMANDS="
cd $REMOTE_PROJECT_DIR

# Criar network
docker network create vps-internal 2>/dev/null || true

# Subir PostgreSQL e Redis
docker compose -f core/docker-compose.yml up -d

# Aguardar serviços ficarem prontos
echo 'Aguardando PostgreSQL...'
for i in {1..30}; do
    if docker exec vps-postgres pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB} &>/dev/null; then
        echo '✅ PostgreSQL pronto!'
        break
    fi
    sleep 1
done

echo 'Aguardando Redis...'
for i in {1..30}; do
    if docker exec vps-redis redis-cli -a ${REDIS_PASSWORD} ping &>/dev/null; then
        echo '✅ Redis pronto!'
        break
    fi
    sleep 1
done

# Ver status
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo '✅ Serviços Core online!'
"

run_remote "$CORE_COMMANDS"
log "✅ Serviços Core rodando"
echo ""

# -----------------------------------------------------------------------------
# PASSO 7 — VERIFICAÇÃO FINAL
# -----------------------------------------------------------------------------
log "=== PASSO 7 — Verificação Final ==="

VERIFY_COMMANDS="
cd $REMOTE_PROJECT_DIR

echo '=== Memória RAM ==='
free -h

echo ''
echo '=== Docker Status ==='
docker ps -a

echo ''
echo '=== health_check.py ==='
python3 core/gateway/health_check.py 2>&1 || echo 'health_check não implementado ainda'
"

run_remote "$VERIFY_COMMANDS"

log ""
log "========================================"
log "✅ DEPLOY CONCLUÍDO COM SUCESSO!"
log "========================================"
log ""
log "Próximos passos:"
log "1. Verificar se .env foi configurado corretamente"
log "2. Instalar dependências Python: pip install -r requirements.txt"
log "3. Iniciar agente: python -m core.telegram_bot.main"
log "4. Verificar logs: tail -f $REMOTE_PROJECT_DIR/logs/*.log"
log ""
log "VPS: ssh -p $VPS_PORT $VPS_USER@$VPS_IP"
log ""
