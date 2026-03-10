# Project Status - Source of Truth

Last updated: 2026-03-09

## Canonical Read Order

1. `origin/main` (GitHub)
2. This file (`docs/PROJECT_STATUS.md`)
3. Local worktree WIP (not committed yet)
4. `archive/` (historical context only, non-normative)

## Branch and Sync Snapshot

- Canonical branch on GitHub: `origin/main`
- Current `origin/main` tip at review time: `4427a60` (post-merge PR #13)
- Current worktree branch: `claude/pr3-fleetintel-integration`
- Local worktree contains FleetIntel/BrazilCNPJ integration work in progress

## Master Plan Status (Strict 100% Gate)

### Implemented and validated locally

- Layered memory primitives (episodic, semantic, procedural, profile, goals)
- Memory policy (TTL, retention, redaction, scope)
- Memory audit trail
- Versioned soul identity with proposal/approval flow and challenge mode
- Runtime adapter layer (local + MCP + A2A + ACP + DeepAgents + OpenClaw)
- Runtime adapter control plane (`/runtimes list|enable|disable`) with persisted overrides
- Skills catalog sync engine + updater agent + autonomous trigger integration
- Catalog operations: pin, unpin, rollback, provenance (DB + fallback file)
- Real semantic memory integration with Qdrant in runtime path (save + recall)
- Regression coverage for delegated runtime and semantic memory paths
- External specialist routing for `fleetintel_analyst`, `brazilcnpj` and `fleetintel_orchestrator`
- Reusable remote MCP client for authenticated FleetIntel/BrazilCNPJ servers
- Skills catalog source now supports direct GitHub repo discovery for LangChain-style `SKILL.md` packs
- Default catalog source now ships with a real FleetIntel snapshot and optional live GitHub sync

Validation at review time:
- targeted: `python -m pytest -q tests/test_catalog_sync_engine.py tests/test_external_specialist_skills.py tests/test_skill_registry.py` -> 25 passed
- pending final full-suite run after docs finish

## Decision Gate for Next Features

Strict gate remains complete. FleetIntel/BrazilCNPJ integration cycle is now in implementation/validation.

## Notes About Conflicting Historical Files

- `.kilocode/rules/memory-bank/brief.md` is now aligned with this file.
- `.kilocode/rules/memory-bank/deployment-tracker.md` remains detailed tracker context.
- `archive/plans/deployment-tracker.md` is historical and must not be used as current status.
