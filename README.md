# astrbot_plugin_local_task_bus

中文 | English

## 中文介绍

本地任务总线插件，为 AstrBot 其他插件提供进程内回调和定时任务 API。

它直接复用 AstrBot 已有的 WebUI API 路由，不新增端口，也不执行任意代码。定时任务由 AstrBot 原生 Cron 管理，任务只允许调用已经由插件注册的 Python 回调。

### 功能

- 其他插件注册定时回调
- 注册每条消息触发的本地回调
- 通过现有 AstrBot API 增删查任务
- 手动立即执行任务
- 任务回调白名单校验
- 卸载插件时清理本插件创建的任务

### 安装

把插件目录放入 `AstrBot/data/plugins/astrbot_plugin_local_task_bus`，然后在 AstrBot 插件管理中重载。

### API

接口前缀：`/api/plug/local-task-bus`

- `GET /callbacks` 查看回调
- `GET /jobs` 查看任务
- `POST /jobs` 创建任务
- `POST /jobs/<job_id>` 立即执行
- `DELETE /jobs/<job_id>` 删除任务

创建任务示例：

```json
{
  "name": "example heartbeat",
  "cron_expression": "* * * * *",
  "callback": "example_heartbeat",
  "payload": {"source": "demo"}
}
```

API 仍受 AstrBot 现有 WebUI/API 鉴权和网络配置控制。不要把管理接口暴露到不可信网络。

### 其他插件调用

```python
from astrbot_plugin_local_task_bus import register_callback

async def cleanup(**payload):
    print(payload)

register_callback("my_cleanup", cleanup)
```

每条消息回调：

```python
from astrbot_plugin_local_task_bus import register_message_callback

def on_message(event):
    if event.message_str.startswith("/watch"):
        print(event.message_str)

register_message_callback("my_message_listener", on_message)
```

完整示例见 `example/consumer_plugin.py` 和 `example/api_usage.sh`。每条消息回调务必自行过滤、限流，避免拖慢消息处理。

## English

An in-process task bus for AstrBot plugins. It provides local Python callbacks, message callbacks, and scheduled-job management through AstrBot's existing WebUI API. It does not open another port and never evaluates arbitrary code.

### Features

- Register callbacks from other plugins
- Run callbacks on every message
- Create, list, run, and delete jobs through the existing AstrBot API
- Allow only registered callback names
- Clean up jobs created by this plugin on unload

See `example/consumer_plugin.py` and `example/api_usage.sh` for complete examples.

## License

MIT License.

## 未来任务页面

插件详情页中打开“未来任务”Page，即可新建任务：

- 指定时间：选择带时区的执行时间，到点调用已注册回调
- 行为触发：消息包含关键词或匹配正则时调用回调
- 支持冷却时间和最多触发次数
- 回调只允许选择已注册名称，不执行任意代码

页面路由由 AstrBot 自动提供，不会额外监听端口。
