import pytest

from core.integrations.external_mcp import RemoteMCPClient


class _MockResponse:
    def __init__(self, *, json_data=None, headers=None, status_code=200, text=""):
        self._json_data = json_data
        self.headers = headers or {}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return self._json_data


@pytest.mark.asyncio
async def test_remote_mcp_client_supports_stateless_http_without_session(monkeypatch):
    responses = [
        _MockResponse(json_data={"result": {"protocolVersion": "2024-11-05"}}, headers={}),
        _MockResponse(
            json_data={
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": '{"status": "ok", "service": "fleetintel"}',
                        }
                    ]
                }
            }
        ),
    ]

    async def fake_post(self, url, json=None, headers=None):
        return responses.pop(0)

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    client = RemoteMCPClient(
        base_url="https://example.com/mcp",
        token="token",
        client_name="test-client",
        server_name="fleetintel",
    )

    result = await client.call_tool("get_operations_status", {})

    assert result["status"] == "ok"
    assert result["service"] == "fleetintel"
