"""
MCP Server com SSE Transport - Sprint 4

Implementa o Model Context Protocol com Server-Sent Events
para streaming real de respostas.

Uso:
    python -m core.mcp_sse

O servidor expos tools via MCP com suporte a SSE.
Conecte via: http://localhost:8000/mcp
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from core.config import get_settings

# ============================================
# MCP Protocol Types
# ============================================


@dataclass
class MCPTool:
    """Representa uma tool MCP."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable = field(default=None)


@dataclass
class MCPResource:
    """Representa um resource MCP."""

    uri: str
    name: str
    description: str
    mime_type: str = "application/json"


@dataclass
class MCPPrompt:
    """Representa um prompt MCP."""

    name: str
    description: str
    arguments: List[Dict[str, Any]] = field(default_factory=list)


# ============================================
# MCP Server Implementation
# ============================================


class MCPServer:
    """
    Servidor MCP com suporte a SSE.

    Implementa o protocolo completo:
    - tools/list, tools/call
    - resources/list, resources/read
    - prompts/list, prompts/get
    """

    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.resources: Dict[str, MCPResource] = {}
        self.prompts: Dict[str, MCPPrompt] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Registra tools padrão do VPS-Agent."""

        # Tool: get_ram
        self.register_tool(
            MCPTool(
                name="get_ram",
                description="Get current RAM usage in MB",
                input_schema={"type": "object", "properties": {}, "required": []},
            )
        )

        # Tool: list_containers
        self.register_tool(
            MCPTool(
                name="list_containers",
                description="List all Docker containers",
                input_schema={
                    "type": "object",
                    "properties": {"all": {"type": "boolean", "default": False}},
                    "required": [],
                },
            )
        )

        # Tool: get_system_status
        self.register_tool(
            MCPTool(
                name="get_system_status",
                description="Get overall system status (RAM, disk, Docker)",
                input_schema={"type": "object", "properties": {}, "required": []},
            )
        )

        # Tool: check_postgres
        self.register_tool(
            MCPTool(
                name="check_postgres",
                description="Check PostgreSQL connection and status",
                input_schema={"type": "object", "properties": {}, "required": []},
            )
        )

        # Tool: check_redis
        self.register_tool(
            MCPTool(
                name="check_redis",
                description="Check Redis connection and status",
                input_schema={"type": "object", "properties": {}, "required": []},
            )
        )

        # Tool: execute_command
        self.register_tool(
            MCPTool(
                name="execute_command",
                description="Execute a shell command on the VPS",
                input_schema={
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "Command to execute"},
                        "timeout": {"type": "number", "default": 30},
                    },
                    "required": ["command"],
                },
            )
        )

    def register_tool(self, tool: MCPTool):
        """Registra uma tool."""
        self.tools[tool.name] = tool

    def register_resource(self, resource: MCPResource):
        """Registra um resource."""
        self.resources[resource.uri] = resource

    def register_prompt(self, prompt: MCPPrompt):
        """Registra um prompt."""
        self.prompts[prompt.name] = prompt

    # ========================================
    # MCP Protocol Methods
    # ========================================

    async def list_tools(self) -> Dict[str, Any]:
        """Lista todas as tools disponíveis."""
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
                for tool in self.tools.values()
            ]
        }

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Chama uma tool pelo nome."""
        if name not in self.tools:
            return {"error": f"Tool '{name}' not found"}

        self.tools[name]

        try:
            # Executa a tool
            if name == "get_ram":
                from core.tools.system_tools import get_ram_usage

                result = get_ram_usage()
            elif name == "list_containers":
                from core.tools.system_tools import list_docker_containers

                result = list_docker_containers()
            elif name == "get_system_status":
                from core.tools.system_tools import get_system_status

                result = get_system_status()
            elif name == "check_postgres":
                from core.tools.system_tools import check_postgres

                result = check_postgres()
            elif name == "check_redis":
                from core.tools.system_tools import check_redis

                result = check_redis()
            elif name == "execute_command":
                import subprocess

                cmd = arguments.get("command", "")
                timeout = arguments.get("timeout", 30)
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True, timeout=timeout
                )
                result = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            else:
                result = f"Tool '{name}' executed"

            return {"content": [{"type": "text", "text": str(result)}]}
        except Exception as e:
            return {"error": str(e)}

    async def list_resources(self) -> Dict[str, Any]:
        """Lista todos os resources."""
        return {
            "resources": [
                {
                    "uri": res.uri,
                    "name": res.name,
                    "description": res.description,
                    "mimeType": res.mime_type,
                }
                for res in self.resources.values()
            ]
        }

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Lê um resource."""
        if uri not in self.resources:
            return {"error": f"Resource '{uri}' not found"}

        resource = self.resources[uri]

        # Por enquanto, retorna info básica
        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": resource.mime_type,
                    "text": json.dumps(
                        {"name": resource.name, "description": resource.description}
                    ),
                }
            ]
        }

    async def list_prompts(self) -> Dict[str, Any]:
        """Lista todos os prompts."""
        return {
            "prompts": [
                {
                    "name": prompt.name,
                    "description": prompt.description,
                    "arguments": prompt.arguments,
                }
                for prompt in self.prompts.values()
            ]
        }


# ============================================
# FastAPI App
# ============================================

app = FastAPI(
    title="VPS-Agent MCP Server (SSE)",
    description="Model Context Protocol with Server-Sent Events",
    version="2.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instância do servidor MCP
mcp_server = MCPServer()


# ============================================
# MCP Endpoints (JSON-RPC 2.0)
# ============================================


@app.post("/mcp/v1/tools/list")
async def mcp_list_tools():
    """MCP: list tools."""
    return await mcp_server.list_tools()


@app.post("/mcp/v1/tools/call")
async def mcp_call_tool(request: Request):
    """MCP: call a tool."""
    body = await request.json()
    name = body.get("name")
    arguments = body.get("arguments", {})
    return await mcp_server.call_tool(name, arguments)


@app.post("/mcp/v1/resources/list")
async def mcp_list_resources():
    """MCP: list resources."""
    return await mcp_server.list_resources()


@app.post("/mcp/v1/resources/read")
async def mcp_read_resource(request: Request):
    """MCP: read a resource."""
    body = await request.json()
    uri = body.get("uri")
    return await mcp_server.read_resource(uri)


@app.post("/mcp/v1/prompts/list")
async def mcp_list_prompts():
    """MCP: list prompts."""
    return await mcp_server.list_prompts()


# ============================================
# SSE Endpoint for Streaming
# ============================================


@app.get("/mcp/stream")
async def mcp_stream(request: Request):
    """
    Endpoint SSE para streaming de eventos MCP.
    Usado por clientes que suportam SSE (Server-Sent Events).
    """

    async def event_generator():
        # Envia evento de conexão
        yield {
            "event": "connected",
            "data": json.dumps({"status": "connected", "server": "vps-agent-mcp"}),
        }

        # Mantém conexão viva com heartbeats
        try:
            while True:
                await asyncio.sleep(30)
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({"time": asyncio.get_event_loop().time()}),
                }
        except asyncio.CancelledError:
            yield {"event": "disconnected", "data": json.dumps({"status": "disconnected"})}

    return EventSourceResponse(event_generator())


# ============================================
# WebSocket for Real-time Communication
# ============================================


@app.websocket("/mcp/ws")
async def mcp_websocket(websocket: WebSocket):
    """
    WebSocket para comunicação em tempo real com o MCP.
    Suporta streaming de tool results e notifications.
    """
    await websocket.accept()

    try:
        while True:
            # Recebe mensagem
            data = await websocket.receive_text()
            message = json.loads(data)

            method = message.get("method")
            params = message.get("params", {})

            # Processa método
            if method == "tools/list":
                result = await mcp_server.list_tools()
                await websocket.send_json({"id": message.get("id"), "result": result})

            elif method == "tools/call":
                result = await mcp_server.call_tool(params.get("name"), params.get("arguments", {}))
                await websocket.send_json({"id": message.get("id"), "result": result})

            elif method == "resources/list":
                result = await mcp_server.list_resources()
                await websocket.send_json({"id": message.get("id"), "result": result})

            else:
                await websocket.send_json(
                    {
                        "id": message.get("id"),
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }
                )

    except WebSocketDisconnect:
        pass


# ============================================
# Health & Info
# ============================================


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "healthy", "service": "vps-agent-mcp-sse"}


@app.get("/")
async def root():
    """Info endpoint."""
    get_settings()
    return {
        "name": "VPS-Agent MCP Server",
        "version": "2.0.0",
        "protocol": "MCP",
        "transport": "SSE + WebSocket",
        "tools_count": len(mcp_server.tools),
        "resources_count": len(mcp_server.resources),
        "prompts_count": len(mcp_server.prompts),
    }


# ============================================
# Main
# ============================================


def main():
    """Inicia o servidor MCP com SSE."""
    import uvicorn

    print("=" * 50)
    print("VPS-Agent MCP Server (SSE)")
    print("=" * 50)
    print("Endpoints:")
    print("  POST /mcp/v1/tools/list   - List tools")
    print("  POST /mcp/v1/tools/call  - Call tool")
    print("  GET  /mcp/stream         - SSE stream")
    print("  WS   /mcp/ws            - WebSocket")
    print("  GET  /                   - Info")
    print("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
