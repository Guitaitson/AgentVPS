#!/usr/bin/env python3
"""
MCP Server for VPS-Agent - Exposes agent tools via Model Context Protocol.

Usage:
    python mcp_server.py

The server will be available at http://localhost:8000/mcp
"""
import subprocess
import sys
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

# Add core to path
sys.path.insert(0, '/opt/vps-agent/core')

from resource_manager.manager import (
    get_available_ram,
    get_running_tools,
    get_tools_status,
    start_tool,
    stop_tool,
)


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


def get_docker_containers() -> list:
    """Get all Docker containers with their status."""
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Image}}"],
        capture_output=True, text=True
    )
    containers = []
    for line in result.stdout.strip().split("\n"):
        if line:
            parts = line.split("|")
            containers.append({
                "name": parts[0] if len(parts) > 0 else "",
                "status": parts[1] if len(parts) > 1 else "",
                "image": parts[2] if len(parts) > 2 else "",
            })
    return containers


def get_system_info() -> dict:
    """Get system information (CPU, RAM, Disk)."""
    # RAM
    ram_result = subprocess.run(["free", "-m"], capture_output=True, text=True)
    ram_lines = ram_result.stdout.strip().split("\n")
    ram_total = int(ram_lines[1].split()[1])
    ram_used = int(ram_lines[1].split()[2])
    ram_available = int(ram_lines[1].split()[6])
    
    # CPU
    cpu_result = subprocess.run(["top", "-bn1"], capture_output=True, text=True)
    cpu_line = [l for l in cpu_result.stdout.split("\n") if "Cpu(s)" in l][0]
    cpu_parts = cpu_line.split()
    cpu_idle = float(cpu_parts[3].replace(",", "."))
    cpu_usage = 100.0 - cpu_idle
    
    return {
        "ram_total_mb": ram_total,
        "ram_used_mb": ram_used,
        "ram_available_mb": ram_available,
        "ram_percent": round((ram_used / ram_total) * 100, 1),
        "cpu_usage_percent": round(cpu_usage, 1),
    }


# Health check endpoint
@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "vps-agent-mcp"}


# MCP Tools

@app.get("/ram")
async def get_ram_status() -> dict:
    """Get current RAM status of the VPS."""
    try:
        ram_info = get_available_ram()
        return {
            "status": "success",
            "available_ram_mb": ram_info
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/containers")
async def list_containers() -> dict:
    """List all Docker containers and their status."""
    try:
        containers = get_docker_containers()
        return {
            "status": "success",
            "containers": containers
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/tools")
async def list_tools() -> dict:
    """List all on-demand tools and their status."""
    try:
        tools_status = get_tools_status()
        return {
            "status": "success",
            "tools": tools_status
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/tools/{tool_name}/start")
async def start_tool_endpoint(tool_name: str) -> dict:
    """Start an on-demand tool."""
    try:
        success, message = start_tool(tool_name)
        return {
            "status": "success" if success else "error",
            "message": message
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/tools/{tool_name}/stop")
async def stop_tool_endpoint(tool_name: str) -> dict:
    """Stop an on-demand tool."""
    try:
        success, message = stop_tool(tool_name)
        return {
            "status": "success" if success else "error",
            "message": message
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/services")
async def list_services() -> dict:
    """List all core services and their status."""
    try:
        containers = get_docker_containers()
        # Filter for core services
        core_names = ["postgres", "redis", "telegram-bot", "langgraph", "vps-agent"]
        core_services = [c for c in containers if any(name in c["name"].lower() for name in core_names)]
        
        return {
            "status": "success",
            "services": core_services
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/system")
async def get_system_info_endpoint() -> dict:
    """Get system information (CPU, RAM, Disk)."""
    try:
        info = get_system_info()
        return {
            "status": "success",
            "system": info
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Create MCP server with FastAPI-MCP
mcp = FastApiMCP(
    app,
    name="VPS-Agent MCP Server",
    description="Model Context Protocol server for VPS management",
    include_health=True,
    include_routes=True,
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
