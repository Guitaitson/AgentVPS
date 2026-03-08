from types import SimpleNamespace

from core.memory import MemoryType
from core.vps_langgraph.memory import AgentMemory


def _raise_db_unavailable():
    raise RuntimeError("db unavailable for test")


class _FakeQdrant:
    def __init__(self):
        self.upsert_calls = []
        self.search_calls = []
        self.delete_calls = []
        self.points = []

    def upsert(self, collection_name: str, points: list, wait: bool = False):
        self.upsert_calls.append(
            {"collection_name": collection_name, "points": points, "wait": wait}
        )

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        query_filter,
        limit: int,
        with_payload: bool,
    ):
        self.search_calls.append(
            {
                "collection_name": collection_name,
                "query_vector_len": len(query_vector),
                "limit": limit,
                "with_payload": with_payload,
                "query_filter": query_filter,
            }
        )
        return self.points[:limit]

    def delete(self, collection_name: str, points_selector, wait: bool = False):
        self.delete_calls.append(
            {
                "collection_name": collection_name,
                "points_selector": points_selector,
                "wait": wait,
            }
        )


def test_save_semantic_memory_upserts_qdrant(monkeypatch):
    fake_qdrant = _FakeQdrant()
    monkeypatch.setattr(AgentMemory, "_init_redis_client", lambda self: None)
    monkeypatch.setattr(AgentMemory, "_init_qdrant_client", lambda self: fake_qdrant)
    memory = AgentMemory()
    monkeypatch.setattr(memory, "_get_conn", _raise_db_unavailable)

    memory.save_typed_memory(
        user_id="u1",
        key="semantic:1",
        value={"text": "status da frota"},
        memory_type=MemoryType.SEMANTIC,
    )

    assert fake_qdrant.upsert_calls
    assert fake_qdrant.upsert_calls[0]["collection_name"] == memory._semantic_collection


def test_search_semantic_memory_prefers_qdrant_results(monkeypatch):
    fake_qdrant = _FakeQdrant()
    fake_qdrant.points = [
        SimpleNamespace(
            payload={
                "key": "semantic:abc",
                "value": {"text": "status da frota"},
                "text": "status da frota",
                "project_id": "p1",
            },
            score=0.91,
        )
    ]
    monkeypatch.setattr(AgentMemory, "_init_redis_client", lambda self: None)
    monkeypatch.setattr(AgentMemory, "_init_qdrant_client", lambda self: fake_qdrant)
    memory = AgentMemory()

    result = memory.search_semantic_memory(
        user_id="u1",
        query_text="qual status da frota",
        project_id="p1",
        limit=2,
    )

    assert result
    assert result[0]["key"] == "semantic:abc"
    assert fake_qdrant.search_calls


def test_search_semantic_memory_fallbacks_to_local_when_qdrant_unavailable(monkeypatch):
    monkeypatch.setattr(AgentMemory, "_init_redis_client", lambda self: None)
    monkeypatch.setattr(AgentMemory, "_init_qdrant_client", lambda self: None)
    memory = AgentMemory()
    monkeypatch.setattr(memory, "_get_conn", _raise_db_unavailable)

    memory.save_typed_memory(
        user_id="u1",
        key="semantic:local",
        value={"text": "atualizacao de catalogo de skills"},
        memory_type=MemoryType.SEMANTIC,
    )

    result = memory.search_semantic_memory(user_id="u1", query_text="catalogo skills", limit=3)

    assert result
    assert result[0]["key"] == "semantic:local"
