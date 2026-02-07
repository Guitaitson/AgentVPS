#!/usr/bin/env python3
"""
MCP Server for VPS-Agent - Exposes agent tools via Model Context Protocol.

Usage:
    python mcp_server.py

The server will be available at http://localhost:8000/mcp
"""
import asyncio
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Add core to path
sys.path.insert(0, '/opt/vps-agent/core')

from resource_manager.manager import ResourceManager
from vps_agent.memory import AgentMemory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ lifespan context manager for startup/shutdown """
    # Startup
    print("[MCP] Starting VPS-Agent MCP Server...")
    yield
    # Shutdown
    print("[MCP] Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="VPS-Agent MCP Server",
    description="Exposes VPS management tools via MCP protocol",
    version="1.0.0",
    lifespan=lifespan
)


# Initialize managers
resource_manager = ResourceManager()
memory = AgentMemory()


# MCP Tools - Expose agent capabilities as MCP tools

@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "vps-agent-mcp"}


@app.get("/ram")
async def get_ram_status() -> dict:
    """Get current RAM status of the VPS."""
    try:
        ram_info = resource_manager.get_ram_status()
        return {
            "status": "success",
            "ram": ram_info
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/containers")
async def list_containers() -> dict:
    """List all Docker containers and their status."""
    try:
        containers = resource_manager.list_containers()
        return {
            "status": "success",
            "containers": containers
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/containers/{container_name}/status")
async def get_container_status(container_name: str) -> dict:
    """Get status of a specific container."""
    try:
        status = resource_manager.get_container_status(container_name)
        return {
            "status": "success",
            "container": status
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/containers/{container_name}/stop")
async def stop_container(container_name: str) -> dict:
    """Stop a running container."""
    try:
        resource_manager.stop_container(container_name)
        return {
            "status": "success",
            "message": f"Container {container_name} stopped"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/containers/{container_name}/start")
async def start_container(container_name: str) -> dict:
    """Start a stopped container."""
    try:
        resource_manager.start_container(container_name)
        return {
            "status": "success",
            "message": f"Container {container_name} started"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/containers/{container_name}/restart")
async def restart_container(container_name: str) -> dict:
    """Restart a container."""
    try:
        resource_manager.restart_container(container_name)
        return {
            "status": "success",
            "message": f"Container {container_name} restarted"
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/services")
async def list_services() -> dict:
    """List all core services and their status."""
    try:
        services = resource_manager.list_services()
        return {
            "status": "success",
            "services": services
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/system")
async def get_system_info() -> dict:
    """Get system information (CPU, RAM, Disk)."""
    try:
        info = resource_manager.get_system_info()
        return {
            "status": "success",
            "system": info
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/memory/search")
async def search_memory(query: str, limit: int = 5) -> dict:
    """Search conversation memory for similar contexts."""
    try:
        results = memory.search_similar(query, limit=limit)
        return {
            "status": "success",
            "results": results
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/memory/facts")
async def get_facts(user_id: str = "default") -> dict:
    """Get stored facts for a user."""
    try:
        facts = memory.get_all_facts(user_id)
        return {
            "status": "success",
            "facts": facts
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Create MCP server with FastAPI-MCP
mcp = FastApiMCP(
    app,
    name="VPS-Agent MCP Server",
    description="Model Context Protocol server for VPS management",
    include_health=True,  # Include /health endpoint
    include_routes=True,   # Include all routes as tools
)


# Mount the MCP server
mcp.mount_http()


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 50)
    print("VPS-Agent MCP Server")
    print("=" * 50)
    print("Starting MCP server...")
    print("MCP endpoint: http://localhost:8000/mcp")
    print("Docs: http://localhost:8000/docs")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
