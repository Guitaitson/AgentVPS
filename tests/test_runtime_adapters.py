import asyncio

import pytest

from core.orchestration import (
    AgentRuntimeAdapter,
    CodexOperatorAdapter,
    DeepAgentsAdapter,
    LocalSkillsAdapter,
    OpenClawAdapter,
    RuntimeExecutionRequest,
    RuntimeExecutionResult,
    RuntimeProtocol,
    RuntimeRouter,
    runtime_adapters,
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


@pytest.mark.asyncio
async def test_codex_operator_adapter_executes_codex_cli(monkeypatch, tmp_path):
    recorded = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self, prompt_bytes):
            recorded["prompt"] = prompt_bytes.decode("utf-8")
            output_index = recorded["command"].index("-o") + 1
            output_path = recorded["command"][output_index]
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(
                    '{"summary":"ok","answer":"Resposta do Codex","confidence":0.82,'
                    '"facts":["f1"],"tool_trace":[{"tool":"fleetintel_analyst","status":"ok"}],'
                    '"unresolved_items":[],"requires_human_approval":false}'
                )
            return b'{"type":"message"}\n', b""

        def kill(self):
            recorded["killed"] = True

        async def wait(self):
            return 0

    async def _fake_create_subprocess_exec(*command, **kwargs):
        recorded["command"] = list(command)
        recorded["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.shutil.which", lambda _cmd: "/usr/bin/codex"
    )
    monkeypatch.setattr("core.orchestration.runtime_adapters.os.path.exists", lambda _path: True)
    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.get_external_skill_contract",
        lambda _name: type(
            "Contract",
            (),
            {
                "external_name": "fleetintel-analyst",
                "version": "abc123",
                "execution_mode": "specialist_response",
                "response_owner": "specialist",
                "raw_output_policy": "on_user_request",
                "description": "Contract test",
                "instructions_markdown": "## Response Contract\nSummarize, do not dump raw JSON.",
            },
        )(),
    )
    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
    )

    adapter = CodexOperatorAdapter(
        codex_command="codex",
        workdir=str(tmp_path),
        python_executable="/opt/vps-agent/core/venv/bin/python",
        model="gpt-5.4",
        timeout_s=10,
    )
    result = await adapter.execute(
        RuntimeExecutionRequest(
            action="fleetintel_analyst",
            args={"query": "Analise o CNPJ 23.373.000/0001-32"},
            user_id="u1",
            context={"user_message": "Analise", "specialist_name": "fleetintel_analyst"},
            context_keys=["user_message", "specialist_name"],
            preferred_protocol=RuntimeProtocol.CODEX_OPERATOR,
        )
    )

    assert result.success is True
    assert result.runtime == RuntimeProtocol.CODEX_OPERATOR
    assert result.output["answer"] == "Resposta do Codex"
    assert "fleetintel_analyst" in recorded["prompt"]
    assert "Response Contract" in recorded["prompt"]
    assert "do not dump raw JSON" in recorded["prompt"]
    assert "--output-schema" in recorded["command"]


@pytest.mark.asyncio
async def test_codex_operator_adapter_supports_synthesizer_mode(monkeypatch, tmp_path):
    recorded = {}

    class _FakeProcess:
        returncode = 0

        async def communicate(self, prompt_bytes):
            recorded["prompt"] = prompt_bytes.decode("utf-8")
            output_index = recorded["command"].index("-o") + 1
            output_path = recorded["command"][output_index]
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(
                    '{"summary":"ok","answer":"Resposta executiva","confidence":0.91,'
                    '"facts":["f1"],"tool_trace":[{"tool":"fleetintel_analyst","status":"ok"}],'
                    '"unresolved_items":[],"requires_human_approval":false}'
                )
            return b"", b""

        async def wait(self):
            return 0

    async def _fake_create_subprocess_exec(*command, **kwargs):
        recorded["command"] = list(command)
        recorded["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.shutil.which", lambda _cmd: "/usr/bin/codex"
    )
    monkeypatch.setattr("core.orchestration.runtime_adapters.os.path.exists", lambda _path: True)
    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.get_external_skill_contract",
        lambda _name: type(
            "Contract",
            (),
            {
                "external_name": "fleetintel-analyst",
                "version": "abc123",
                "execution_mode": "specialist_response",
                "response_owner": "specialist",
                "raw_output_policy": "on_user_request",
                "description": "Contract test",
                "instructions_markdown": "## Response Contract\nSummarize, do not dump raw JSON.",
            },
        )(),
    )
    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
    )

    adapter = CodexOperatorAdapter(
        codex_command="codex",
        workdir=str(tmp_path),
        python_executable="/opt/vps-agent/core/venv/bin/python",
        timeout_s=10,
    )
    result = await adapter.execute(
        RuntimeExecutionRequest(
            action="fleetintel_analyst",
            args={
                "query": "Use o FleetIntel Analyst para me dar os latest insights do FleetIntel.",
                "specialist_result": '{"items":[{"empresa":"A"}]}',
            },
            user_id="u1",
            context={
                "codex_mode": "synthesizer",
                "specialist_result": '{"items":[{"empresa":"A"}]}',
            },
            context_keys=["codex_mode", "specialist_result"],
            preferred_protocol=RuntimeProtocol.CODEX_OPERATOR,
        )
    )

    assert result.success is True
    assert result.output["answer"] == "Resposta executiva"
    assert "Voce e o sintetizador Codex do AgentVPS." in recorded["prompt"]
    assert "Nao chame especialistas novamente." in recorded["prompt"]
    assert "Working data do especialista" in recorded["prompt"]
    assert "run-skill" not in recorded["prompt"]


