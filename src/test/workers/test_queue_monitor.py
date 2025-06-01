# 文件路径：tests/workers/test_queue_monitor.py
# -*- coding: utf-8 -*-
"""
Queue Monitor 单元测试：使用 fakeredis 模拟 Redis 客户端，替换告警函数为无操作（避免发送真实邮件或钉钉）。
测试点包括 get_queue_length、alert_if_queue_over_threshold、monitor_queue_length_loop 等逻辑。
"""

import pytest
import fakeredis
import asyncio
from unittest.mock import MagicMock

import src.workers.queue_monitor as monitor_mod

# -------------------------
# 固件：替换 _redis 为 FakeRedis
# -------------------------
@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fake = fakeredis.FakeRedis(decode_responses=True)
    # 将模块中的 Redis 实例替换为 FakeRedis
    monkeypatch.setattr(monitor_mod, "_redis", fake)
    return fake

# -------------------------
# 固件：替换告警函数，避免真实发送
# -------------------------
@pytest.fixture
def mock_alerts(monkeypatch):
    mock_alert_func = MagicMock()
    # 不实际发送邮件或钉钉
    monkeypatch.setattr(monitor_mod, "alert_if_queue_over_threshold", mock_alert_func)
    return mock_alert_func

# -------------------------
# 测试 get_queue_length 正常返回
# -------------------------
def test_get_queue_length_initial(fake_redis):
    # 初始队列为空
    length = monitor_mod.get_queue_length("queue:session_tasks")
    assert length == 0

    # 模拟入队
    fake_redis.lpush("queue:session_tasks", "item_1")
    length = monitor_mod.get_queue_length("queue:session_tasks")
    assert length == 1

# -------------------------
# 测试 get_queue_length 失败返回 -1
# -------------------------
def test_get_queue_length_failure(monkeypatch):
    # 模拟 LLEN 抛出异常
    class FakeExc:
        def llen(self, key):
            raise Exception("Redis 连接失败")
    monkeypatch.setattr(monitor_mod, "_redis", FakeExc())
    length = monitor_mod.get_queue_length("queue:session_tasks")
    assert length == -1

# -------------------------
# 测试 monitor_queue_length_loop 告警逻辑
# -------------------------
@pytest.mark.asyncio
async def test_monitor_loop_triggers_alert(fake_redis, mock_alerts, monkeypatch):
    # 设置一个较低的阈值用于测试
    test_threshold = 5
    monkeypatch.setattr(monitor_mod, "QUEUE_ALERT_THRESHOLD", test_threshold)
    monkeypatch.setattr(monitor_mod, "JOB_INTERVAL_SECONDS", 0.01) # 加快循环

    # 模拟队列长度超过阈值
    for i in range(test_threshold + 1):
        fake_redis.lpush("queue:session_tasks", f"item_{i}")

    # 创建并启动协程
    task = asyncio.create_task(monitor_mod.monitor_queue_length_loop("queue:session_tasks"))
    await asyncio.sleep(0.05) # 等待协程执行几次

    # 验证告警函数被调用
    mock_alerts.assert_called()
    # 验证调用时的参数
    call_args, _ = mock_alerts.call_args
    assert call_args[0] == "queue:session_tasks"
    assert call_args[1] == test_threshold + 1

    # 取消任务
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass