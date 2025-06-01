# tests/workers/test_queue_monitor.py
# -*- coding: utf-8 -*-
import pytest
import fakeredis
import threading # Not used in final version of tests but kept if user had other plans
import time
import json
from unittest.mock import patch, MagicMock # Ensure MagicMock is imported
import redis # Added import

import src.workers.queue_monitor as monitor_mod
import logging # For caplog

# Fixture to set up fakeredis for the monitor's _redis_client
@pytest.fixture(autouse=True) # autouse for all tests in this module
def fake_redis(monkeypatch): # User's snippet for fixture name
    fake_r = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(monitor_mod, "_redis_client", fake_r)
    return fake_r

# Fixture to mock alert functions
@pytest.fixture(autouse=True)
def mock_alerts(monkeypatch):
    mock_send_email = MagicMock()
    mock_send_dingtalk = MagicMock()

    monkeypatch.setattr(monitor_mod, "send_email_alert", mock_send_email)
    monkeypatch.setattr(monitor_mod, "send_dingtalk_alert", mock_send_dingtalk)

    return mock_send_email, mock_send_dingtalk

def test_get_queue_length(fake_redis): # fake_redis is the client instance
    queue_name = "queue:session_tasks" # Default queue name used by monitor

    # Test empty queue
    assert monitor_mod.get_queue_length(queue_name) == 0

    # Test with items
    fake_redis.lpush(queue_name, "item1", "item2")
    assert monitor_mod.get_queue_length(queue_name) == 2

    # Test non-existent list key (llen returns 0)
    assert monitor_mod.get_queue_length("non_existent_queue") == 0

    # Test Redis error scenario for get_queue_length
    with patch.object(monitor_mod._redis_client, 'llen', side_effect=redis.exceptions.RedisError("Simulated Redis Error")):
        assert monitor_mod.get_queue_length(queue_name) == -1

def test_alert_if_needed_function_sends_alerts(mock_alerts): # mock_alerts fixture provides mocked alert functions
    mock_send_email, mock_send_dingtalk = mock_alerts

    # This test verifies that alert_if_needed calls the alert functions.
    # The threshold check itself is part of run_monitor_loop.
    # Assuming QUEUE_ALERT_THRESHOLD is, for example, 10 for the body text.
    # We can patch it if its value matters for the text, or use the default.
    # The function body uses monitor_mod.QUEUE_ALERT_THRESHOLD for the message.
    with patch.object(monitor_mod, 'QUEUE_ALERT_THRESHOLD', 5): # Example threshold for message
        monitor_mod.alert_if_needed(length=10) # Call with some length

        mock_send_email.assert_called_once()
        mock_send_dingtalk.assert_called_once()

        # Check subject and body content passed to email
        email_args, _ = mock_send_email.call_args
        expected_subject = "[告警] Redis 队列过长: 10"
        expected_body = "当前 queue:session_tasks 长度为 10，超过阈值 5。"
        assert email_args[0] == expected_subject
        assert email_args[1] == expected_body
        assert email_args[2] == monitor_mod.ALERT_EMAIL_LIST # Checks it uses the list from settings

        # Check message passed to dingtalk
        dingtalk_args, _ = mock_send_dingtalk.call_args
        assert dingtalk_args[0] == expected_body


@patch('src.workers.queue_monitor.time.sleep') # Mock time.sleep in the loop
@patch.object(monitor_mod, 'alert_if_needed') # Mock the actual alert decision function
def test_run_monitor_loop_alerting_behavior(mock_alert_if_needed_func, mock_sleep, fake_redis, caplog):
    caplog.set_level(logging.INFO) # To capture log messages from the monitor

    # Patch QUEUE_ALERT_THRESHOLD for predictable testing
    with patch.object(monitor_mod, 'QUEUE_ALERT_THRESHOLD', 10):
        # Scenario 1: Queue length below threshold
        fake_redis.lpush("queue:session_tasks", "item1") # length = 1

        # Make sleep raise an exception to stop the loop after one iteration
        mock_sleep.side_effect = KeyboardInterrupt("Stopping loop for test scenario 1")

        # The KeyboardInterrupt is caught inside run_monitor_loop, so it shouldn't propagate out
        monitor_mod.run_monitor_loop()

        mock_alert_if_needed_func.assert_not_called()
        assert "[Monitor] 当前队列长度: 1" in caplog.text
        assert "触发告警" not in caplog.text # Check log for no alert trigger

        # Clear queue and mocks for next scenario
        fake_redis.delete("queue:session_tasks")
        mock_alert_if_needed_func.reset_mock()
        caplog.clear()

        # Scenario 2: Queue length meets or exceeds threshold
        for i in range(10): # length = 10
            fake_redis.lpush("queue:session_tasks", f"item{i}")

        mock_sleep.side_effect = KeyboardInterrupt("Stopping loop for test scenario 2") # Reset side effect

        # The KeyboardInterrupt is caught inside run_monitor_loop
        monitor_mod.run_monitor_loop()

        mock_alert_if_needed_func.assert_called_once_with(10) # alert_if_needed called with length 10
        assert "[Monitor] 当前队列长度: 10" in caplog.text
        assert f"[Monitor] 队列长度 10 >= 阈值 10，触发告警" in caplog.text

        # Clear queue and mocks for next scenario
        fake_redis.delete("queue:session_tasks")
        mock_alert_if_needed_func.reset_mock()
        caplog.clear()

        # Scenario 3: get_queue_length returns -1 (error)
        with patch.object(monitor_mod, 'get_queue_length', return_value=-1):
            mock_sleep.side_effect = KeyboardInterrupt("Stopping loop for test scenario 3")
            # The KeyboardInterrupt is caught inside run_monitor_loop
            monitor_mod.run_monitor_loop()

        mock_alert_if_needed_func.assert_not_called() # No alert if queue length fetch fails
        assert "Redis连接或LLEN命令失败，60秒后重试..." in caplog.text


if __name__ == '__main__':
    # This allows running tests with `python tests/workers/test_queue_monitor.py`
    # but `pytest` is the recommended way.
    pytest.main([__file__])
