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


class _MockResponse:
    def __init__(self, *, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        if self._json_data is None:
            raise RuntimeError("json not available")
        return self._json_data


@pytest.mark.asyncio
async def test_catalog_sync_parses_langchain_skills_github_repo_source(tmp_path, monkeypatch):
    sources_file = tmp_path / "sources.json"
    cache_file = tmp_path / "cache.json"
    _write_json(
        sources_file,
        {
            "sources": [
                {
                    "name": "fleetintel_repo",
                    "type": "langchain_skills_github_repo",
                    "location": "https://github.com/Guitaitson/fleetintel-mcp",
                    "enabled": True,
                }
            ]
        },
    )

    async def fake_get(self, url, headers=None):
        if "commits/main" in url:
            return _MockResponse(json_data={"sha": "abcdef1234567890"})
        if "/git/trees/" in url:
            return _MockResponse(
                json_data={
                    "tree": [
                        {"path": "skills/fleetintel-orchestrator/SKILL.md"},
                        {"path": "skills/brazilcnpj-enricher/SKILL.md"},
                    ]
                }
            )
        if "fleetintel-orchestrator/SKILL.md" in url:
            return _MockResponse(
                text=(
                    "---\n"
                    "name: fleetintel-orchestrator\n"
                    "description: Coordinate FleetIntel and BrazilCNPJ\n"
                    "metadata:\n"
                    "  mcp_servers: fleetintel-mcp,brazilcnpj-mcp\n"
                    "---\n"
                    "# FleetIntel Orchestrator\n"
                )
            )
        if "brazilcnpj-enricher/SKILL.md" in url:
            return _MockResponse(
                text=(
                    "---\n"
                    "name: brazilcnpj-enricher\n"
                    "description: Enrich companies with CNPJ data\n"
                    "---\n"
                    "# BrazilCNPJ Enricher\n"
                )
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr("httpx.AsyncClient.get", fake_get)

    engine = SkillsCatalogSyncEngine(sources_file=str(sources_file))
    engine._fallback_cache_path = str(cache_file)
    engine._get_conn = _raise_db_unavailable

    result = await engine.sync(mode="check")

    assert result["success"] is True
    assert result["skills_discovered"] == 2
    assert result["added"] == 2
