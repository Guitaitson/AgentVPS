"""
Gateway Module - FastAPI-based HTTP interface for AgentVPS

Provides HTTP endpoints for:
- Telegram webhook integration
- REST API for agent interactions
- Health checks and monitoring
- Authentication and rate limiting
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from core.gateway.adapters import TelegramAdapter
from core.gateway.rate_limiter import RateLimiter
from core.vps_agent.agent import process_message_async

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)

# Load API key from environment
GATEWAY_API_KEY = os.getenv("GATEWAY_API_KEY")
GATEWAY_DEV_MODE = os.getenv("GATEWAY_DEV_MODE", "false").lower() == "true"

# Rate limiter (in-memory, replace with Redis in production)
rate_limiter = RateLimiter(requests_per_minute=60)


def verify_gateway_auth(api_key: Optional[str]) -> bool:
    """Verify if the provided API key is valid."""
    if GATEWAY_DEV_MODE:
        return True

    if not GATEWAY_API_KEY:
        # No API key configured, reject all requests
        return False

    return api_key == GATEWAY_API_KEY


# ============ Pydantic Models ============


class MessageRequest(BaseModel):
    """Request model for sending messages to the agent."""

    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., description="Message to process")
    session_id: Optional[str] = Field(None, description="Session ID for continuity")


class MessageResponse(BaseModel):
    """Response model for agent messages."""

    response: str
    session_id: str
    intent: Optional[str] = None
    confidence: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    components: dict


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str
    error_code: Optional[str] = None


# ============ Lifespan Context Manager ============


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context for startup and shutdown events."""
    logger.info("🚀 Gateway Module starting...")
    logger.info("📡 HTTP endpoints initializing...")
    yield
    logger.info("👋 Gateway Module shutting down...")


# ============ FastAPI App ============

app = FastAPI(
    title="AgentVPS Gateway",
    description="HTTP API for AgentVPS autonomous agent",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Security Dependencies ============


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
) -> str:
    """
    Verify API key or bearer token.

    Requires GATEWAY_API_KEY environment variable to be set.
    Set GATEWAY_DEV_MODE=true for development (bypasses auth).
    """
    # Check API key first
    if api_key and verify_gateway_auth(api_key):
        return f"apikey:{api_key[:8]}..."

    # Bearer token check (future JWT implementation)
    if credentials:
        # TODO: Implement JWT verification using credentials.credentials
        raise HTTPException(
            status_code=401,
            detail="Bearer token authentication not yet implemented. Use X-API-Key header.",
        )

    # No valid authentication
    raise HTTPException(
        status_code=401,
        detail=(
            "Authentication required. "
            "Set GATEWAY_DEV_MODE=true for development or "
            "provide X-API-Key header with valid API key."
        ),
    )


# ============ Routes ============


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {"service": "AgentVPS Gateway", "version": "1.0.0", "docs": "/docs"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns the status of the gateway and its dependencies.
    """
    components = {}

    # Check core agent
    try:
        # Basic import check
        components["agent"] = "healthy"
    except Exception as e:
        components["agent"] = f"unhealthy: {str(e)}"

    # Check memory
    try:
        from core.vps_langgraph.memory import AgentMemory

        AgentMemory()
        components["memory"] = "healthy"
    except Exception as e:
        components["memory"] = f"unhealthy: {str(e)}"

    overall_status = (
        "healthy" if all("healthy" in str(v) for v in components.values()) else "degraded"
    )

    return HealthResponse(status=overall_status, version="1.0.0", components=components)


@app.post(
    "/api/v1/messages",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    tags=["Messages"],
)
async def send_message(request: MessageRequest, user_identifier: str = Depends(verify_api_key)):
    """
    Send a message to the agent.

    This is the main endpoint for interacting with the agent via HTTP.
    """
    # Rate limiting
    client_id = request.user_id
    if not rate_limiter.allow_request(client_id):
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    try:
        logger.info(f"📨 Message from {request.user_id}: {request.message[:100]}...")

        # Process message through agent
        result = await process_message_async(
            user_id=request.user_id, message=request.message, session_id=request.session_id
        )

        return MessageResponse(
            response=result.get("response", "Erro ao processar mensagem"),
            session_id=result.get("session_id", request.session_id or ""),
            intent=result.get("intent"),
            confidence=result.get("intent_confidence"),
        )

    except Exception as e:
        logger.error(f"❌ Error processing message: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/api/v1/capabilities", tags=["Capabilities"])
async def get_capabilities():
    """Get the list of available capabilities."""
    try:
        from core.capabilities.registry import capabilities_registry

        capabilities = capabilities_registry.list_capabilities()
        return {"capabilities": [cap.to_dict() for cap in capabilities], "count": len(capabilities)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/webhook/telegram", tags=["Webhooks"])
async def telegram_webhook(request: Request):
    """
    Telegram webhook endpoint.

    Receives updates from Telegram and processes them through the agent.
    Isso unifica o entry point: Telegram → Gateway → Agent (em vez de polling).
    """
    # Verify rate limit
    if not rate_limiter.allow_request("telegram:webhook"):
        return JSONResponse(status_code=429, content={"error": "Rate limited"})

    try:
        update = await request.json()
        logger.info(f"📨 Telegram update received: {update.get('update_id', 'unknown')}")

        # Process through Telegram adapter
        adapter = TelegramAdapter()
        result = adapter.process_update(update)

        # Se for uma mensagem, processar através do agente
        if result.get("type") == "message" and result.get("text"):
            user_id = result.get("user_id")
            text = result.get("text")
            chat_id = result.get("chat_id")
            
            # Processar via agente
            agent_result = await process_message_async(
                user_id=user_id,
                message=text,
                session_id=chat_id
            )
            
            # Responder ao usuário
            response_text = agent_result.get("response", "Erro ao processar")
            adapter.send_message(chat_id, response_text)
            
            return {"ok": True, "processed": True, "response": response_text}

        return result

    except Exception as e:
        logger.error(f"❌ Telegram webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/sessions/{session_id}", tags=["Sessions"])
async def get_session(session_id: str):
    """Get session information."""
    try:
        from core.gateway.session_manager import SessionManager

        manager = SessionManager()
        session = manager.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return session

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Run Server ============


def run_server():
    """Main entry point for running the gateway server."""
    import os

    port = int(os.getenv("GATEWAY_PORT", "8080"))
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")

    logger.info(f"🌐 Starting Gateway on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
