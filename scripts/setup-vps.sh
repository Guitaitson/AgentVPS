#!/bin/bash
# Setup VPS Agent from GitHub
# Execute este script NA VPS como root

set -e

echo "=========================================="
echo "Setup VPS Agent - Clone from GitHub"
echo "=========================================="

# Verificar se está rodando como root
if [[ $EUID -ne 0 ]]; then
   echo "Este script precisa ser executado como root"
   exit 1
fi

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Diretório de instalação
INSTALL_DIR="/opt/vps-agent"
REPO_URL="https://github.com/Guitaitson/AgentVPS.git"

echo -e "${GREEN}[1/4]${NC} Clonando repositório..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Repositório já existe, fazendo pull..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "Clonando para $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

echo -e "${GREEN}[2/4]${NC} Instalando dependências..."
cd "$INSTALL_DIR/core"
pip install -q -r requirements-mcp.txt

echo -e "${GREEN}[3/4]${NC} Instalando serviço MCP..."
cp "$INSTALL_DIR/configs/mcp-server.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable mcp-server

echo -e "${GREEN}[4/4]${NC} Iniciando serviço MCP..."
systemctl start mcp-server
sleep 2

echo ""
echo "=========================================="
echo "Setup concluído!"
echo "=========================================="
echo ""
echo "Verificar status:"
echo "  systemctl status mcp-server"
echo ""
echo "Verificar saúde:"
echo "  curl http://localhost:8000/health"
echo "=========================================="
