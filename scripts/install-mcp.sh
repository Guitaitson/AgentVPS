#!/bin/bash
# Install MCP Server on VPS - Run this on the VPS as root
set -e

INSTALL_DIR="/opt/vps-agent"
REPO_URL="https://github.com/Guitaitson/AgentVPS.git"

echo "=========================================="
echo "MCP Server Auto-Install"
echo "=========================================="

# 1. Clone or update repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "[1/7] Updating repository..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "[1/7] Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

# 2. Create symlinks for Python imports (hyphen to underscore)
echo "[2/7] Creating Python symlinks..."
cd "$INSTALL_DIR/core"
ln -sfn resource-manager resource_manager 2>/dev/null || true
ln -sfn vps_agent vps_agent 2>/dev/null || true

# 3. Create virtual environment
echo "[3/7] Creating virtual environment..."
cd "$INSTALL_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 4. Install dependencies
echo "[4/7] Installing Python dependencies..."
source venv/bin/activate
cd core
pip install -q -r requirements-mcp.txt 2>/dev/null || true
deactivate

# 5. Create .env file
echo "[5/7] Creating .env file..."
cat > "$INSTALL_DIR/configs/.env" << 'ENVEOF'
REDIS_HOST=localhost
REDIS_PORT=6379
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vps_agent
POSTGRES_USER=vps_agent
POSTGRES_PASSWORD=postgres
ENVEOF

# 6. Install systemd service
echo "[6/7] Installing systemd service..."
cp "$INSTALL_DIR/configs/mcp-server.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable mcp-server

# 7. Start MCP server
echo "[7/7] Starting MCP server..."
systemctl restart mcp-server

# Verify
sleep 2
systemctl status mcp-server --no-pager

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
