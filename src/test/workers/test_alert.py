# 文件路径：tests/workers/test_alert.py
# -*- coding: utf-8 -*-
"""
Node Failure Rate Monitor 单元测试：模拟任务结果记录与告警逻辑
测试点包括 record_task_result、get_failure_rate、alert_if_failure_rate_exceeded、monitor_failure_rate_loop 等。
"""

import pytest
import asyncio
from unittest.mock import MagicMock

import src.workers.alert as alert_mod


# -------------------------
# 在每个测试前清空滑动窗口
# -------------------------
@pytest.fixture(autouse=True)
def clear_window():
    alert_mod.node_result_window.clear()


# -------------------------
# 测试初始失败率为 0.0
# -------------------------
def test_initial_failure_rate_zero():
    rate = alert_mod.get_failure_rate()
    assert rate == 0.0


# -------------------------
# 测试 record_task_result 与计算失败率
# -------------------------
def test_record_and_failure_rate():
    # 记录 2 次成功，3 次失败
    for s in [True, True, False, False, False]:
        alert_mod.record_task_result(s)
    # 失败率为 3/5 = 0.6
    rate = alert_mod.get_failure_rate()
    assert pytest.approx(rate) == 0.6


# -------------------------
# 测试滑动窗口特性
# -------------------------
def test_sliding_window_behavior():
    # 填满窗口
    for i in range(alert_mod.MAX_WINDOW_SIZE):
        alert_mod.record_task_result(True if i % 2 == 0 else False)  # 50% 失败率

    assert len(alert_mod.node_result_window) == alert_mod.MAX_WINDOW_SIZE
    assert pytest.approx(alert_mod.get_failure_rate()) == 0.5

    # 新增一个成功记录，最早的一个记录（成功）将被移除
    alert_mod.record_task_result(True)
    # 窗口内应有 51 个成功，49 个失败
    assert pytest.approx(alert_mod.get_failure_rate()) == 0.49


# -------------------------
# 测试 alert_if_failure_rate_exceeded 告警逻辑
# -------------------------
@pytest.fixture
def mock_alert_adapters(monkeypatch):
    mock_local = MagicMock()
    mock_cloud = MagicMock()
    monkeypatch.setattr(alert_mod.LocalAlertAdapter, "notify", mock_local)
    monkeypatch.setattr(alert_mod.CloudAlertAdapter, "notify", mock_cloud)
    return mock_local, mock_cloud


def test_alert_if_exceeded_triggers_local(mock_alert_adapters, monkeypatch):
    mock_local, mock_cloud = mock_alert_adapters
    monkeypatch.setattr(alert_mod, "FAILURE_RATE_THRESHOLD", 0.4)
    monkeypatch.setenv("ALERT_PROVIDER", "local")

    # 失败率 50% > 40%
    for _ in range(5):
        alert_mod.record_task_result(False)
    for _ in range(5):
        alert_mod.record_task_result(True)

    alert_mod.alert_if_failure_rate_exceeded()

    mock_local.assert_called_once()
    mock_cloud.assert_not_called()


# -------------------------
# 测试 monitor_failure_rate_loop 执行一次后正常退出
# -------------------------
@pytest.mark.asyncio
async def test_monitor_failure_rate_loop_once(monkeypatch):
    # 替换告警逻辑，避免真实发送
    monkeypatch.setattr(alert_mod, "alert_if_failure_rate_exceeded", lambda: None)

    # 启动协程并在短时间后取消
    task = asyncio.create_task(alert_mod.monitor_failure_rate_loop())
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass