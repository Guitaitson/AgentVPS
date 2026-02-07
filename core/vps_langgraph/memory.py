"""
Sistema de memória do agente.
Duas dimensões: por usuário e global.
PostgreSQL para fatos, Redis para cache.
"""
import os
import json
from typing import Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor
import redis
from dotenv import load_dotenv

load_dotenv("/opt/vps-agent/core/.env")


class AgentMemory:
    """Gerencia memória persistente do agente."""
    
    def __init__(self):
        self._db_config = {
            "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "port": int(os.getenv("POSTGRES_PORT", 5432)),
            "dbname": os.getenv("POSTGRES_DB", "vps_agent"),
            "user": os.getenv("POSTGRES_USER"),
            "password": os.getenv("POSTGRES_PASSWORD"),
        }
        self._redis = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1"), 
            port=int(os.getenv("REDIS_PORT", 6379)), 
            decode_responses=True
        )
    
    def _get_conn(self):
        return psycopg2.connect(**self._db_config)
    
    # --- Memória por usuário ---
    
    def get_user_facts(self, user_id: str) -> dict:
        """Recupera todos os fatos conhecidos sobre um usuário."""
        # Tentar cache primeiro
        cache_key = f"user_facts:{user_id}"
        cached = self._redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT key, value, confidence FROM agent_memory "
            "WHERE user_id = %s AND memory_type = 'fact' "
            "ORDER BY confidence DESC",
            (user_id,)
        )
        facts = {row["key"]: row["value"] for row in cur.fetchall()}
        conn.close()
        
        # Cache por 5 minutos
        self._redis.setex(cache_key, 300, json.dumps(facts))
        return facts
    
    def save_fact(self, user_id: str, key: str, value: dict, confidence: float = 1.0):
        """Salva ou atualiza um fato sobre o usuário."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO agent_memory (user_id, memory_type, key, value, confidence)
            VALUES (%s, 'fact', %s, %s, %s)
            ON CONFLICT (user_id, memory_type, key) 
            DO UPDATE SET value = EXCLUDED.value, confidence = EXCLUDED.confidence
            """,
            (user_id, key, Json(value), confidence)
        )
        conn.commit()
        conn.close()
        
        # Invalida cache
        self._redis.delete(f"user_facts:{user_id}")
    
    def get_conversation_history(self, user_id: str, limit: int = 10) -> list:
        """Recupera histórico de conversa recente."""
        cache_key = f"conv_history:{user_id}:{limit}"
        cached = self._redis.get(cache_key)
        if cached:
            return json.loads(cached)
        
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT role, content, created_at as timestamp FROM conversation_log "
            "WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
            (user_id, limit)
        )
        history = [
            {"role": row["role"], "content": row["content"]}
            for row in cur.fetchall()
        ]
        conn.close()
        history.reverse()  # chronological order
        
        self._redis.setex(cache_key, 60, json.dumps(history))
        return history
    
    def save_conversation(
        self, user_id: str, role: str, content: str
    ):
        """Salva uma mensagem na conversa."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO conversation_log (user_id, role, content)
            VALUES (%s, %s, %s)
            """,
            (user_id, role, content)
        )
        conn.commit()
        conn.close()
        
        # Invalida cache
        self._redis.delete(f"conv_history:{user_id}:*")
    
    # --- Memória global ---
    
    def get_system_state(self) -> dict:
        """Recupera estado global do sistema."""
        cached = self._redis.get("system_state")
        if cached:
            return json.loads(cached)
        
        conn = self._get_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT key, value FROM system_state")
        state = {row["key"]: row["value"] for row in cur.fetchall()}
        conn.close()
        
        self._redis.setex("system_state", 60, json.dumps(state))
        return state
    
    def set_system_state(self, key: str, value: dict):
        """Atualiza estado global."""
        conn = self._get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO system_state (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (key, Json(value))
        )
        conn.commit()
        conn.close()
        
        self._redis.delete("system_state")
    
    # --- Cleanup ---
    
    def close(self):
        """Fecha conexões."""
        if hasattr(self, '_redis'):
            self._redis.close()
