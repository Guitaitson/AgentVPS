"""Shared progress callbacks for long-running agent requests."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from typing import Any

ProgressCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]

_current_progress_callback: contextvars.ContextVar[ProgressCallback | None] = (
    contextvars.ContextVar(
        "agentvps_progress_callback",
        default=None,
    )
)


@contextmanager
def bind_progress_callback(callback: ProgressCallback | None):
    token = _current_progress_callback.set(callback)
    try:
        yield
    finally:
        _current_progress_callback.reset(token)


async def emit_progress(event: str, **payload: Any) -> None:
    callback = _current_progress_callback.get()
    if callback is None:
        return

    result = callback(event, payload)
    if inspect.isawaitable(result):
        await result


def emit_progress_nowait(event: str, **payload: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(emit_progress(event, **payload))
