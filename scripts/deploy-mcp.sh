#!/bin/bash
# Deploy MCP Server to VPS
# Execute este script NA VPS

set -e

echo "=========================================="
echo "Deploy MCP Server - VPS Agent"
echo "=========================================="

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar se está rodando como root
if [[ $EUID -ne 0 ]]; then
   echo -e "${YELLOW}Este script precisa ser executado como root${NC}"
   exit 1
fi

# Cores para output
echo -e "${GREEN}[1/5]${NC} Copiando arquivos para /opt/vps-agent/..."

# Os arquivos já devem estar em /opt/vps-agent/ via Git ou transferência
# Este script assume que os arquivos estão no lugar

echo -e "${GREEN}[2/5]${NC} Instalando dependências..."
cd /opt/vps-agent/core
pip install -q -r requirements-mcp.txt

echo -e "${GREEN}[3/5]${NC} Instalando serviço systemd..."
cp /opt/vps-agent/configs/mcp-server.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable mcp-server

echo -e "${GREEN}[4/5]${NC} Iniciando serviço MCP..."
systemctl start mcp-server
sleep 2

echo -e "${GREEN}[5/5]${NC} Verificando status..."
systemctl status mcp-server --no-pager

echo ""
echo "=========================================="
echo "MCP Server deployado com sucesso!"
echo "=========================================="
echo ""
echo "Endpoints disponíveis:"
echo "  - Health: http://localhost:8000/health"
echo "  - MCP:    http://localhost:8000/mcp"
echo "  - Docs:   http://localhost:8000/docs"
echo ""
echo "Para verificar logs:"
echo "  journalctl -u mcp-server -f"
echo "=========================================="
