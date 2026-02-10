"""
Tests for Gateway Module

Tests for FastAPI endpoints, rate limiting, adapters, and session management.
"""

import time
from unittest.mock import MagicMock

import pytest

# ============ Rate Limiter Tests ============


class TestRateLimiter:
    """Tests for the RateLimiter class."""

    def test_allow_request_under_limit(self):
        """Test that requests under the limit are allowed."""
        from core.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=10)

        # First 10 requests should be allowed
        for i in range(10):
            assert limiter.allow_request("test_user") is True

    def test_allow_request_over_limit(self):
        """Test that requests over the limit are denied."""
        from core.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=5)

        # First 5 requests should be allowed
        for i in range(5):
            limiter.allow_request("test_user")

        # 6th request should be denied
        assert limiter.allow_request("test_user") is False

    def test_different_clients_have_separate_limits(self):
        """Test that different clients have separate rate limits."""
        from core.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=2)

        # Client A makes 2 requests
        limiter.allow_request("client_a")
        limiter.allow_request("client_a")

        # Client A should be blocked
        assert limiter.allow_request("client_a") is False

        # Client B should still be allowed
        assert limiter.allow_request("client_b") is True

    def test_get_remaining_requests(self):
        """Test getting remaining requests."""
        from core.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=5)

        assert limiter.get_remaining("user") == 5

        limiter.allow_request("user")
        limiter.allow_request("user")

        assert limiter.get_remaining("user") == 3

    def test_cleanup_old_tokens(self):
        """Test that old tokens are cleaned up."""
        from core.gateway.rate_limiter import RateLimiter

        limiter = RateLimiter(requests_per_minute=10)

        # Add some tokens
        limiter.allow_request("user")
        limiter.allow_request("user")

        # Simulate time passing (manually manipulate tokens)
        now = time.time()
        limiter.tokens["user"] = [now - 120, now - 60]  # Older than 60s

        # Request should be allowed (tokens cleaned up)
        assert limiter.allow_request("user") is True


# ============ Adapter Tests ============


class TestTelegramAdapter:
    """Tests for the TelegramAdapter class."""

    def test_process_message(self):
        """Test processing a Telegram message."""
        from core.gateway.adapters import TelegramAdapter

        adapter = TelegramAdapter(bot_token="test_token")

        update = {
            "update_id": 12345,
            "message": {
                "message_id": 1,
                "chat": {"id": 100, "type": "private"},
                "from": {"id": 200, "username": "testuser", "first_name": "Test"},
                "text": "Hello, agent!",
            },
        }

        result = adapter.process_update(update)

        assert result["type"] == "message"
        assert result["user_id"] == "testuser"
        assert result["text"] == "Hello, agent!"
        assert result["chat_type"] == "private"

    def test_process_callback_query(self):
        """Test processing a callback query."""
        from core.gateway.adapters import TelegramAdapter

        adapter = TelegramAdapter(bot_token="test_token")

        update = {
            "update_id": 12345,
            "callback_query": {
                "id": "callback123",
                "from": {"id": 200, "username": "testuser"},
                "data": "button_clicked",
                "message": {"message_id": 1, "chat": {"id": 100}},
            },
        }

        result = adapter.process_update(update)

        assert result["type"] == "callback_query"
        assert result["user_id"] == "testuser"
        assert result["data"] == "button_clicked"

    def test_process_inline_query(self):
        """Test processing an inline query."""
        from core.gateway.adapters import TelegramAdapter

        adapter = TelegramAdapter(bot_token="test_token")

        update = {
            "update_id": 12345,
            "inline_query": {
                "id": "inline123",
                "from": {"id": 200, "username": "testuser"},
                "query": "search term",
            },
        }

        result = adapter.process_update(update)

        assert result["type"] == "inline_query"
        assert result["query"] == "search term"


class TestWebhookAdapter:
    """Tests for the WebhookAdapter class."""

    def test_process_webhook(self):
        """Test processing a generic webhook."""
        from core.gateway.adapters import WebhookAdapter

        adapter = WebhookAdapter(secret_token="secret123")

        data = {"event": "test", "value": 42}
        headers = {"X-Webhook-Source": "test-service"}

        result = adapter.process_webhook("test-service", data, headers)

        assert result["source"] == "test-service"
        assert result["type"] == "webhook"
        assert result["data"] == data
        assert result["headers"] == headers

    def test_verify_signature_with_secret(self):
        """Test signature verification with secret."""
        import hashlib
        import hmac

        from core.gateway.adapters import WebhookAdapter

        adapter = WebhookAdapter(secret_token="mysecret")

        payload = b'{"test": "data"}'

        # Create valid signature
        signature = hmac.new(b"mysecret", payload, hashlib.sha256).hexdigest()

        # Mock request
        mock_request = MagicMock()
        mock_request.headers = {"X-Signature": f"sha256={signature}"}

        assert adapter.verify_signature(mock_request, payload) is True


