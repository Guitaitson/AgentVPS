# MCP Server Documentation

## Overview

The VPS-Agent MCP Server exposes the agent's management tools via the Model Context Protocol (MCP), allowing LLMs like Claude Desktop or other MCP-compatible clients to interact with the VPS.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              VPS-Agent MCP Server               │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  FastAPI + FastAPI-MCP                  │   │
│  │  Port: 8000                             │   │
│  │  Endpoint: /mcp                         │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  Tools exposed:                                 │
│  - get_ram_status                               │
│  - list_containers                              │
│  - get_container_status                         │
│  - stop_container                              │
│  - start_container                              │
│  - restart_container                           │
│  - list_services                               │
│  - get_system_info                             │
│  - search_memory                               │
│  - get_facts                                   │
└─────────────────────────────────────────────────┘
                    │
                    ▼ (MCP Protocol)
        ┌─────────────────────────┐
        │  Claude Desktop         │
        │  Claude CLI             │
        │  Other MCP Clients      │
        └─────────────────────────┘
```

## Installation

### 1. Install Dependencies

```bash
cd /opt/vps-agent/core
pip install -r requirements-mcp.txt
```

### 2. Install Systemd Service

```bash
sudo cp /opt/vps-agent/configs/mcp-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mcp-server
sudo systemctl start mcp-server
```

### 3. Verify Installation

```bash
sudo systemctl status mcp-server
curl http://localhost:8000/health
```

## Configuration

### Environment Variables

Create or update `/opt/vps-agent/configs/.env`:

```env
# MCP Server
MCP_PORT=8000
MCP_HOST=0.0.0.0

# Redis (for caching)
REDIS_HOST=localhost
REDIS_PORT=6379

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=vps_agent
POSTGRES_USER=vps_agent
POSTGRES_PASSWORD=your_password
```

## Usage

### Direct Access

```bash
# Health check
curl http://localhost:8000/health

# Get RAM status
curl http://localhost:8000/ram

# List containers
curl http://localhost:8000/containers

# Get system info
curl http://localhost:8000/system

# Search memory
curl "http://localhost:8000/memory/search?query=hello&limit=5"
```

### Claude Desktop Integration

Add to your Claude Desktop config (`~/.claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "vps-agent": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp"]
    }
  }
}
```

### Claude CLI Integration

Add to your MCP config:

```json
{
  "mcpServers": {
    "vps-agent": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp"]
    }
  }
}
```

### Remote Access (via SSH Tunnel)

For remote access to the MCP server, use an SSH tunnel:

```bash
# Local port forwarding
ssh -L 8000:localhost:8000 root@107.175.1.42

# Then access locally
curl http://localhost:8000/health
```

Or configure Claude Desktop with SSH tunnel:

```json
{
  "mcpServers": {
    "vps-agent": {
      "command": "ssh",
      "args": ["-L", "8000:localhost:8000", "root@107.175.1.42", "npx", "mcp-remote", "http://localhost:8000/mcp"]
    }
  }
}
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `get_ram_status` | Get current RAM usage | None |
| `list_containers` | List all Docker containers | None |
| `get_container_status` | Get status of specific container | `container_name` (string) |
| `stop_container` | Stop a running container | `container_name` (string) |
| `start_container` | Start a stopped container | `container_name` (string) |
| `restart_container` | Restart a container | `container_name` (string) |
| `list_services` | List all core services | None |
| `get_system_info` | Get system information | None |
| `search_memory` | Search conversation memory | `query` (string), `limit` (int) |
| `get_facts` | Get stored facts | `user_id` (string) |

## Docker Alternative

You can also run the MCP server as a Docker container:

```yaml
# docker-compose.mcp.yml
version: '3.8'

services:
  mcp-server:
    image: python:3.12-slim
    container_name: vps-agent-mcp
    working_dir: /opt/vps-agent/core
    environment:
      - PYTHONPATH=/opt/vps-agent/core
    volumes:
      - ./:/opt/vps-agent:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - "8000:8000"
    command: python mcp_server.py
    restart: unless-stopped
```

## Security Considerations

- **Local Access Only**: The MCP server listens on `localhost` by default
- **SSH Tunnel for Remote Access**: Use SSH tunneling for remote connections
- **Authentication**: Add OAuth 2.0 authentication using `AuthConfig` if needed
- **Rate Limiting**: Consider adding rate limiting for production use

## Troubleshooting

### Check Service Status

```bash
sudo systemctl status mcp-server
journalctl -u mcp-server -f
```

### Check Logs

```bash
journalctl -u mcp-server --since "1 hour ago"
```

### Test Connectivity

```bash
curl -v http://localhost:8000/health
```

## API Documentation

Full API documentation available at: `http://localhost:8000/docs`

OpenAPI schema at: `http://localhost:8000/openapi.json`
