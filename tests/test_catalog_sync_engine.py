import json

import pytest

from core.catalog import SkillsCatalogSyncEngine


def _raise_db_unavailable():
    raise RuntimeError("db unavailable in test")


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")


@pytest.mark.asyncio
async def test_catalog_sync_check_detects_added_skills(tmp_path):
    source_payload = {
        "skills": [
            {
                "name": "external_shell",
                "description": "External shell helper",
                "version": "1.0.0",
                "security_level": "moderate",
            }
        ]
    }
    local_source = tmp_path / "source.json"
    sources_file = tmp_path / "sources.json"
    cache_file = tmp_path / "cache.json"
    _write_json(local_source, source_payload)
    _write_json(
        sources_file,
        {
            "sources": [
                {
                    "name": "local_test",
                    "type": "local_json",
                    "location": str(local_source),
                    "enabled": True,
                }
            ]
        },
    )

    engine = SkillsCatalogSyncEngine(sources_file=str(sources_file))
    engine._fallback_cache_path = str(cache_file)
    engine._get_conn = _raise_db_unavailable

    result = await engine.sync(mode="check")

    assert result["success"] is True
    assert result["added"] == 1
    assert result["changes_detected"] == 1


@pytest.mark.asyncio
async def test_catalog_sync_apply_persists_and_detects_updates(tmp_path):
    local_source = tmp_path / "source.json"
    sources_file = tmp_path / "sources.json"
    cache_file = tmp_path / "cache.json"
    _write_json(
        sources_file,
        {
            "sources": [
                {
                    "name": "local_test",
                    "type": "local_json",
                    "location": str(local_source),
                    "enabled": True,
                }
            ]
        },
    )

    _write_json(
        local_source,
        {
            "skills": [
                {
                    "name": "external_shell",
                    "description": "External shell helper",
                    "version": "1.0.0",
                    "security_level": "moderate",
                }
            ]
        },
    )
    engine = SkillsCatalogSyncEngine(sources_file=str(sources_file))
    engine._fallback_cache_path = str(cache_file)
    engine._get_conn = _raise_db_unavailable

    first = await engine.sync(mode="apply")
    assert first["success"] is True
    assert cache_file.exists()

    _write_json(
        local_source,
        {
            "skills": [
                {
                    "name": "external_shell",
                    "description": "External shell helper changed",
                    "version": "1.1.0",
                    "security_level": "moderate",
                }
            ]
        },
    )
    second = await engine.sync(mode="check")

    assert second["success"] is True
    assert second["updated"] == 1
    assert second["changes_detected"] == 1


@pytest.mark.asyncio
async def test_catalog_sync_parses_langchain_skills_source(tmp_path):
    local_source = tmp_path / "langchain_source.json"
    sources_file = tmp_path / "sources.json"
    cache_file = tmp_path / "cache.json"

    _write_json(
        local_source,
        {
            "packages": [
                {
                    "name": "pack-a",
                    "skills": [
                        {
                            "id": "lc_lookup",
                            "summary": "Lookup docs",
                            "semver": "0.3.1",
                            "risk_level": "medium",
                            "keywords": ["lookup", "docs"],
                            "input_schema": {
                                "type": "object",
                                "properties": {"q": {"type": "string"}},
                            },
                        }
                    ],
                }
            ]
        },
    )
    _write_json(
        sources_file,
        {
            "sources": [
                {
                    "name": "lc_test",
                    "type": "langchain_skills_local_json",
                    "location": str(local_source),
                    "enabled": True,
                }
            ]
        },
    )

    engine = SkillsCatalogSyncEngine(sources_file=str(sources_file))
    engine._fallback_cache_path = str(cache_file)
    engine._get_conn = _raise_db_unavailable

    result = await engine.sync(mode="check")

    assert result["success"] is True
    assert result["skills_discovered"] == 1
    assert result["added"] == 1
