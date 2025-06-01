# tests/workers/test_local_queue_monitor.py
# -*- coding: utf-8 -*-
import pytest
import asyncio
import time
import logging # For caplog
from unittest.mock import patch, MagicMock
from queue import Empty as QueueEmptyException # Import Empty from queue module

# Module to test
from src.workers import queue_monitor as local_queue_monitor_mod
from src.config import settings # To patch QUEUE_LENGTH_THRESHOLD etc.
# Import adapters to allow monkeypatching their static notify methods
from src.adapters import local_alert_adapter
from src.adapters import cloud_alert_adapter

@pytest.fixture(autouse=True)
def mock_adapter_notify_methods(monkeypatch):
    # Mocks out the alert adapters' static notify methods.
    mock_local_notify = MagicMock()
    mock_cloud_notify = MagicMock()

    monkeypatch.setattr(local_alert_adapter.LocalAlertAdapter, 'notify', mock_local_notify)
    monkeypatch.setattr(cloud_alert_adapter.CloudAlertAdapter, 'notify', mock_cloud_notify)
    return mock_local_notify, mock_cloud_notify

@pytest.fixture
def local_task_queue_fixture(monkeypatch):
    # Provides direct access to the local task_queue for manipulation in tests and ensures it's empty.
    q = local_queue_monitor_mod.task_queue
    while not q.empty():
        try:
            q.get_nowait()
        except QueueEmptyException:
            break
    return q


def test_enqueue_dequeue_local_queue(local_task_queue_fixture):
    assert local_queue_monitor_mod.get_queue_length() == 0
    local_queue_monitor_mod.enqueue_task("task1")
    assert local_queue_monitor_mod.get_queue_length() == 1
    local_queue_monitor_mod.enqueue_task("task2")
    assert local_queue_monitor_mod.get_queue_length() == 2

    item1 = local_queue_monitor_mod.dequeue_task()
    assert item1 == "task1"
    assert local_queue_monitor_mod.get_queue_length() == 1

    item2 = local_queue_monitor_mod.dequeue_task()
    assert item2 == "task2"
    assert local_queue_monitor_mod.get_queue_length() == 0

    item_none = local_queue_monitor_mod.dequeue_task()
    assert item_none is None

def test_get_queue_length_local_queue(local_task_queue_fixture):
    assert local_queue_monitor_mod.get_queue_length() == 0
    local_task_queue_fixture.put("item")
    assert local_queue_monitor_mod.get_queue_length() == 1

@patch.object(settings, 'QUEUE_LENGTH_THRESHOLD', 5)
@patch.object(settings, 'JOB_INTERVAL_SECONDS', 0.01)
@patch.object(local_queue_monitor_mod, 'send_alert')
@pytest.mark.asyncio
async def test_monitor_queue_length_loop_alerts_local_queue(mock_send_alert, local_task_queue_fixture, caplog):
    caplog.set_level(logging.INFO)

    local_queue_monitor_mod.enqueue_task("t1")
    local_queue_monitor_mod.enqueue_task("t2")

    monitor_task = asyncio.create_task(local_queue_monitor_mod.monitor_queue_length())
    await asyncio.sleep(0.05) # Allow a few cycles for checks (0.01 interval * 5)

    mock_send_alert.assert_not_called()
    assert "Alert triggered for queue length" not in caplog.text

    # Fill queue to exceed threshold (5)
    # Current size is 2. Need 5 + 1 = 6. So add 4 more.
    for i in range(settings.QUEUE_LENGTH_THRESHOLD + 1 - local_task_queue_fixture.qsize()):
        local_queue_monitor_mod.enqueue_task(f"t_extra_{i}")

    await asyncio.sleep(0.05) # Allow a few more cycles for alert to trigger

    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

    assert mock_send_alert.called
    assert "Alert triggered for queue length" in caplog.text # Check log message

    args, _ = mock_send_alert.call_args
    assert "【告警】队列长度过高" in args[0] # Check subject
    assert f"超过阈值：{settings.QUEUE_LENGTH_THRESHOLD}" in args[1] # Check content

def test_send_alert_uses_local_adapter(mock_adapter_notify_methods, monkeypatch):
    mock_local_notify, mock_cloud_notify = mock_adapter_notify_methods
    monkeypatch.setattr(settings, 'ALERT_PROVIDER', 'local')

    local_queue_monitor_mod.send_alert("Test Subject Local", "Test Content Local")

    mock_local_notify.assert_called_once_with("Test Subject Local", "Test Content Local")
    mock_cloud_notify.assert_not_called()

def test_send_alert_uses_cloud_adapter(mock_adapter_notify_methods, monkeypatch):
    mock_local_notify, mock_cloud_notify = mock_adapter_notify_methods
    monkeypatch.setattr(settings, 'ALERT_PROVIDER', 'cloud')

    local_queue_monitor_mod.send_alert("Test Subject Cloud", "Test Content Cloud")

    mock_cloud_notify.assert_called_once_with("Test Subject Cloud", "Test Content Cloud")
    mock_local_notify.assert_not_called()
