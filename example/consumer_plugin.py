"""其他插件调用本地任务总线的最小示例。

把这段逻辑放到自己的 AstrBot 插件里即可。无需 HTTP、无需新增端口。
"""
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from astrbot_plugin_local_task_bus import register_callback, register_message_callback


@register("example_consumer", "example", "本地任务总线调用示例", "v0.1.0")
class ExampleConsumer(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        register_callback("example_heartbeat", self.heartbeat)
        register_message_callback("example_message", self.on_any_message)

    async def heartbeat(self, **payload):
        # 这里写定时执行的业务，payload 来自创建任务时的 payload。
        print("heartbeat payload:", payload)

    async def on_any_message(self, event: AstrMessageEvent):
        # 每条消息都会进入这里，请自行做过滤和限流。
        if event.message_str.strip() == "/local-bus-test":
            yield event.plain_result("local callback works")

    async def terminate(self):
        # 生产插件应在卸载时注销自己的回调，避免重复注册。
        from astrbot_plugin_local_task_bus import unregister_callback, unregister_message_callback
        unregister_callback("example_heartbeat")
        unregister_message_callback("example_message")
