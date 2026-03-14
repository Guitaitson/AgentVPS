#!/usr/bin/env python3
"""Run voice-context inspect/sync flows against an explicit batch manifest."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from core.env import load_project_env
from core.voice_context import VoiceContextService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Voice context batch runner")
    parser.add_argument(
        "--mode",
        choices=("inspect", "sync", "sync-if-green"),
        default="inspect",
        help="Batch action to run on the VPS inbox.",
    )
    parser.add_argument(
        "--manifest-path",
        help="Remote batch_manifest.json path. Approved files from this manifest are targeted.",
    )
    parser.add_argument(
        "--file-names-json",
        help="Optional explicit JSON array of filenames already present in the inbox.",
    )
    parser.add_argument(
        "--source",
        default="voice_batch_runner",
        help="Source label stored in voice ingestion stats.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional max number of files to process from the selected batch.",
    )
    return parser


def _load_manifest_file_names(manifest_path: str | None) -> list[str]:
    if not manifest_path:
        return []
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    files = payload.get("files") or []
    selected: list[str] = []
    for item in files:
        if str(item.get("decision") or "").strip().lower() != "approved":
            continue
        staged_name = str(item.get("stagedName") or "").strip()
        if staged_name and staged_name not in selected:
            selected.append(staged_name)
    return selected


def _load_explicit_file_names(raw_json: str | None) -> list[str]:
    if not raw_json:
        return []
    payload = json.loads(raw_json)
    if not isinstance(payload, list):
        raise ValueError("file_names_json must be a JSON array")
    selected: list[str] = []
    for item in payload:
        name = str(item or "").strip()
        if name and name not in selected:
            selected.append(name)
    return selected


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    load_project_env()
    service = VoiceContextService()

    file_names = _load_manifest_file_names(args.manifest_path)
    explicit_names = _load_explicit_file_names(args.file_names_json)
    for name in explicit_names:
        if name not in file_names:
            file_names.append(name)

    inspect_result = await service.inspect_inbox(
        source=f"{args.source}:inspect",
        max_files=args.max_files,
        file_names=file_names or None,
    )
    result: dict[str, Any] = {
        "success": bool(inspect_result.get("success")),
        "mode": args.mode,
        "selected_files": file_names,
        "inspect": inspect_result,
    }
    gate = inspect_result.get("green_gate") or service.evaluate_green_gate(inspect_result)
    result["green_gate"] = gate

    if args.mode == "inspect":
        return result

    if args.mode == "sync-if-green" and not gate.get("passed"):
        result["success"] = False
        result["status"] = "blocked_by_green_gate"
        return result

    sync_result = await service.sync_inbox(
        source=f"{args.source}:sync",
        max_files=args.max_files,
        file_names=file_names or None,
    )
    result["sync"] = sync_result
    result["success"] = bool(sync_result.get("success"))
    result["status"] = sync_result.get("status", "completed")
    return result


def main() -> int:
    args = _build_parser().parse_args()
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # pragma: no cover - top-level CLI guard
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.mode == "sync-if-green" and not result.get("green_gate", {}).get("passed"):
        return 3
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
