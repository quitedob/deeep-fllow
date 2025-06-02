# tests/workers/test_alert_local.py
# -*- coding: utf-8 -*-
"""
Node Failure Rate Monitor 单元测试（本地版本）：
测试 record_task_result、get_failure_rate、evaluate_node_health (旧名: alert_if_failure_rate_exceeded) 等逻辑。
不依赖 Redis，仅测试滑动窗口与告警分发行为。
"""

import pytest
import asyncio # Not strictly used in these tests but kept if user had it
import time # Not strictly used but kept
import logging # For caplog
from unittest.mock import patch, MagicMock

# Module to test
from src.workers import alert as alert_mod
# Import settings to allow patching, and adapters for mocking
from src.config import settings
from src.adapters import local_alert_adapter, cloud_alert_adapter


# -----------------------------
# 固件：清空滑动窗口，避免前一次测试影响后续
# -----------------------------
@pytest.fixture(autouse=True)
def clear_window_fixture():
    alert_mod.node_result_window.clear()
    yield
    alert_mod.node_result_window.clear()

# -----------------------------
# 测试初始失败率为 0.0
# -----------------------------
def test_initial_failure_rate_zero():
    rate = alert_mod.get_failure_rate()
    assert rate == 0.0

# -----------------------------
# 测试 record_task_result 与计算失败率
# -----------------------------
def test_record_and_failure_rate():
    # 连续记录：True、False、True、False，共 4 条
    alert_mod.record_task_result(True)
    alert_mod.record_task_result(False)
    alert_mod.record_task_result(True)
    alert_mod.record_task_result(False)
    # 当前窗口长度 4，失败数 2 → 失败率 0.5
    rate = alert_mod.get_failure_rate()
    assert pytest.approx(rate, rel=1e-3) == 0.5

    # Test with full window to ensure maxlen is respected
    alert_mod.node_result_window.clear()
    for i in range(alert_mod.MAX_WINDOW_SIZE + 10):
        alert_mod.record_task_result(i % 2 == 0)

    assert len(alert_mod.node_result_window) == alert_mod.MAX_WINDOW_SIZE
    # With alternating True/False, if MAX_WINDOW_SIZE is even, rate is 0.5
    # If MAX_WINDOW_SIZE is odd, it depends on which value started the last 100 items.
    # For simplicity, assuming count(False) / len() is the core test of get_failure_rate
    # and the deque's maxlen behavior is standard.
    # A more direct way to test full window with known content:
    alert_mod.node_result_window.clear()
    for _ in range(alert_mod.MAX_WINDOW_SIZE // 2):
        alert_mod.node_result_window.append(False)
        alert_mod.node_result_window.append(True)
    if alert_mod.MAX_WINDOW_SIZE % 2 != 0: # If odd, add one more to fill
        alert_mod.node_result_window.append(False) # Example, making fails potentially higher

    # This test for full window is more about the deque maxlen than precise rate if content is random.
    # The count(False)/len() is the main thing.
    # Re-evaluating a simple known pattern for full window:
    alert_mod.node_result_window.clear()
    num_false = alert_mod.MAX_WINDOW_SIZE // 2
    num_true = alert_mod.MAX_WINDOW_SIZE - num_false
    for _ in range(num_false): alert_mod.record_task_result(False)
    for _ in range(num_true): alert_mod.record_task_result(True)
    assert pytest.approx(alert_mod.get_failure_rate(), rel=1e-3) == num_false / alert_mod.MAX_WINDOW_SIZE


    alert_mod.node_result_window.clear()
    for _ in range(10): alert_mod.record_task_result(True)
    assert alert_mod.get_failure_rate() == 0.0
    for _ in range(10): alert_mod.record_task_result(False)
    assert pytest.approx(alert_mod.get_failure_rate(), rel=1e-3) == 0.5 # 10 False / 20 total


# -----------------------------
# 测试 evaluate_node_health
# -----------------------------
@patch.object(alert_mod, 'send_alert')
def test_evaluate_node_health_triggers_alert(mock_send_alert_in_alert_mod, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG) # Changed to DEBUG to capture the debug log message

    monkeypatch.setattr(settings, 'FAILURE_RATE_THRESHOLD', 0.1)

    # Scenario 1: Failure rate below threshold
    alert_mod.node_result_window.clear()
    num_tasks = 20
    # Example: threshold 0.1, rate 0.05 (1 fail in 20)
    num_fails_below_thresh = 1
    for _ in range(num_fails_below_thresh): alert_mod.record_task_result(False)
    for _ in range(num_tasks - num_fails_below_thresh): alert_mod.record_task_result(True)

    alert_mod.evaluate_node_health()
    mock_send_alert_in_alert_mod.assert_not_called()
    # Check for the debug log, not the warning log for alert trigger
    assert f"Evaluating node health at" in caplog.text # General log
    assert "Alert triggered for high failure rate" not in caplog.text # Specific warning

    # Scenario 2: Failure rate above threshold
    mock_send_alert_in_alert_mod.reset_mock() # Reset mock for new scenario
    caplog.clear()
    alert_mod.node_result_window.clear()
    # Example: threshold 0.1, rate 0.15 (3 fails in 20)
    num_fails_above_thresh = 3
    for _ in range(num_fails_above_thresh): alert_mod.record_task_result(False)
    for _ in range(num_tasks - num_fails_above_thresh): alert_mod.record_task_result(True)

    alert_mod.evaluate_node_health()
    mock_send_alert_in_alert_mod.assert_called_once()
    assert "Alert triggered for high failure rate" in caplog.text

    args, _ = mock_send_alert_in_alert_mod.call_args
    assert "【告警】节点故障率过高" in args[0]
    current_rate = alert_mod.get_failure_rate() # Should be 3/20 = 0.15
    assert f"当前失败率：{current_rate*100:.2f}%" in args[1]
    assert f"超过阈值：{settings.FAILURE_RATE_THRESHOLD*100:.2f}%" in args[1]


# -----------------------------
# Test for the send_alert function within alert_mod itself (dispatch logic)
# -----------------------------
@patch.object(local_alert_adapter.LocalAlertAdapter, 'notify')
@patch.object(cloud_alert_adapter.CloudAlertAdapter, 'notify')
def test_alert_mod_send_alert_dispatch_local(mock_cloud_notify, mock_local_notify, monkeypatch):
    # Patch ALERT_PROVIDER directly in the alert_mod module's namespace
    monkeypatch.setattr(alert_mod, 'ALERT_PROVIDER', 'local')
    alert_mod.send_alert("Test Subject Local", "Test Content Local")
    mock_local_notify.assert_called_once_with("Test Subject Local", "Test Content Local")
    mock_cloud_notify.assert_not_called()

@patch.object(local_alert_adapter.LocalAlertAdapter, 'notify')
@patch.object(cloud_alert_adapter.CloudAlertAdapter, 'notify')
def test_alert_mod_send_alert_dispatch_cloud(mock_cloud_notify, mock_local_notify, monkeypatch):
    # Patch ALERT_PROVIDER directly in the alert_mod module's namespace
    monkeypatch.setattr(alert_mod, 'ALERT_PROVIDER', 'cloud')
    alert_mod.send_alert("Test Subject Cloud", "Test Content Cloud")
    mock_cloud_notify.assert_called_once_with("Test Subject Cloud", "Test Content Cloud")
    mock_local_notify.assert_not_called()

# The main async loop `monitor_failure_rate_task` is defined in `src/main.py`
# and calls `evaluate_node_health`. So, testing `evaluate_node_health` covers the core logic.
# Direct testing of the async loop would be part of `tests/test_main.py` if needed.

if __name__ == '__main__':
    pytest.main([__file__])
