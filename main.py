from __future__ import annotations
import re, time, uuid
from datetime import datetime
from pathlib import Path
from quart import request
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, StarTools, register
from . import task_bus
from .future_store import FutureStore

PLUGIN='astrbot_plugin_local_task_bus'
@register(PLUGIN,'local','本地任务总线：定时执行或行为触发的本地回调任务。','v0.2.0')
class LocalTaskBus(Star):
    def __init__(self, context: Context):
        super().__init__(context); self.context=context
        self.store=FutureStore(Path(StarTools.get_data_dir(PLUGIN))/'future_tasks.json')
        self._runtime_jobs=set(); self._last_fire={}; self._counts={}
        context.register_web_api(f'/{PLUGIN}/callbacks',self.api_callbacks,['GET'],'列出本地回调')
        context.register_web_api(f'/{PLUGIN}/future-tasks',self.api_tasks,['GET','POST'],'管理未来任务')
        context.register_web_api(f'/{PLUGIN}/future-tasks/<task_id>',self.api_task,['POST'],'删除任务')
        # 保留兼容旧 API
        context.register_web_api('/local-task-bus/callbacks',self.api_callbacks,['GET'],'列出本地回调')
        context.register_web_api('/local-task-bus/jobs',self.api_legacy_jobs,['GET','POST'],'旧版定时任务 API')
        context.register_web_api('/local-task-bus/jobs/<job_id>',self.api_legacy_job,['DELETE','POST'],'旧版任务操作')
        self._restore_time_tasks()

    def _restore_time_tasks(self):
        for tid,t in self.store.data.items():
            if t.get('mode')=='time' and t.get('enabled',True) and t.get('status')=='scheduled':
                try: self._schedule_time(tid,t)
                except Exception: logger.exception('恢复未来任务失败: %s',tid)

    def _schedule_time(self,tid,t):
        async def run(**payload):
            try: await task_bus.invoke(t['callback'],payload)
            finally:
                self.store.data.pop(tid,None); self.store.save(); self._runtime_jobs.discard(tid)
        run_at=datetime.fromisoformat(t['run_at'])
        job=self.context.cron_manager.scheduler.add_job(run,'date',run_date=run_at,id='localbus_'+tid,replace_existing=True,kwargs=t.get('payload') or {})
        self._runtime_jobs.add(tid)

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self,event:AstrMessageEvent):
        await task_bus.invoke_message(event)
        text=event.message_str or ''; now=time.monotonic()
        for tid,t in list(self.store.data.items()):
            if t.get('mode')!='behavior' or not t.get('enabled',True): continue
            cb=t.get('callback')
            if cb not in task_bus.callback_names(): continue
            if t.get('match_type')=='regex':
                try: matched=bool(re.search(t['pattern'],text))
                except re.error: matched=False
            else: matched=t.get('pattern','') in text
            if not matched: continue
            cooldown=max(0,int(t.get('cooldown',0))); last=self._last_fire.get(tid,0)
            if now-last<cooldown: continue
            maximum=max(0,int(t.get('max_runs',0))); count=self._counts.get(tid,0)
            if maximum and count>=maximum: continue
            self._last_fire[tid]=now; self._counts[tid]=count+1
            try: await task_bus.invoke(cb,{**(t.get('payload') or {}),'event':event,'matched_text':text})
            except Exception: logger.exception('行为任务执行失败: %s',tid)
            if maximum and self._counts[tid]>=maximum:
                t['enabled']=False; t['status']='completed'; self.store.save()

    async def api_callbacks(self):
        return {'callbacks':task_bus.callback_names(),'message_callbacks':task_bus.message_callback_names()}

    async def api_tasks(self):
        return {'tasks':[self._public(tid,t) for tid,t in self.store.data.items()]}

    async def api_tasks_post(self,body):
        name=str(body.get('name','')).strip(); mode=body.get('mode'); cb=str(body.get('callback','')).strip()
        if not name or mode not in ('time','behavior') or cb not in task_bus.callback_names():
            return {'error':'需要任务名称、有效 mode 和已注册 callback'},400
        tid=uuid.uuid4().hex[:12]
        t={'id':tid,'name':name,'mode':mode,'callback':cb,'payload':body.get('payload') or {},'enabled':True,'status':'scheduled','created_at':datetime.now().astimezone().isoformat()}
        if not isinstance(t['payload'],dict): return {'error':'payload 必须是对象'},400
        if mode=='time':
            raw=str(body.get('run_at',''))
            try: dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
            except ValueError: return {'error':'run_at 必须是 ISO 日期时间'},400
            if dt.tzinfo is None: return {'error':'run_at 必须包含时区'},400
            if dt.timestamp()<=time.time(): return {'error':'执行时间必须在未来'},400
            t['run_at']=dt.isoformat()
        else:
            pat=str(body.get('pattern','')).strip(); mt=body.get('match_type','contains')
            if not pat or mt not in ('contains','regex'): return {'error':'需要关键词/正则及合法匹配方式'},400
            if mt=='regex':
                try: re.compile(pat)
                except re.error as e: return {'error':f'正则无效: {e}'},400
            if len(pat)>500: return {'error':'匹配规则最多 500 字符'},400
            t.update(pattern=pat,match_type=mt,cooldown=max(0,min(86400,int(body.get('cooldown',30)))),max_runs=max(0,int(body.get('max_runs',1))))
        self.store.data[tid]=t; self.store.save()
        if mode=='time': self._schedule_time(tid,t)
        return self._public(tid,t),201

    async def api_tasks(self):
        if request.method=='GET': return {'tasks':[self._public(tid,t) for tid,t in self.store.data.items()]}
        body=await request.get_json(silent=True) or {}
        return await self.api_tasks_post(body)

    async def api_task(self,task_id,**kwargs):
        body=await request.get_json(silent=True) or {}
        if body.get('action')!='delete': return {'error':'仅支持 action=delete'},400
        t=self.store.data.pop(task_id,None)
        if not t: return {'error':'任务不存在'},404
        job='localbus_'+task_id
        if self.context.cron_manager.scheduler.get_job(job): self.context.cron_manager.scheduler.remove_job(job)
        self.store.save(); return {'ok':True}

    @staticmethod
    def _public(tid,t):
        return {'id':tid,'name':t['name'],'mode':t['mode'],'callback':t['callback'],'enabled':t.get('enabled',True),'summary':t.get('run_at') or f"{t.get('match_type')}:{t.get('pattern')}",'status':t.get('status')}

    async def api_legacy_jobs(self):
        if request.method=='GET': return await self.api_tasks()
        body=await request.get_json(silent=True) or {}
        return await self.api_tasks_post({'name':body.get('name'),'mode':'time','callback':body.get('callback'),'run_at':body.get('run_at'),'payload':body.get('payload')})
    async def api_legacy_job(self,job_id,**kwargs):
        if request.method=='DELETE':
            self.store.data.pop(job_id,None); self.store.save(); return {'ok':True}
        return {'error':'旧 API 即时执行不支持'},400

    async def terminate(self):
        for tid in list(self._runtime_jobs):
            job=self.context.cron_manager.scheduler.get_job('localbus_'+tid)
            if job: self.context.cron_manager.scheduler.remove_job('localbus_'+tid)
