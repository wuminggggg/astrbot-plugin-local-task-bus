"""进程内任务总线。其他插件可直接导入 register_callback。"""
from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

_callbacks: dict[str, Callable[..., Any]] = {}
_message_callbacks: dict[str, Callable[..., Any]] = {}
_jobs: dict[str, str] = {}


def register_callback(name: str, callback: Callable[..., Any]) -> None:
    """注册定时任务回调，name 需全局唯一。"""
    if not name or not callable(callback):
        raise ValueError("name 和 callback 必须有效")
    _callbacks[name] = callback


def unregister_callback(name: str) -> None:
    _callbacks.pop(name, None)


def register_message_callback(name: str, callback: Callable[..., Any]) -> None:
    """注册每条消息回调。回调接收 event 参数。"""
    if not name or not callable(callback):
        raise ValueError("name 和 callback 必须有效")
    _message_callbacks[name] = callback


def unregister_message_callback(name: str) -> None:
    _message_callbacks.pop(name, None)


def callback_names() -> list[str]:
    return sorted(_callbacks)


def message_callback_names() -> list[str]:
    return sorted(_message_callbacks)


def bind_job(job_id: str, callback_name: str) -> None:
    _jobs[job_id] = callback_name


def unbind_job(job_id: str) -> None:
    _jobs.pop(job_id, None)

async def invoke(name: str, payload: dict[str, Any] | None = None) -> Any:
    callback = _callbacks.get(name)
    if callback is None:
        raise KeyError(f"callback not registered: {name}")
    result = callback(**(payload or {}))
    return await result if inspect.isawaitable(result) else result

async def invoke_message(event: Any) -> None:
    for name, callback in list(_message_callbacks.items()):
        try:
            result = callback(event)
            if inspect.isawaitable(result):
                await result
        except Exception:
            import logging
            logging.getLogger("astrbot").exception("local task message callback failed: %s", name)


def get_bound_callback(job_id: str) -> str | None:
    return _jobs.get(job_id)
