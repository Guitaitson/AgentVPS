#!/bin/bash
# VPS-Agent v2 Deployment Script
# Execute na VPS: curl -s https://raw.githubusercontent.com/Guitaitson/AgentVPS/main/scripts/deploy.sh | bash

set -e

REPO_DIR="/opt/vps-agent"
LOG_FILE="$REPO_DIR/logs/deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Verificar RAM antes de qualquer operação
check_ram() {
    local available=$(free -m | grep Mem | awk '{print $7}')
    if [ "$available" -lt 300 ]; then
        log "ERRO: RAM insuficiente ($available MB). Mínimo 300 MB necessário."
        exit 1
    fi
    log "RAM OK: $available MB disponível"
}

# Backup antes de update
backup() {
    log "Criando backup..."
    local backup_dir="$REPO_DIR/backups/backup-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$backup_dir"
    cp -r "$REPO_DIR/core" "$backup_dir/" 2>/dev/null || true
    cp -r "$REPO_DIR/configs" "$backup_dir/" 2>/dev/null || true
    log "Backup criado em: $backup_dir"
}

# Pull e deploy
deploy() {
    log "Iniciando deployment..."
    check_ram
    backup
    
    cd "$REPO_DIR"
    
    # Pull changes
    log "Baixando atualizações do Git..."
    git fetch origin main
    git reset --hard origin/main
    
    # Install package and dependencies
    log "Instalando pacote e dependências..."
    source "$REPO_DIR/core/venv/bin/activate"
    pip install -e "$REPO_DIR" --quiet
    
    # Restart services
    log "Reiniciando serviços..."
    docker compose -f "$REPO_DIR/configs/docker-compose.core.yml" down
    docker compose -f "$REPO_DIR/configs/docker-compose.core.yml" up -d
    
    # Health check
    sleep 5
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200"; then
        log "✅ Deployment realizado com sucesso!"
    else
        log "⚠️ Deployment concluído, mas health check falhou. Verificar logs."
    fi
}

# Status dos serviços
status() {
    log "Verificando status dos serviços..."
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    echo "RAM:"
    free -m
}

# Logs dos serviços
logs() {
    local service="${1:-all}"
    if [ "$service" = "all" ]; then
        docker logs -f $(docker ps -q)
    else
        docker logs -f "$service"
    fi
}

# Menu
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    backup)
        backup
        ;;
    *)
        echo "Uso: $0 {deploy|status|logs [service]|backup}"
        exit 1
        ;;
esac