@pytest.mark.asyncio
async def test_codex_operator_adapter_accepts_valid_output_even_with_nonzero_exit(
    monkeypatch, tmp_path
):
    class _FakeProcess:
        returncode = 1

        async def communicate(self, _prompt_bytes):
            output_path = recorded["command"][recorded["command"].index("-o") + 1]
            with open(output_path, "w", encoding="utf-8") as fh:
                fh.write(
                    '{"summary":"ok","answer":"Resposta do Codex","confidence":0.82,'
                    '"facts":["f1"],"tool_trace":[{"tool":"fleetintel_analyst","status":"ok"}],'
                    '"unresolved_items":[],"requires_human_approval":false}'
                )
            return b"", b"warning"

        async def wait(self):
            return 1

    recorded = {}

    async def _fake_create_subprocess_exec(*command, **kwargs):
        recorded["command"] = list(command)
        recorded["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.shutil.which", lambda _cmd: "/usr/bin/codex"
    )
    monkeypatch.setattr("core.orchestration.runtime_adapters.os.path.exists", lambda _path: True)
    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
    )

    adapter = CodexOperatorAdapter(codex_command="codex", workdir=str(tmp_path), timeout_s=10)
    result = await adapter.execute(
        RuntimeExecutionRequest(
            action="fleetintel_analyst",
            args={"query": "Analise o CNPJ 23.373.000/0001-32"},
            user_id="u1",
            preferred_protocol=RuntimeProtocol.CODEX_OPERATOR,
        )
    )

    assert result.success is True
    assert result.output["answer"] == "Resposta do Codex"


@pytest.mark.asyncio
async def test_codex_operator_adapter_kills_process_group_on_timeout(monkeypatch, tmp_path):
    recorded = {}

    class _HungProcess:
        returncode = None
        pid = 4242

        async def communicate(self, _prompt_bytes):
            await asyncio.sleep(1)
            return b"", b""

        def kill(self):
            recorded["killed"] = True

        async def wait(self):
            recorded["waited"] = True
            return 0

    async def _fake_create_subprocess_exec(*command, **kwargs):
        recorded["command"] = list(command)
        recorded["kwargs"] = kwargs
        return _HungProcess()

    def _fake_killpg(pid, sig):
        recorded["killpg"] = (pid, sig)

    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.shutil.which", lambda _cmd: "/usr/bin/codex"
    )
    monkeypatch.setattr("core.orchestration.runtime_adapters.os.path.exists", lambda _path: True)
    monkeypatch.setattr(
        "core.orchestration.runtime_adapters.asyncio.create_subprocess_exec",
        _fake_create_subprocess_exec,
    )
    monkeypatch.setattr(runtime_adapters.os, "killpg", _fake_killpg, raising=False)

    adapter = CodexOperatorAdapter(
        codex_command="codex",
        workdir=str(tmp_path),
        timeout_s=0,
    )
    result = await adapter.execute(
        RuntimeExecutionRequest(
            action="brazilcnpj",
            args={"query": "Enriqueca o CNPJ 23.373.000/0001-32"},
            user_id="u1",
            preferred_protocol=RuntimeProtocol.CODEX_OPERATOR,
        )
    )

    assert result.success is False
    assert result.error == "Codex operator timeout"
    if "killpg" in recorded:
        assert recorded["killpg"][0] == 4242
    else:
        assert recorded["killed"] is True
    assert recorded["waited"] is True
