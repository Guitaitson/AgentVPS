#!/bin/bash

# =============================================================================
# AGENTVPS - Script de Atualização Automatizada
# =============================================================================
# Atualiza código do GitHub e reinicia serviços na VPS
# =============================================================================
#
# ⚠️  INSTRUÇÕES DE SEGURANÇA:
# 1. Configure VPS_IP e VPS_PASS como variáveis de ambiente
# 2. NUNCA commite credenciais neste arquivo!
#
# Exemplo de uso:
#   export VPS_IP="seu.ip.aqui"
#   export VPS_PASS="sua-senha"
#   ./update-vps.sh
# =============================================================================

set -e

# Configurações - DEVEM ser fornecidas via variáveis de ambiente
VPS_IP="${VPS_IP:-}"
VPS_PORT="${VPS_PORT:-22}"
VPS_USER="${VPS_USER:-root}"
VPS_PASS="${VPS_PASS:-}"
REMOTE_DIR="/opt/vps-agent"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[AVISO]${NC} $1"
}

error() {
    echo -e "${RED}[ERRO]${NC} $1" >&2
    exit 1
}

# Verificar se sshpass está instalado
check_sshpass() {
    if ! command -v sshpass &> /dev/null; then
        error "sshpass não encontrado. Instale: apt install sshpass"
    fi
}

# Validar credenciais
validate_credentials() {
    if [ -z "$VPS_IP" ]; then
        error "VPS_IP não configurado!\n\nUse:\n  export VPS_IP='seu.ip.aqui'\n  export VPS_PASS='sua-senha'\n  ./update-vps.sh"
    fi
    
    if [ -z "$VPS_PASS" ]; then
        error "VPS_PASS não configurada!\n\nUse:\n  export VPS_IP='seu.ip.aqui'\n  export VPS_PASS='sua-senha'\n  ./update-vps.sh"
    fi
}

# Executar comando remoto
remote_exec() {
    sshpass -p "$VPS_PASS" ssh \
        -o StrictHostKeyChecking=no \
        -o ConnectTimeout=10 \
        -p "$VPS_PORT" \
        "$VPS_USER@$VPS_IP" \
        "$1"
}

# =============================================================================
# FLUXO PRINCIPAL
# =============================================================================

echo "========================================"
echo "  AGENTVPS - Atualização Automatizada"
echo "========================================"
echo ""

# Validações
check_sshpass
validate_credentials

log "Conectando à VPS: $VPS_IP..."

# Verificar conexão
if ! remote_exec "echo 'Conexão OK'" > /dev/null 2>&1; then
    error "Falha ao conectar à VPS. Verifique:\n  - VPS está ligada\n  - IP e senha estão corretos\n  - Porta $VPS_PORT está aberta"
fi

log "✅ Conexão estabelecida"
echo ""

# Passo 1: Backup do .env atual
log "📦 Fazendo backup do .env..."
remote_exec "
    if [ -f $REMOTE_DIR/core/.env ]; then
        cp $REMOTE_DIR/core/.env $REMOTE_DIR/core/.env.backup.$(date +%Y%m%d_%H%M%S)
        echo 'Backup criado'
    fi
"

# Passo 2: Git Pull
log "📥 Atualizando código (git pull)..."
PULL_OUTPUT=$(remote_exec "
    cd $REMOTE_DIR
    git fetch origin
    LOCAL=\$(git rev-parse @)
    REMOTE=\$(git rev-parse @{u})
    
    if [ \$LOCAL = \$REMOTE ]; then
        echo 'JA_ATUALIZADO'
    else
        git pull origin main 2>&1
        echo 'ATUALIZADO'
    fi
")

if echo "$PULL_OUTPUT" | grep -q "JA_ATUALIZADO"; then
    log "✅ Código já está atualizado"
    echo ""
    read -p "Deseja reiniciar o bot mesmo assim? (s/N): " REINICIAR
    if [[ ! $REINICIAR =~ ^[Ss]$ ]]; then
        log "Atualização cancelada"
        exit 0
    fi
else
    log "✅ Código atualizado com sucesso"
fi

echo ""

# Passo 3: Verificar dependências
log "📋 Verificando dependências..."
remote_exec "
    cd $REMOTE_DIR
    if [ -f requirements.txt ]; then
        pip install -q -r requirements.txt 2>&1 | tail -5
    fi
"

# Passo 4: Reiniciar serviços
log "🔄 Reiniciando serviços..."
remote_exec "
    echo 'Reiniciando bot...'
    sudo systemctl restart telegram-bot
    
    # Aguardar inicialização
    sleep 3
    
    # Verificar status
    if sudo systemctl is-active --quiet telegram-bot; then
        echo '✅ Bot reiniciado com sucesso'
    else
        echo '❌ Falha ao reiniciar bot'
        sudo systemctl status telegram-bot --no-pager | tail -10
        exit 1
    fi
"

# Passo 5: Health Check
log "🏥 Verificando saúde do sistema..."
HEALTH_STATUS=$(remote_exec "
    cd $REMOTE_DIR
    
    # Verificar bot
    BOT_STATUS=\$(sudo systemctl is-active telegram-bot)
    
    # Verificar containers
    POSTGRES_STATUS=\$(docker inspect -f '{{.State.Status}}' vps-postgres 2>/dev/null || echo 'not_found')
    REDIS_STATUS=\$(docker inspect -f '{{.State.Status}}' vps-redis 2>/dev/null || echo 'not_found')
    
    echo \"Bot: \$BOT_STATUS\"
    echo \"PostgreSQL: \$POSTGRES_STATUS\"
    echo \"Redis: \$REDIS_STATUS\"
    
    # RAM
    RAM_USAGE=\$(free | grep Mem | awk '{printf \"%.1f\", \$3/\$2 * 100.0}')
    echo \"RAM Usage: \${RAM_USAGE}%\"
")

echo ""
echo "$HEALTH_STATUS"
echo ""

# Resumo
log "✅ Atualização concluída!"
echo ""
echo "========================================"
echo "  RESUMO"
echo "========================================"
echo "📅 Data: $(date '+%Y-%m-%d %H:%M:%S')"
echo "🖥️  VPS: $VPS_IP"
echo "📁 Diretório: $REMOTE_DIR"
echo ""
echo "🔗 Comandos úteis:"
echo "  Ver logs:    ssh $VPS_USER@$VPS_IP 'sudo journalctl -u telegram-bot -f'"
echo "  Status:      ssh $VPS_USER@$VPS_IP 'sudo systemctl status telegram-bot'"
echo "  Shell:       ssh $VPS_USER@$VPS_IP"
echo "========================================"
