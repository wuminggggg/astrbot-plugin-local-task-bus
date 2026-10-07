#!/usr/bin/env bash
# AstrBot WebUI API 的根地址示例，端口沿用现有 AstrBot 配置。
BASE='http://127.0.0.1:6185/api/plug/local-task-bus'

# 查看已注册的本地回调
curl "$BASE/callbacks"

# 创建每分钟执行一次的任务
curl -X POST "$BASE/jobs" \
  -H 'Content-Type: application/json' \
  -d '{"name":"example heartbeat","cron_expression":"* * * * *","callback":"example_heartbeat","payload":{"source":"demo"}}'

# 查看任务
curl "$BASE/jobs"

# 立即执行，JOB_ID 替换成返回的 id
curl -X POST "$BASE/jobs/JOB_ID"

# 删除任务
curl -X DELETE "$BASE/jobs/JOB_ID"
