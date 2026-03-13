# Git and GitHub Governance

Last updated: 2026-03-13

This document defines the operational source of truth for branch management, pull requests, releases, and deploys.

## Canonical Rules

1. `origin/main` is the only production branch.
2. Every code change starts from the latest `origin/main`.
3. Every non-trivial change goes through a pull request to `main`.
4. Merge happens only after CI is green.
5. Autonomous VPS deploy happens only from a published GitHub Release.
6. Any exceptional manual deploy must still leave the VPS aligned to `origin/main`.

## Branch Policy

- Allowed long-lived branch:
  - `main`
- Allowed short-lived branches:
  - `feat/...`
  - `fix/...`
  - `docs/...`
  - `chore/...`
  - temporary automation branches such as `claude/prNN-...` while they are tied to an active PR
- Disallowed as steady state:
  - local branches with `gone` upstream
  - local branches left `ahead` after merge
  - production deployments from feature branches

## Pull Request Policy

Before opening a PR:

- sync branch with latest `origin/main`
- keep worktree clean except for the intended change
- run targeted tests and `ruff check`
- update docs when user-visible or operational behavior changes

Before merging a PR:

- CI on GitHub must be green
- PR description must state behavior change and operational risk
- release notes impact must be clear: either `requires release note` or `no release note`

Preferred merge strategy:

- squash merge by default
- rebase merge only when preserving the commit sequence is important

## Release and Deploy Policy

The release flow is:

1. branch from `main`
2. open PR to `main`
3. merge to `main` with green CI
4. publish GitHub Release with semantic version tag `vX.Y.Z`
5. let `.github/workflows/release-deploy.yml` deploy the release to the VPS

Rules:

- never publish a release for a commit that is not already in `main`
- never treat branch push as production deploy authorization
- never leave the VPS on a temporary branch after manual intervention

## Hygiene and Audit

Run the local audit before push, before merge coordination, and before release:

```bash
python scripts/audit_git_governance.py
```

The audit checks:

- dirty worktree
- current branch and upstream
- stale local branches (`gone`)
- local branches still `ahead`
- open PRs
- latest release visibility
- release deploy workflow presence

## Documentation Hierarchy

When Git or GitHub process docs conflict, use this order:

1. `origin/main`
2. this file
3. `README.md`
4. `CONTRIBUTING.md`
5. historical context under `archive/` and `Sprint*`
