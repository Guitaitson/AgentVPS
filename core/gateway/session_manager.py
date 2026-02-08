"""
Session Manager for Gateway Module

Manages user sessions for conversation continuity.
"""

import json
import time
import uuid
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class Session:
    """Represents a user session."""
    session_id: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)
    message_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = datetime.fromtimestamp(self.created_at).isoformat()
        data["last_activity"] = datetime.fromtimestamp(self.last_activity).isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            created_at=data.get("created_at", time.time()),
            last_activity=data.get("last_activity", time.time()),
            context=data.get("context", {}),
            message_count=data.get("message_count", 0),
            metadata=data.get("metadata", {})
        )


class SessionManager:
    """
    Manages user sessions for conversation continuity.
    
    Provides in-memory session storage with optional Redis backing
    for distributed deployments.
    """
    
    DEFAULT_TIMEOUT = 3600  # 1 hour timeout
    MAX_MESSAGES = 100  # Maximum messages per session
    
    def __init__(self, redis_client=None, timeout: int = None, max_messages: int = None):
        """
        Initialize the session manager.
        
        Args:
            redis_client: Optional Redis client for distributed storage
            timeout: Session timeout in seconds (default 1 hour)
            max_messages: Maximum messages per session
        """
        self.redis = redis_client
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_messages = max_messages or self.MAX_MESSAGES
        self.local_sessions: Dict[str, Session] = {}
    
    def _get_redis_key(self, session_id: str) -> str:
        """Get Redis key for a session."""
        return f"session:{session_id}"
    
    async def create_session(self, user_id: str, metadata: Dict[str, Any] = None) -> Session:
        """
        Create a new session for a user.
        
        Args:
            user_id: User identifier
            metadata: Optional initial metadata
        
        Returns:
            Created session
        """
        session_id = str(uuid.uuid4())
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            metadata=metadata or {}
        )
        
        if self.redis:
            key = self._get_redis_key(session_id)
            await self.redis.setex(
                key,
                self.timeout,
                json.dumps(session.to_dict())
            )
        else:
            self.local_sessions[session_id] = session
        
        logger.info(f"📝 Session created: {session_id} for user {user_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Session if found, None otherwise
        """
        if self.redis:
            key = self._get_redis_key(session_id)
            data = await self.redis.get(key)
            
            if data:
                session = Session.from_dict(json.loads(data))
                return session
            return None
        else:
            return self.local_sessions.get(session_id)
    
    async def update_session(self, session: Session) -> None:
        """
        Update an existing session.
        
        Args:
            session: Session to update
        """
        session.last_activity = time.time()
        
        if self.redis:
            key = self._get_redis_key(session.session_id)
            await self.redis.setex(
                key,
                self.timeout,
                json.dumps(session.to_dict())
            )
        else:
            self.local_sessions[session.session_id] = session
    
    async def end_session(self, session_id: str) -> bool:
        """
        End and delete a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session was deleted, False if not found
        """
        if self.redis:
            key = self._get_redis_key(session_id)
            result = await self.redis.delete(key)
            return result > 0
        else:
            if session_id in self.local_sessions:
                del self.local_sessions[session_id]
                return True
            return False
    
    async def add_message(self, session: Session, role: str, content: str) -> None:
        """
        Add a message to the session history.
        
        Args:
            session: Session to update
            role: Message role (user, assistant, system)
            content: Message content
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if "messages" not in session.context:
            session.context["messages"] = []
        
        session.context["messages"].append(message)
        session.message_count += 1
        
        # Trim old messages if over limit
        if len(session.context["messages"]) > self.max_messages:
            session.context["messages"] = session.context["messages"][-self.max_messages:]
        
        await self.update_session(session)
    
    async def get_conversation_history(self, session_id: str) -> list:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session identifier
        
        Returns:
            List of messages
        """
        session = await self.get_session(session_id)
        
        if session:
            return session.context.get("messages", [])
        return []
    
    async def cleanup_expired(self) -> int:
        """
        Clean up expired sessions.
        
        Note: This only works for local sessions, Redis handles expiry automatically.
        
        Returns:
            Number of sessions cleaned up
        """
        if not self.redis:
            now = time.time()
            expired = [
                sid for sid, session in self.local_sessions.items()
                if now - session.last_activity > self.timeout
            ]
            
            for sid in expired:
                del self.local_sessions[sid]
            
            logger.info(f"🧹 Cleaned up {len(expired)} expired sessions")
            return len(expired)
        
        return 0
    
    async def get_user_sessions(self, user_id: str) -> list:
        """
        Get all active sessions for a user.
        
        Note: This only works for local sessions.
        
        Args:
            user_id: User identifier
        
        Returns:
            List of active sessions
        """
        if not self.redis:
            return [
                s for s in self.local_sessions.values()
                if s.user_id == user_id
            ]
        return []


# Synchronous wrapper for non-async usage
class SyncSessionManager:
    """Synchronous wrapper for SessionManager."""
    
    def __init__(self, **kwargs):
        self.async_manager = SessionManager(**kwargs)
        self.loop = None
    
    def _get_loop(self):
        """Get or create event loop."""
        import asyncio
        if self.loop is None or self.loop.is_closed():
            self.loop = asyncio.new_event_loop()
        return self.loop
    
    def create_session(self, user_id: str, metadata: Dict[str, Any] = None) -> Session:
        loop = self._get_loop()
        return loop.run_until_complete(self.async_manager.create_session(user_id, metadata))
    
    def get_session(self, session_id: str) -> Optional[Session]:
        loop = self._get_loop()
        return loop.run_until_complete(self.async_manager.get_session(session_id))
    
    def update_session(self, session: Session) -> None:
        loop = self._get_loop()
        return loop.run_until_complete(self.async_manager.update_session(session))
    
    def end_session(self, session_id: str) -> bool:
        loop = self._get_loop()
        return loop.run_until_complete(self.async_manager.end_session(session_id))
    
    def add_message(self, session: Session, role: str, content: str) -> None:
        loop = self._get_loop()
        return loop.run_until_complete(self.async_manager.add_message(session, role, content))
    
    def get_conversation_history(self, session_id: str) -> list:
        loop = self._get_loop()
        return loop.run_until_complete(self.async_manager.get_conversation_history(session_id))


# Import logging
import logging
logger = logging.getLogger(__name__)
