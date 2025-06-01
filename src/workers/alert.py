# src/workers/alert.py
# -*- coding: utf-8 -*-
"""
节点故障率告警模块：统计本地模拟节点的失败率，若超出阈值则触发告警
"""
import time
import logging
from collections import deque
from typing import Deque, List # Added List as it's used by LocalAlertAdapter via settings

from src.config.settings import FAILURE_RATE_THRESHOLD, ALERT_PROVIDER
# Imports for adapters as per user's snippet for this file
from src.adapters.local_alert_adapter import LocalAlertAdapter
from src.adapters.cloud_alert_adapter import CloudAlertAdapter

logger = logging.getLogger(__name__)

MAX_WINDOW_SIZE = 100
node_result_window: Deque[bool] = deque(maxlen=MAX_WINDOW_SIZE)

def record_task_result(success: bool):
    """
    每当节点执行完一个任务后调用：将成功/失败数据加入滑动窗口
    """
    node_result_window.append(success)
    logger.debug(f"Task result recorded: {success}. Window size: {len(node_result_window)}")

def get_failure_rate() -> float:
    """
    计算当前滑动窗口中的失败率
    """
    if not node_result_window:
        return 0.0
    failure_count = node_result_window.count(False)
    rate = failure_count / len(node_result_window)
    logger.debug(f"Current failure rate: {rate:.2f} (Failures: {failure_count}, Window: {len(node_result_window)})")
    return rate

def send_alert(subject: str, content: str): # This is the send_alert from user's snippet for this file
    """
    根据配置选择本地或云端告警
    """
    logger.info(f"Sending failure rate alert. Provider: {ALERT_PROVIDER}. Subject: {subject}")
    if ALERT_PROVIDER == "cloud":
        CloudAlertAdapter.notify(subject, content)
    else: # Default to local
        LocalAlertAdapter.notify(subject, content) # Calls the LocalAlertAdapter.notify

def evaluate_node_health():
    """
    检查节点健康状态，如失败率超过阈值则触发告警
    """
    rate = get_failure_rate()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    # Log level changed to debug for less verbosity unless an alert is triggered
    logger.debug(f"Evaluating node health at {timestamp}. Current failure rate: {rate*100:.2f}% (Threshold: {FAILURE_RATE_THRESHOLD*100:.2f}%)")

    if rate > FAILURE_RATE_THRESHOLD: # User used > not >=
        subject = "【告警】节点故障率过高"
        content = f"时间：{timestamp}，当前失败率：{rate*100:.2f}%，超过阈值：{FAILURE_RATE_THRESHOLD*100:.2f}%"
        logger.warning(f"Alert triggered for high failure rate: {subject} - {content}")
        send_alert(subject, content)

# The user's plan also mentions an async monitor loop for failure rate in main.py:
# async def monitor_failure_rate():
#     while True:
#         evaluate_node_health()
#         await asyncio.sleep(60)
# This means evaluate_node_health is the function to be called periodically.
# This file itself doesn't need an async loop if main.py handles scheduling it.
