# src/workers/queue_monitor.py
# -*- coding: utf-8 -*-
"""
队列监控模块：本地版本使用 Python 内置 Queue 模拟队列，
定时检查长度并触发告警；未来可通过配置切换为 Redis、RabbitMQ 等队列。
"""
import asyncio
import time
import logging
from queue import Queue # Standard library queue for local simulation
from typing import Any # For type hint

from src.config.settings import QUEUE_LENGTH_THRESHOLD, ALERT_PROVIDER, JOB_INTERVAL_SECONDS
from src.adapters.local_alert_adapter import LocalAlertAdapter
from src.adapters.cloud_alert_adapter import CloudAlertAdapter

logger = logging.getLogger(__name__)

task_queue = Queue()

def enqueue_task(task_item: Any):
    """
    将任务压入队列
    """
    task_queue.put(task_item)
    logger.info(f"Task enqueued (local queue): {task_item}")

def dequeue_task() -> Any:
    """
    从队列弹出任务
    """
    if not task_queue.empty():
        task_item = task_queue.get()
        logger.info(f"Task dequeued (local queue): {task_item}")
        return task_item
    return None

def send_alert(subject: str, content: str): # Defined here as per user snippet
    """
    根据配置选择本地或云端告警
    """
    logger.info(f"Sending queue length alert. Provider: {ALERT_PROVIDER}. Subject: {subject}")
    if ALERT_PROVIDER == "cloud":
        CloudAlertAdapter.notify(subject, content)
    else: # Default to local
        LocalAlertAdapter.notify(subject, content)

async def monitor_queue_length(interval: int = JOB_INTERVAL_SECONDS):
    """
    异步定时任务：每隔 interval 秒检查队列长度
    如超过 QUEUE_LENGTH_THRESHOLD，触发告警
    """
    logger.info(f"Local Queue monitor started. Interval: {interval}s, Threshold: {QUEUE_LENGTH_THRESHOLD}.") # Corrected logger name
    while True:
        try: # Added try-except around the loop content for robustness
            current_length = task_queue.qsize()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            logger.debug(f"Local Queue length check at {timestamp}: {current_length} (Threshold: {QUEUE_LENGTH_THRESHOLD})")

            if current_length > QUEUE_LENGTH_THRESHOLD: # User used > not >=
                subject = "【告警】队列长度过高" # Changed subject to be more generic for queue
                content = f"时间：{timestamp}，当前队列长度：{current_length}，超过阈值：{QUEUE_LENGTH_THRESHOLD}"
                logger.warning(f"Alert triggered for queue length: {subject} - {content}")
                send_alert(subject, content) # Calls the local send_alert

            await asyncio.sleep(interval)
        except KeyboardInterrupt: # Allow graceful exit from loop if run directly
            logger.info("Local Queue monitor loop received KeyboardInterrupt, stopping...")
            break
        except Exception as e:
            logger.error(f"Local Queue monitor loop encountered an error: {e}", exc_info=True)
            await asyncio.sleep(interval) # Wait before retrying after an error


def get_queue_length() -> int:
    """
    返回当前队列长度，以供 REST 接口调用
    """
    length = task_queue.qsize()
    logger.debug(f"API query for local queue length: {length}")
    return length

def start_monitoring():
    """
    应用启动时调用，开启后台监控协程
    """
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    logger.info("Creating queue monitoring task for local queue monitor...") # Corrected logger name
    loop.create_task(monitor_queue_length())
