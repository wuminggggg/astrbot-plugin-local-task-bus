from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from quart import request
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from . import task_bus


@register(
    "astrbot_plugin_local_task_bus",
    "local",
    "本地任务总线：为插件提供进程内定时回调和每条消息触发，不新增端口。",
    "v0.1.0",
)
class LocalTaskBus(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context = context
        context.register_web_api("/local-task-bus/callbacks", self.api_callbacks, ["GET"], "列出已注册回调")
        context.register_web_api("/local-task-bus/jobs", self.api_jobs, ["GET", "POST"], "管理本地回调定时任务")
        context.register_web_api("/local-task-bus/jobs/<job_id>", self.api_job, ["DELETE", "POST"], "删除或立即执行任务")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        await task_bus.invoke_message(event)

    async def api_callbacks(self):
        return {"callbacks": task_bus.callback_names(), "message_callbacks": task_bus.message_callback_names()}

    async def api_jobs(self, **kwargs):
        if request.method == "GET":
            jobs = await self.context.cron_manager.list_jobs("basic")
            return {"jobs": [self._job_dict(j) for j in jobs]}
        body = await request.get_json(silent=True) or {}
        name = str(body.get("name", "")).strip()
        cron = str(body.get("cron_expression", "")).strip()
        callback = str(body.get("callback", "")).strip()
        if not name or not cron or callback not in task_bus.callback_names():
            return {"error": "需要 name、有效 cron_expression 和已注册 callback"}, 400
        payload = body.get("payload") or {}
        if not isinstance(payload, dict):
            return {"error": "payload 必须是对象"}, 400
        async def handler(**data: Any):
            await task_bus.invoke(callback, data)
        job = await self.context.cron_manager.add_basic_job(
            name=name, cron_expression=cron, handler=handler,
            description=str(body.get("description", "")), timezone=body.get("timezone"),
            payload=payload, persistent=False,
        )
        task_bus.bind_job(job.job_id, callback)
        return self._job_dict(job), 201

    async def api_job(self, job_id: str, **kwargs):
        if request.method == "DELETE":
            await self.context.cron_manager.delete_job(job_id)
            task_bus.unbind_job(job_id)
            return {"ok": True}
        await self.context.cron_manager.run_job_now(job_id)
        return {"ok": True}

    @staticmethod
    def _job_dict(job):
        return {"id": job.job_id, "name": job.name, "cron_expression": job.cron_expression,
                "callback": task_bus.get_bound_callback(job.job_id), "enabled": job.enabled,
                "persistent": job.persistent}

    async def terminate(self):
        for job in list((await self.context.cron_manager.list_jobs("basic"))):
            if task_bus.get_bound_callback(job.job_id):
                await self.context.cron_manager.delete_job(job.job_id)
                task_bus.unbind_job(job.job_id)
