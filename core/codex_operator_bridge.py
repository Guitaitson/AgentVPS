"""Controlled bridge for Codex CLI to invoke allowlisted AgentVPS specialists."""

from __future__ import annotations

import argparse
import asyncio
import json

from core.env import load_project_env
from core.skills.registry import get_skill_registry

ALLOWED_SPECIALISTS = {
    "fleetintel_analyst",
    "fleetintel_orchestrator",
    "brazilcnpj",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AgentVPS Codex bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list-skills", help="List allowlisted specialists")
    list_parser.set_defaults(handler=_handle_list_skills)

    run_parser = subparsers.add_parser("run-skill", help="Run one allowlisted specialist")
    run_parser.add_argument("--skill", required=True, help="Skill name")
    run_parser.add_argument("--args-json", required=True, help="JSON args passed to the skill")
    run_parser.set_defaults(handler=_handle_run_skill)
    return parser


def _handle_list_skills(_args: argparse.Namespace) -> int:
    print(json.dumps({"skills": sorted(ALLOWED_SPECIALISTS)}, ensure_ascii=False))
    return 0


async def _run_skill(skill_name: str, args_json: str) -> int:
    if skill_name not in ALLOWED_SPECIALISTS:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": "skill_not_allowed",
                    "skill": skill_name,
                },
                ensure_ascii=False,
            )
        )
        return 2

    try:
        skill_args = json.loads(args_json)
    except json.JSONDecodeError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": f"invalid_args_json: {exc}",
                    "skill": skill_name,
                },
                ensure_ascii=False,
            )
        )
        return 2

    load_project_env()
    registry = get_skill_registry()
    result = await registry.execute_skill(skill_name, skill_args)
    print(
        json.dumps(
            {
                "success": True,
                "skill": skill_name,
                "result": result,
            },
            ensure_ascii=False,
        )
    )
    return 0


def _handle_run_skill(args: argparse.Namespace) -> int:
    return asyncio.run(_run_skill(args.skill, args.args_json))


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
