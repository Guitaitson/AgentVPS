import pytest

from core.vps_agent.agent import process_message_async


class _FakeGraph:
    async def ainvoke(self, initial_state, config=None):
        return {"response": f"ok:{initial_state['user_message']}"}


@pytest.mark.asyncio
async def test_process_message_async_emits_progress(monkeypatch):
    events = []

    async def callback(event, payload):
        events.append((event, payload))

    monkeypatch.setattr("core.vps_agent.agent.get_agent_graph", lambda: _FakeGraph())

    response = await process_message_async("user-1", "teste", progress_callback=callback)

    assert response == "ok:teste"
    assert [event for event, _payload in events] == ["received", "routing", "done"]
