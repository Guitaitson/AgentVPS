import json

import pytest

from core.catalog import SkillsCatalogSyncEngine


def _raise_db_unavailable():
    raise RuntimeError("db unavailable in test")


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


@pytest.mark.asyncio
async def test_catalog_pin_and_unpin_fallback(tmp_path):
    cache_file = tmp_path / "cache.json"
    history_file = tmp_path / "history.json"
    pins_file = tmp_path / "pins.json"

    _write_json(
        cache_file,
        {
            "updated_at": "2026-03-08T00:00:00Z",
            "skills": [
                {
                    "skill_name": "external_shell",
                    "source_name": "lc",
                    "version": "1.0.0",
                    "schema_hash": "abc",
                    "payload": {"name": "external_shell"},
                    "status": "active",
                }
            ],
            "diff": {},
        },
    )

    engine = SkillsCatalogSyncEngine(sources_file=str(tmp_path / "sources.json"))
    engine._get_conn = _raise_db_unavailable
    engine._fallback_cache_path = str(cache_file)
    engine._history_file_path = str(history_file)
    engine._pins_file_path = str(pins_file)

    pinned = await engine.pin(
        skill_name="external_shell",
        source_name="lc",
        version="1.0.0",
        reason="freeze",
        pinned_by="test",
    )
    assert pinned["success"] is True
    pins_data = json.loads(pins_file.read_text(encoding="utf-8"))
    assert "external_shell:lc" in pins_data

    unpinned = await engine.unpin(skill_name="external_shell", source_name="lc")
    assert unpinned["success"] is True
    pins_data_after = json.loads(pins_file.read_text(encoding="utf-8"))
    assert pins_data_after == {}


@pytest.mark.asyncio
async def test_catalog_provenance_and_rollback_fallback(tmp_path):
    cache_file = tmp_path / "cache.json"
    history_file = tmp_path / "history.json"
    pins_file = tmp_path / "pins.json"

    _write_json(
        cache_file,
        {
            "updated_at": "2026-03-08T00:00:00Z",
            "skills": [
                {
                    "skill_name": "external_shell",
                    "source_name": "lc",
                    "version": "2.0.0",
                    "schema_hash": "hash_v2",
                    "payload": {"name": "external_shell", "version": "2.0.0"},
                    "status": "active",
                }
            ],
            "diff": {},
        },
    )
    _write_json(
        history_file,
        [
            {
                "ts": "2026-03-07T10:00:00Z",
                "skills": [
                    {
                        "skill_name": "external_shell",
                        "source_name": "lc",
                        "version": "1.0.0",
                        "schema_hash": "hash_v1",
                        "payload": {"name": "external_shell", "version": "1.0.0"},
                        "status": "active",
                    }
                ],
                "diff": {},
            },
            {
                "ts": "2026-03-08T10:00:00Z",
                "skills": [
                    {
                        "skill_name": "external_shell",
                        "source_name": "lc",
                        "version": "2.0.0",
                        "schema_hash": "hash_v2",
                        "payload": {"name": "external_shell", "version": "2.0.0"},
                        "status": "active",
                    }
                ],
                "diff": {},
            },
        ],
    )

    engine = SkillsCatalogSyncEngine(sources_file=str(tmp_path / "sources.json"))
    engine._get_conn = _raise_db_unavailable
    engine._fallback_cache_path = str(cache_file)
    engine._history_file_path = str(history_file)
    engine._pins_file_path = str(pins_file)

    provenance = await engine.provenance(skill_name="external_shell", source_name="lc", limit=5)
    assert provenance["success"] is True
    assert provenance["current"]["version"] == "2.0.0"
    assert provenance["history"]

    rollback = await engine.rollback(
        skill_name="external_shell",
        source_name="lc",
        target_version="1.0.0",
    )
    assert rollback["success"] is True
    assert rollback["rolled_back_to_version"] == "1.0.0"

    cache_data_after = json.loads(cache_file.read_text(encoding="utf-8"))
    skill = cache_data_after["skills"][0]
    assert skill["version"] == "1.0.0"
