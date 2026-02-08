"""
Adapters for Gateway Module

Provides protocol adapters for:
- Telegram Bot API
- Generic Webhooks
"""

import logging
import sys
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Add core to path
sys.path.insert(0, "/opt/vps-agent/core")

logger = logging.getLogger(__name__)


@dataclass
class TelegramUpdate:
    """Represents a Telegram update."""
    update_id: str
    message: Optional[Dict[str, Any]] = None
    callback_query: Optional[Dict[str, Any]] = None
    inline_query: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelegramUpdate":
        """Create from Telegram API response."""
        return cls(
            update_id=str(data.get("update_id", "")),
            message=data.get("message"),
            callback_query=data.get("callback_query"),
            inline_query=data.get("inline_query")
        )


class TelegramAdapter:
    """
    Adapter for Telegram Bot API.
    
    Handles incoming updates and formats them for the agent.
    """
    
    def __init__(self, bot_token: str = None):
        """
        Initialize the Telegram adapter.
        
        Args:
            bot_token: Telegram Bot Token (loaded from env if not provided)
        """
        self.bot_token = bot_token or "your-bot-token"
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    def process_update(self, update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a Telegram update.
        
        Args:
            update: Raw update from Telegram webhook
        
        Returns:
            Formatted result for agent processing
        """
        tg_update = TelegramUpdate.from_dict(update)
        
        logger.info(f"📨 Processing Telegram update {tg_update.update_id}")
        
        # Handle different update types
        if tg_update.message:
            return self._handle_message(tg_update.message)
        elif tg_update.callback_query:
            return self._handle_callback_query(tg_update.callback_query)
        elif tg_update.inline_query:
            return self._handle_inline_query(tg_update.inline_query)
        else:
            return {
                "update_id": tg_update.update_id,
                "type": "unknown",
                "text": "Unknown update type"
            }
    
    def _handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming message."""
        chat = message.get("chat", {})
        from_user = message.get("from", {})
        text = message.get("text", "")
        
        # Extract user info
        user_id = str(from_user.get("id", "unknown"))
        chat_id = str(chat.get("id", "unknown"))
        username = from_user.get("username", "unknown")
        first_name = from_user.get("first_name", "user")
        
        # Build user identifier (prefer username, fall back to user_id)
        identifier = username if username != "unknown" else f"tg_{user_id}"
        
        logger.info(f"💬 Message from {identifier}: {text[:100]}...")
        
        return {
            "update_id": str(message.get("message_id", "")),
            "type": "message",
            "user_id": identifier,
            "chat_id": chat_id,
            "message_id": str(message.get("message_id", "")),
            "text": text,
            "user": {
                "id": user_id,
                "username": username,
                "first_name": first_name
            },
            "chat_type": chat.get("type", "private")
        }
    
    def _handle_callback_query(self, callback_query: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a callback query (inline button press)."""
        from_user = callback_query.get("from", {})
        data = callback_query.get("data", "")
        message = callback_query.get("message", {})
        
        user_id = str(from_user.get("id", "unknown"))
        username = from_user.get("username", "unknown")
        identifier = username if username != "unknown" else f"tg_{user_id}"
        
        logger.info(f"🔘 Callback from {identifier}: {data}")
        
        return {
            "update_id": str(callback_query.get("id", "")),
            "type": "callback_query",
            "user_id": identifier,
            "data": data,
            "message_id": str(message.get("message_id", "")),
            "chat_id": str(message.get("chat", {}).get("id", ""))
        }
    
    def _handle_inline_query(self, inline_query: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an inline query."""
        from_user = inline_query.get("from", {})
        
        user_id = str(from_user.get("id", "unknown"))
        username = from_user.get("username", "unknown")
        identifier = username if username != "unknown" else f"tg_{user_id}"
        
        query = inline_query.get("query", "")
        
        logger.info(f"🔍 Inline query from {identifier}: {query}")
        
        return {
            "update_id": str(inline_query.get("id", "")),
            "type": "inline_query",
            "user_id": identifier,
            "query": query
        }
    
    def send_message(self, chat_id: str, text: str, **kwargs) -> Dict[str, Any]:
        """
        Send a message to a chat.
        
        Args:
            chat_id: Target chat ID
            text: Message text
            **kwargs: Additional parameters (parse_mode, reply_markup, etc.)
        
        Returns:
            API response
        """
        import requests
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            **kwargs
        }
        
        response = requests.post(
            f"{self.api_url}/sendMessage",
            json=payload,
            timeout=10
        )
        
        return response.json()
    
    def answer_callback(self, callback_id: str, text: str = None, show_alert: bool = False) -> Dict[str, Any]:
        """Answer a callback query."""
        import requests
        
        payload = {
            "callback_query_id": callback_id,
            "show_alert": show_alert
        }
        
        if text:
            payload["text"] = text
        
        response = requests.post(
            f"{self.api_url}/answerCallbackQuery",
            json=payload,
            timeout=10
        )
        
        return response.json()


class WebhookAdapter:
    """
    Generic webhook adapter.
    
    Handles incoming webhooks from various sources.
    """
    
    def __init__(self, secret_token: str = None):
        """
        Initialize the webhook adapter.
        
        Args:
            secret_token: Optional secret token for verification
        """
        self.secret_token = secret_token
    
    def verify_signature(self, request: Any, payload: bytes, signature: str = None) -> bool:
        """
        Verify webhook signature.
        
        Args:
            request: FastAPI request object
            payload: Raw request body
            signature: Signature from header
        
        Returns:
            True if signature is valid
        """
        if not self.secret_token:
            return True
        
        # Check for signature in various headers
        headers = dict(request.headers)
        received_sig = signature or headers.get("X-Signature") or headers.get("X-Hub-Signature-256")
        
        if not received_sig:
            return False
        
        # Verify signature (implementation depends on source)
        import hmac
        import hashlib
        
        expected = hmac.new(
            self.secret_token.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(received_sig, f"sha256={expected}")
    
    def process_webhook(self, source: str, data: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Process a generic webhook.
        
        Args:
            source: Webhook source identifier
            data: Webhook payload
            headers: Request headers
        
        Returns:
            Formatted result for agent processing
        """
        logger.info(f"📥 Webhook from {source}: {str(data)[:200]}...")
        
        return {
            "source": source,
            "type": "webhook",
            "data": data,
            "headers": headers or {}
        }


class SlackAdapter:
    """
    Adapter for Slack webhooks and events.
    """
    
    def __init__(self, signing_secret: str = None):
        self.signing_secret = signing_secret
    
    def verify_request(self, request: Any, payload: bytes) -> bool:
        """Verify Slack request signature."""
        if not self.signing_secret:
            return True
        
        import hmac
        import hashlib
        import time
        
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
        
        # Check timestamp to prevent replay attacks
        try:
            if abs(time.time() - int(timestamp)) > 60 * 5:
                return False
        except ValueError:
            return False
        
        sig_basestring = f"v0:{timestamp}:{payload.decode()}"
        signature = hmac.new(
            self.signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        expected = f"v0={signature}"
        received = request.headers.get("X-Slack-Signature", "")
        
        return hmac.compare_digest(expected, received)
    
    def process_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a Slack event."""
        event = event_data.get("event", {})
        
        user_id = event.get("user", "unknown")
        text = event.get("text", "")
        channel = event.get("channel", "unknown")
        
        logger.info(f"💬 Slack event from {user_id}: {text[:100]}...")
        
        return {
            "source": "slack",
            "type": "event",
            "user_id": f"slack_{user_id}",
            "channel": channel,
            "text": text,
            "event_type": event.get("type")
        }
    
    def process_interaction(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process a Slack interaction (button clicks, etc.)."""
        user = payload.get("user", {})
        user_id = user.get("id", "unknown")
        actions = payload.get("actions", [])
        
        action = actions[0] if actions else {}
        value = action.get("value", "")
        
        return {
            "source": "slack",
            "type": "interaction",
            "user_id": f"slack_{user_id}",
            "action": action.get("type"),
            "value": value
        }
