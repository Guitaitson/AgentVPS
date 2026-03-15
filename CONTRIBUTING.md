# Contributing

Use [AGENTS.md](AGENTS.md) as the day-to-day contributor guide. This file keeps only the project-specific governance and required reading that should not drift across PRs.

## Required Reading
Before changing code, review:

- [README.md](README.md): project overview and runtime layout
- [AGENTS.md](AGENTS.md): structure, commands, coding style, tests, and PR expectations
- [docs/GIT_GOVERNANCE.md](docs/GIT_GOVERNANCE.md): branch, release, and deploy flow
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): graph, integrations, and boundaries
- [docs/adr/README.md](docs/adr/README.md): architectural decision records

If the change affects current operational state, also review:

- [`.kilocode/rules/memory-bank/brief.md`](.kilocode/rules/memory-bank/brief.md)
- [`.kilocode/rules/vps-agent-rules.md`](.kilocode/rules/vps-agent-rules.md)

## Delivery Workflow
The canonical flow is:

1. sync with `origin/main`
2. create a short-lived branch from `main`
3. implement and validate locally
4. open a PR to `main`
5. merge only after green CI
6. publish a GitHub Release
7. let the release workflow deploy to the VPS

Rules:

- `main` is the only production branch
- do not leave the VPS pinned to a temporary branch
- do not release commits that are not already in `main`
- clean up stale local branches and worktrees after merge

## Change Checklist
- update tests for behavioral changes
- run `python -m pytest -q`
- run `python -m ruff check .`
- run `python -m ruff format --check .`
- run `python scripts/audit_git_governance.py` before release-sensitive work
- add or update ADRs when the architecture changes

## Security and Scope Boundaries
- Never commit real credentials; use `configs/.env.example` as the template.
- Avoid destructive commands unless explicitly approved.
- Preserve system boundaries: AgentVPS owns orchestration, auth, UX, memory, and fallback; external specialists such as FleetIntel or BrazilCNPJ own domain logic and specialist output.
