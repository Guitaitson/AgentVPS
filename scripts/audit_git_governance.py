"""Local Git/GitHub governance audit for AgentVPS."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AuditReport:
    failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)

    def add(self, level: str, message: str) -> None:
        mapping = {
            "fail": self.failures,
            "warning": self.warnings,
            "info": self.infos,
        }
        mapping[level].append(message)

    @property
    def success(self) -> bool:
        return not self.failures


def run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )


def git_output(*args: str) -> str:
    result = run_command("git", *args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def gh_json(*args: str) -> Any | None:
    if not shutil.which("gh"):
        return None
    result = run_command("gh", *args)
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    if not output:
        return None
    return json.loads(output)


def audit_worktree(report: AuditReport) -> None:
    status = git_output("status", "--short", "--branch")
    lines = [line for line in status.splitlines() if line.strip()]
    if not lines:
        report.add("fail", "Unable to determine git status.")
        return

    branch_line = lines[0]
    report.add("info", branch_line)
    dirty_lines = lines[1:]
    if dirty_lines:
        report.add("fail", f"Worktree is dirty ({len(dirty_lines)} tracked change(s)).")
    else:
        report.add("info", "Worktree is clean.")


def audit_current_branch(report: AuditReport) -> None:
    branch = git_output("branch", "--show-current")
    upstream = run_command("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    upstream_name = upstream.stdout.strip() if upstream.returncode == 0 else ""

    report.add("info", f"Current branch: {branch or '(detached)'}")
    if branch == "main":
        report.add("warning", "You are working directly on main.")

    if upstream_name:
        report.add("info", f"Upstream: {upstream_name}")
    else:
        report.add("warning", "Current branch has no upstream configured.")


def audit_local_branches(report: AuditReport) -> None:
    branch_output = git_output("branch", "-vv")
    gone = 0
    ahead = 0
    for raw_line in branch_output.splitlines():
        line = raw_line.strip()
        if "[gone]" in line:
            gone += 1
        if ": ahead " in line or " ahead " in line:
            ahead += 1

    if gone:
        report.add("warning", f"Found {gone} local branch(es) with gone upstream.")
    if ahead:
        report.add("warning", f"Found {ahead} local branch(es) still ahead of upstream.")
    if not gone and not ahead:
        report.add("info", "No stale local branches detected.")


def audit_main_alignment(report: AuditReport) -> None:
    origin_main = git_output("rev-parse", "--short", "origin/main")
    report.add("info", f"origin/main tip: {origin_main}")


def audit_prs_and_releases(report: AuditReport) -> None:
    open_prs = gh_json(
        "pr",
        "list",
        "--repo",
        "Guitaitson/AgentVPS",
        "--state",
        "open",
        "--json",
        "number,title,headRefName,baseRefName",
    )
    if open_prs is None:
        report.add("warning", "Could not query open PRs via gh.")
    else:
        report.add("info", f"Open PRs: {len(open_prs)}")

    releases = gh_json(
        "release",
        "list",
        "--repo",
        "Guitaitson/AgentVPS",
        "--limit",
        "1",
        "--json",
        "tagName,publishedAt,isLatest",
    )
    if releases is None:
        report.add("warning", "Could not query releases via gh.")
    elif releases:
        latest = releases[0]
        report.add(
            "info",
            f"Latest release: {latest.get('tagName')} published at {latest.get('publishedAt')}",
        )
    else:
        report.add("warning", "No GitHub releases found.")


def audit_release_workflow(report: AuditReport) -> None:
    workflow_path = ".github/workflows/release-deploy.yml"
    if shutil.which("git"):
        tracked = run_command("git", "ls-files", "--error-unmatch", workflow_path)
        if tracked.returncode == 0:
            report.add("info", f"Release workflow present: {workflow_path}")
            return
    report.add("fail", f"Missing required workflow: {workflow_path}")


def main() -> int:
    report = AuditReport()
    try:
        audit_worktree(report)
        audit_current_branch(report)
        audit_local_branches(report)
        audit_main_alignment(report)
        audit_prs_and_releases(report)
        audit_release_workflow(report)
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        report.add("fail", f"Audit crashed: {exc}")

    print("AgentVPS Git/GitHub governance audit")
    for label, items in (
        ("FAIL", report.failures),
        ("WARN", report.warnings),
        ("INFO", report.infos),
    ):
        for item in items:
            print(f"[{label}] {item}")

    if report.success:
        print("Result: PASS")
        return 0

    print("Result: FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
