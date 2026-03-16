import httpx
import pytest

from core.integrations.external_mcp import RemoteMCPClient, RemoteMCPConnection, RemoteMCPError


class _MockResponse:
    def __init__(self, *, json_data=None, headers=None, status_code=200, text=""):
        self._json_data = json_data
        self.headers = headers or {}
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_remote_mcp_client_supports_static_cf_access_headers(monkeypatch):
    responses = [
        _MockResponse(json_data={"result": {"protocolVersion": "2024-11-05"}}, headers={}),
        _MockResponse(
            json_data={
                "result": {
                    "content": [
                        {"type": "text", "text": '{"status": "ok", "service": "fleetintel"}'}
                    ]
                }
            }
        ),
    ]
    seen_headers = []

    async def fake_post(self, url, json=None, headers=None):
        seen_headers.append(headers or {})
        return responses.pop(0)

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = RemoteMCPClient(
        base_url="https://example.com/mcp",
        access_client_id="client-id",
        access_client_secret="client-secret",
        client_name="test-client",
        server_name="fleetintel",
    )

    result = await client.call_tool("get_operations_status", {})

    assert result["status"] == "ok"
    assert seen_headers[0]["CF-Access-Client-Id"] == "client-id"
    assert seen_headers[0]["CF-Access-Client-Secret"] == "client-secret"
    assert "Authorization" not in seen_headers[0]


@pytest.mark.asyncio
async def test_remote_mcp_client_retries_transient_502(monkeypatch):
    responses = [
        _MockResponse(json_data={"result": {"protocolVersion": "2024-11-05"}}, headers={}),
        _MockResponse(status_code=502, text="bad gateway"),
        _MockResponse(
            json_data={"result": {"content": [{"type": "text", "text": '{"status": "ok"}'}]}}
        ),
    ]
    calls = []

    async def fake_post(self, url, json=None, headers=None):
        calls.append(json["method"])
        return responses.pop(0)

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("asyncio.sleep", lambda *_args, **_kwargs: _completed_awaitable())

    client = RemoteMCPClient(
        base_url="https://example.com/mcp",
        access_client_id="client-id",
        access_client_secret="client-secret",
        client_name="test-client",
        server_name="fleetintel",
    )

    result = await client.call_tool("get_operations_status", {})

    assert result["status"] == "ok"
    assert calls == ["initialize", "tools/call", "tools/call"]


@pytest.mark.asyncio
async def test_remote_mcp_client_does_not_retry_auth_error_without_refresh(monkeypatch):
    calls = []

    async def fake_post(self, url, json=None, headers=None):
        calls.append(json["method"])
        return _MockResponse(status_code=403, text="forbidden")

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = RemoteMCPClient(
        base_url="https://example.com/mcp",
        access_client_id="client-id",
        access_client_secret="client-secret",
        client_name="test-client",
        server_name="fleetintel",
    )

    with pytest.raises(RemoteMCPError) as exc:
        await client.call_tool("get_operations_status", {})

    assert exc.value.status_code == 403
    assert calls == ["initialize"]


@pytest.mark.asyncio
async def test_remote_mcp_client_refreshes_bundle_once_after_initialize_403(monkeypatch):
    calls = []
    current = {
        "connection": RemoteMCPConnection(
            base_url="https://stale.example/mcp",
            access_client_id="stale-id",
            access_client_secret="stale-secret",
        )
    }

    async def fake_post(self, url, json=None, headers=None):
        calls.append((json["method"], headers.get("CF-Access-Client-Id")))
        if headers.get("CF-Access-Client-Id") == "stale-id":
            return _MockResponse(status_code=403, text="forbidden")
        if json["method"] == "initialize":
            return _MockResponse(
                json_data={"result": {"protocolVersion": "2024-11-05"}}, headers={}
            )
        return _MockResponse(
            json_data={"result": {"content": [{"type": "text", "text": '{"status": "ok"}'}]}}
        )

    async def refresh_callback():
        current["connection"] = RemoteMCPConnection(
            base_url="https://fresh.example/mcp",
            access_client_id="fresh-id",
            access_client_secret="fresh-secret",
        )
        return True

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = RemoteMCPClient(
        client_name="test-client",
        server_name="fleetintel",
        connection_provider=lambda: current["connection"],
        auth_refresh_callback=refresh_callback,
    )

    result = await client.call_tool("get_operations_status", {})

    assert result["status"] == "ok"
    assert calls == [
        ("initialize", "stale-id"),
        ("initialize", "fresh-id"),
        ("tools/call", "fresh-id"),
    ]


@pytest.mark.asyncio
async def test_remote_mcp_client_refreshes_bundle_once_after_tool_call_403(monkeypatch):
    calls = []
    current = {
        "connection": RemoteMCPConnection(
            base_url="https://stale.example/mcp",
            access_client_id="stale-id",
            access_client_secret="stale-secret",
        )
    }

    async def fake_post(self, url, json=None, headers=None):
        calls.append((json["method"], headers.get("CF-Access-Client-Id")))
        if json["method"] == "initialize":
            return _MockResponse(
                json_data={"result": {"protocolVersion": "2024-11-05"}}, headers={}
            )
        if headers.get("CF-Access-Client-Id") == "stale-id":
            return _MockResponse(status_code=403, text="forbidden")
        return _MockResponse(
            json_data={"result": {"content": [{"type": "text", "text": '{"status": "ok"}'}]}}
        )

    async def refresh_callback():
        current["connection"] = RemoteMCPConnection(
            base_url="https://fresh.example/mcp",
            access_client_id="fresh-id",
            access_client_secret="fresh-secret",
        )
        return True

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = RemoteMCPClient(
        client_name="test-client",
        server_name="fleetintel",
        connection_provider=lambda: current["connection"],
        auth_refresh_callback=refresh_callback,
    )

    result = await client.call_tool("get_operations_status", {})

    assert result["status"] == "ok"
    assert calls == [
        ("initialize", "stale-id"),
        ("tools/call", "stale-id"),
        ("initialize", "fresh-id"),
        ("tools/call", "fresh-id"),
    ]


@pytest.mark.asyncio
async def test_remote_mcp_client_retries_initialize_timeout(monkeypatch):
    attempts = {"count": 0}

    async def fake_post(self, url, json=None, headers=None):
        if json["method"] == "initialize":
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ReadTimeout("timeout")
            return _MockResponse(
                json_data={"result": {"protocolVersion": "2024-11-05"}}, headers={}
            )
        return _MockResponse(
            json_data={"result": {"content": [{"type": "text", "text": '{"status": "ok"}'}]}}
        )

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    monkeypatch.setattr("asyncio.sleep", lambda *_args, **_kwargs: _completed_awaitable())

    client = RemoteMCPClient(
        base_url="https://example.com/mcp",
        access_client_id="client-id",
        access_client_secret="client-secret",
        client_name="test-client",
        server_name="fleetintel",
    )

    result = await client.call_tool("get_operations_status", {})

    assert result["status"] == "ok"
    assert attempts["count"] == 2


async def _completed_awaitable():
    return None
