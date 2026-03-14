# Project Status - Operational Snapshot

Last updated: 2026-03-13

## Canonical Read Order

1. `origin/main` (GitHub)
2. `docs/GIT_GOVERNANCE.md`
3. This file (`docs/PROJECT_STATUS.md`)
4. Local worktree WIP (not committed yet)
5. `archive/` (historical context only, non-normative)

## Branch and Sync Policy

- Canonical branch on GitHub: `origin/main`
- This file must not track ephemeral local branch names or transient commit hashes.
- Use `git rev-parse origin/main` and `python scripts/audit_git_governance.py` for live branch and release state.
- Production deploy authority comes from published GitHub Release, not from branch pushes.

## Master Plan Status (Strict 100% Gate)

### Implemented and validated locally

- Layered memory primitives (episodic, semantic, procedural, profile, goals)
- Memory policy (TTL, retention, redaction, scope)
- Memory audit trail
- Versioned soul identity with proposal/approval flow and challenge mode
- Runtime adapter layer (local + MCP + A2A + ACP + DeepAgents + OpenClaw)
- Runtime adapter control plane (`/runtimes list|enable|disable`) with persisted overrides
- Optional `codex_operator` runtime adapter for FleetIntel/BrazilCNPJ specialist delegation
- Skills catalog sync engine + updater agent + autonomous trigger integration
- Catalog operations: pin, unpin, rollback, provenance (DB + fallback file)
- Real semantic memory integration with Qdrant in runtime path (save + recall)
- Regression coverage for delegated runtime and semantic memory paths
- External specialist routing for `fleetintel_analyst`, `brazilcnpj` and `fleetintel_orchestrator`
- Reusable remote MCP client for authenticated FleetIntel/BrazilCNPJ servers
- Skills catalog source now supports direct GitHub repo discovery for LangChain-style `SKILL.md` packs
- Default catalog source now points to live FleetIntel GitHub discovery
- External catalog updater now supports auto-apply with smoke and auto rollback for FleetIntel/BrazilCNPJ metadata updates
- External FleetIntel contracts now persist `instructions_markdown`, and `react_node` can route `fleetintel-orchestrator` / `fleetintel-analyst` through `codex_operator` when the synced contract says the specialist owns the final response

Validation baseline at review time:
- targeted: `python -m pytest -q tests/test_runtime_adapters.py tests/test_runtime_control.py tests/test_external_specialist_skills.py tests/test_react_codex_operator.py` -> 24 passed
- full suite: `python -m pytest -q` -> 266 passed, 2 skipped

## Decision Gate for Next Features

Strict gate remains complete. FleetIntel/BrazilCNPJ integration cycle is now in implementation/validation.

## Notes About Conflicting Historical Files

- `.kilocode/rules/memory-bank/brief.md` is now aligned with this file.
- `.kilocode/rules/memory-bank/deployment-tracker.md` remains detailed tracker context.
- `archive/plans/deployment-tracker.md` is historical and must not be used as current status.

## Voice Context Capture Status

Implemented locally:
- `core/voice_context/` with ingestion, deduplication, extraction, review flow and memory commit.
- New skill `voice_context_sync`.
- Telegram commands `/contextsync` and `/contextstatus`.
- Autonomous trigger `voice_context_batch` + transcript cleanup integration.
- New schema and migration: `configs/migration-voice-context.sql`.
- Windows companion under `desktop_companion/windows/` for removable-device import and `scp` upload.

Validation in this cycle:
- `python -m pytest -q tests/test_voice_context.py tests/test_voice_context_skill.py tests/test_execute_scheduled_skill.py` -> passed
- Full-suite validation pending after final lint/docs sweep.