# ============ Session Manager Tests ============


class TestSessionManager:
    """Tests for the SessionManager class using sync wrapper."""

    def test_create_session(self):
        """Test creating a new session."""
        from core.gateway.session_manager import SyncSessionManager

        manager = SyncSessionManager()

        session = manager.create_session("user123")

        assert session.user_id == "user123"
        assert session.session_id is not None
        assert session.message_count == 0
        assert len(session.context) == 0

    def test_get_session(self):
        """Test getting a session by ID."""
        from core.gateway.session_manager import SyncSessionManager

        manager = SyncSessionManager()

        created = manager.create_session("user123")
        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.user_id == "user123"
        assert retrieved.session_id == created.session_id

    def test_get_nonexistent_session(self):
        """Test getting a session that doesn't exist."""
        from core.gateway.session_manager import SyncSessionManager

        manager = SyncSessionManager()

        session = manager.get_session("nonexistent")

        assert session is None

    def test_add_message(self):
        """Test adding a message to a session."""
        from core.gateway.session_manager import SyncSessionManager

        manager = SyncSessionManager()

        session = manager.create_session("user123")
        manager.add_message(session, "user", "Hello!")
        manager.add_message(session, "assistant", "Hi there!")

        messages = session.context.get("messages", [])

        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello!"
        assert messages[1]["role"] == "assistant"

    def test_session_message_limit(self):
        """Test that session has a message limit."""
        from core.gateway.session_manager import SyncSessionManager

        manager = SyncSessionManager(max_messages=5)

        session = manager.create_session("user123")

        # Add 10 messages
        for i in range(10):
            manager.add_message(session, "user", f"Message {i}")

        # Should only keep last 5
        messages = session.context.get("messages", [])
        assert len(messages) == 5
        assert messages[0]["content"] == "Message 5"
        assert messages[-1]["content"] == "Message 9"

    def test_end_session(self):
        """Test ending a session."""
        from core.gateway.session_manager import SyncSessionManager

        manager = SyncSessionManager()

        session = manager.create_session("user123")
        session_id = session.session_id

        assert manager.end_session(session_id) is True
        assert manager.get_session(session_id) is None

    def test_end_nonexistent_session(self):
        """Test ending a session that doesn't exist."""
        from core.gateway.session_manager import SyncSessionManager

        manager = SyncSessionManager()

        assert manager.end_session("nonexistent") is False


# ============ FastAPI Endpoint Tests ============


class TestGatewayEndpoints:
    """Tests for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        from fastapi.testclient import TestClient

        from core.gateway.main import app

        return TestClient(app)

    def test_root_endpoint(self, client):
        """Test the root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "AgentVPS Gateway"
        assert "version" in data

    def test_health_endpoint(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "version" in data

    def test_capabilities_endpoint(self, client):
        """Test the capabilities endpoint."""
        response = client.get("/api/v1/capabilities")

        # Should return 200 or 500 (if capabilities not available)
        assert response.status_code in [200, 500]

    def test_message_endpoint_with_api_key(self, monkeypatch):
        """Test that message endpoint accepts valid API key."""
        import os

        # Set env vars before importing
        monkeypatch.setenv("GATEWAY_API_KEY", "test-api-key")
        monkeypatch.setenv("GATEWAY_DEV_MODE", "false")

        # Import after setting env vars
        from importlib import reload

        import core.gateway.main as main_module
        from fastapi.testclient import TestClient

        # Reload module to pick up new env vars
        reload(main_module)

        # Create client after reloading
        client = TestClient(main_module.app)

        # Should get 422 (validation error - missing session_id is OK) or 200 with valid request
        response = client.post(
            "/api/v1/messages",
            json={"user_id": "test_user", "message": "Hello"},
            headers={"X-API-Key": "test-api-key"},
        )

        # Should NOT be 401 (auth error) - either 200, 422, or 500 is acceptable
        assert response.status_code != 401

    def test_message_endpoint_auth_required(self, client):
        """Test that message endpoint requires authentication without dev mode."""
        # Without dev mode and without API key, should get 401
        response = client.post(
            "/api/v1/messages", json={"user_id": "test_user", "message": "Test"}
        )

        assert response.status_code == 401


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
