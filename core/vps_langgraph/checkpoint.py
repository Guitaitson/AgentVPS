"""
Checkpointing para LangGraph com PostgreSQL.

Persiste o estado do grafo no PostgreSQL para recuperação
em caso de falhas e para manter contexto entre sessões.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

try:
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg import Connection
    CHECKPOINT_AVAILABLE = True
except ImportError:
    CHECKPOINT_AVAILABLE = False
    PostgresSaver = None
    Connection = None

from .state import AgentState


def get_connection_string() -> str:
    """Retorna string de conexão com PostgreSQL."""
    host = os.getenv("POSTGRES_HOST", "127.0.0.1")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "vps_agent")
    user = os.getenv("POSTGRES_USER", "vps_agent")
    password = os.getenv("POSTGRES_PASSWORD", "")
    
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[Optional[PostgresSaver]]:
    """
    Context manager para o checkpointer PostgreSQL.
    
    Yields:
        PostgresSaver configurado ou None se não disponível
    """
    if not CHECKPOINT_AVAILABLE:
        yield None
        return
    
    conn_string = get_connection_string()
    
    try:
        # Criar conexão
        import psycopg
        
        conn = await psycopg.AsyncConnection.connect(conn_string)
        
        # Criar checkpointer
        checkpointer = PostgresSaver(conn)
        
        # Setup das tabelas
        await checkpointer.setup()
        
        yield checkpointer
        
        await conn.close()
        
    except Exception as e:
        print(f"Erro ao criar checkpointer: {e}")
        yield None


def create_sync_checkpointer() -> Optional[PostgresSaver]:
    """
    Cria checkpointer síncrono para uso com graph.sync().
    
    Returns:
        PostgresSaver configurado ou None se não disponível
    """
    if not CHECKPOINT_AVAILABLE:
        return None
    
    try:
        import psycopg
        
        conn_string = get_connection_string()
        conn = psycopg.connect(conn_string)
        
        checkpointer = PostgresSaver(conn)
        checkpointer.setup()
        
        return checkpointer
        
    except Exception as e:
        print(f"Erro ao criar checkpointer síncrono: {e}")
        return None


# Singleton para reutilização
_checkpointer_instance: Optional[PostgresSaver] = None


def get_checkpointer_instance() -> Optional[PostgresSaver]:
    """Retorna instância singleton do checkpointer."""
    global _checkpointer_instance
    
    if _checkpointer_instance is None:
        _checkpointer_instance = create_sync_checkpointer()
    
    return _checkpointer_instance


def close_checkpointer():
    """Fecha conexão do checkpointer."""
    global _checkpointer_instance
    
    if _checkpointer_instance is not None:
        try:
            _checkpointer_instance.conn.close()
        except:
            pass
        _checkpointer_instance = None


__all__ = [
    "get_checkpointer",
    "create_sync_checkpointer",
    "get_checkpointer_instance",
    "close_checkpointer",
    "CHECKPOINT_AVAILABLE",
]
