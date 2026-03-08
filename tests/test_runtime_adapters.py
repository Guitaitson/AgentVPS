import pytest

from core.orchestration import (
    AgentRuntimeAdapter,
    DeepAgentsAdapter,
    LocalSkillsAdapter,
    OpenClawAdapter,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
    RuntimeProtocol,
    RuntimeRouter,
)


class DummyRegistry:
    def __init__(self):
        self.calls = []

    def get(self, name: str):
        if name == "shell_exec":
            return object()
        return None

    async def execute_skill(self, name: str, args: dict):
        self.calls.append((name, args))
        return f"executed:{name}:{args.get('command', '')}"


class CapturingAdapter(AgentRuntimeAdapter):
    def __init__(self, protocol: RuntimeProtocol):
        self.protocol = protocol
        self.last_request = None

    async def execute(self, request: RuntimeExecutionRequest) -> RuntimeExecutionResult:
        self.last_request = request
        return RuntimeExecutionResult(
            success=True,
            output={"action": request.action},
            runtime=self.protocol,
            latency_ms=1,
        )


class _NonMatchingLocalAdapter(CapturingAdapter):
    def can_handle(self, request: RuntimeExecutionRequest) -> bool:  # noqa: ARG002
        return False


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response_payload: dict):
        self._response_payload = response_payload
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, json: dict, headers: dict | None = None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        return _FakeResponse(self._response_payload)


@pytest.mark.asyncio
async def test_local_skills_adapter_executes_registry_skill():
    registry = DummyRegistry()
    adapter = LocalSkillsAdapter(registry=registry)

    result = await adapter.execute(
        RuntimeExecutionRequest(
            action="shell_exec",
            args={"command": "whoami"},
            user_id="u1",
        )
    )

    assert result.success is True
    assert result.runtime == RuntimeProtocol.LOCAL_SKILLS
    assert registry.calls == [("shell_exec", {"command": "whoami"})]


@pytest.mark.asyncio
async def test_runtime_router_respects_preferred_protocol():
    local = CapturingAdapter(RuntimeProtocol.LOCAL_SKILLS)
    a2a = CapturingAdapter(RuntimeProtocol.A2A)
    router = RuntimeRouter([local, a2a])

    result = await router.dispatch(
        RuntimeExecutionRequest(
            action="shell_exec",
            args={},
            user_id="u1",
            preferred_protocol=RuntimeProtocol.A2A,
        )
    )

    assert result.runtime == RuntimeProtocol.A2A
    assert a2a.last_request is not None


@pytest.mark.asyncio
async def test_runtime_router_applies_least_privilege_context_redaction():
    local = CapturingAdapter(RuntimeProtocol.LOCAL_SKILLS)
    router = RuntimeRouter([local])

    await router.dispatch(
        RuntimeExecutionRequest(
            action="shell_exec",
            args={"command": "echo ok"},
            user_id="u1",
            context={
                "summary": "safe",
                "api_key": "secret-value",
                "internal_notes": "do not share",
            },
            context_keys=["summary", "api_key"],
        )
    )

    assert local.last_request is not None
    assert local.last_request.context == {
        "summary": "safe",
        "api_key": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_deepagents_adapter_maps_payload_contract(monkeypatch):
    fake_client = _FakeAsyncClient({"success": True, "output": {"result": "ok"}})

    class _Factory:
        def __init__(self, timeout: int):
            self.timeout = timeout

        async def __aenter__(self):
            return await fake_client.__aenter__()

        async def __aexit__(self, exc_type, exc, tb):
            return await fake_client.__aexit__(exc_type, exc, tb)

    monkeypatch.setattr("core.orchestration.runtime_adapters.httpx.AsyncClient", _Factory)

    adapter = DeepAgentsAdapter(endpoint="https://deepagents.local/run", timeout_s=12)
    result = await adapter.execute(
        RuntimeExecutionRequest(
            action="plan_task",
            args={"goal": "sync"},
            user_id="u1",
            project_id="p1",
            context={"summary": "ctx"},
        )
    )

    assert result.success is True
    assert result.runtime == RuntimeProtocol.DEEPAGENTS
    assert fake_client.calls
    payload = fake_client.calls[0]["json"]
    assert payload["task"]["name"] == "plan_task"
    assert payload["identity"]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_openclaw_adapter_maps_payload_and_api_key(monkeypatch):
    fake_client = _FakeAsyncClient({"success": True, "output": {"result": "ok"}})

    class _Factory:
        def __init__(self, timeout: int):
            self.timeout = timeout

        async def __aenter__(self):
            return await fake_client.__aenter__()

        async def __aexit__(self, exc_type, exc, tb):
            return await fake_client.__aexit__(exc_type, exc, tb)

    monkeypatch.setattr("core.orchestration.runtime_adapters.httpx.AsyncClient", _Factory)

    adapter = OpenClawAdapter(
        endpoint="https://openclaw.local/gateway",
        api_key="secret-key",
        timeout_s=9,
    )
    result = await adapter.execute(
        RuntimeExecutionRequest(
            action="catalog_sync",
            args={"mode": "check"},
            user_id="u2",
            context={"foo": "bar"},
        )
    )

    assert result.success is True
    assert result.runtime == RuntimeProtocol.OPENCLAW
    assert fake_client.calls
    call = fake_client.calls[0]
    assert call["headers"]["X-API-Key"] == "secret-key"
    assert call["json"]["action"] == "catalog_sync"


@pytest.mark.asyncio
async def test_runtime_router_falls_back_to_deepagents_when_local_missing():
    local = _NonMatchingLocalAdapter(RuntimeProtocol.LOCAL_SKILLS)
    deepagents = CapturingAdapter(RuntimeProtocol.DEEPAGENTS)
    router = RuntimeRouter([local, deepagents])

    result = await router.dispatch(
        RuntimeExecutionRequest(
            action="not_a_local_skill",
            args={},
            user_id="u1",
        )
    )

    assert result.runtime == RuntimeProtocol.DEEPAGENTS
