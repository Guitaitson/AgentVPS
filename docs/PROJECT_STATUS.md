# Project Status - Source of Truth

Last updated: 2026-03-08

## Canonical Read Order

1. `origin/main` (GitHub)
2. This file (`docs/PROJECT_STATUS.md`)
3. Local worktree WIP (not committed yet)
4. `archive/` (historical context only, non-normative)

## Branch and Sync Snapshot

- Canonical branch on GitHub: `origin/main`
- Current `origin/main` tip at review time: `27c1d69` (2026-03-08 sync)
- Current worktree branch: `claude/pr2-runtime-gate`
- Local worktree contains additional uncommitted changes (tracked + untracked)

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

Validation at review time:
- `python -m ruff check .` -> OK
- `python -m pytest -q` -> 218 passed, 2 skipped

## Decision Gate for Next Features

Strict gate is complete. Next feature cycle is unblocked.

## Notes About Conflicting Historical Files

- `.kilocode/rules/memory-bank/brief.md` is now aligned with this file.
- `.kilocode/rules/memory-bank/deployment-tracker.md` remains detailed tracker context.
- `archive/plans/deployment-tracker.md` is historical and must not be used as current status.
