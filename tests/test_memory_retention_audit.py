from core.memory import MemoryPolicy, MemoryType
from core.vps_langgraph.memory import AgentMemory


def _raise_db_unavailable():
    raise RuntimeError("db unavailable for test")


def _retention_policy(limit: int) -> MemoryPolicy:
    retention = {
        MemoryType.EPISODIC: limit,
        MemoryType.SEMANTIC: 50,
        MemoryType.PROCEDURAL: 50,
        MemoryType.PROFILE: 50,
        MemoryType.GOALS: 50,
    }
    return MemoryPolicy(retention_limits=retention)


def test_typed_memory_enforces_retention_in_local_fallback(monkeypatch):
    monkeypatch.setattr(AgentMemory, "_init_redis_client", lambda self: None)
    memory = AgentMemory(policy=_retention_policy(limit=2))
    monkeypatch.setattr(memory, "_get_conn", _raise_db_unavailable)

    memory.save_typed_memory(
        user_id="u1",
        key="k1",
        value={"v": 1},
        memory_type=MemoryType.EPISODIC,
    )
    memory.save_typed_memory(
        user_id="u1",
        key="k2",
        value={"v": 2},
        memory_type=MemoryType.EPISODIC,
    )
    memory.save_typed_memory(
        user_id="u1",
        key="k3",
        value={"v": 3},
        memory_type=MemoryType.EPISODIC,
    )

    local_entries = memory._local_typed["u1"][MemoryType.EPISODIC]
    assert len(local_entries) == 2
    assert "k1" not in local_entries
    assert set(local_entries.keys()) == {"k2", "k3"}


def test_memory_audit_uses_local_buffer_when_db_unavailable(monkeypatch):
    monkeypatch.setattr(AgentMemory, "_init_redis_client", lambda self: None)
    memory = AgentMemory(policy=_retention_policy(limit=2))
    monkeypatch.setattr(memory, "_get_conn", _raise_db_unavailable)

    memory.save_fact("u1", "favorite_lang", {"name": "python"})
    events = memory.list_memory_audit(user_id="u1")

    assert events
    assert events[-1]["action"] == "save_fact"
    assert events[-1]["user_id"] == "u1"
