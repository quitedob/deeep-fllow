# 文件路径：src/workers/queue_monitor.py
# -*- coding: utf-8 -*-
"""
Redis 队列长度监控模块 (优化版):
    - 引入状态机 (NORMAL/ALERTING)，实现告警去重和恢复通知。
    - 仅在状态变化时发送告警，避免重复打扰。
"""

import asyncio
import time
import redis
import logging
from typing import Optional

from src.config.settings import (
    REDIS_HOST, REDIS_PORT, REDIS_DB,
    QUEUE_ALERT_THRESHOLD, ALERT_PROVIDER,
    JOB_INTERVAL_SECONDS, ALERT_STATE_EXPIRY_SECONDS
)
from src.adapters.local_alert_adapter import LocalAlertAdapter
from src.adapters.cloud_alert_adapter import CloudAlertAdapter
from src.utils.cache import get_alert_state, set_alert_state

# 可选：Prometheus 埋点
try:
    from prometheus_client import Gauge, Counter

    QUEUE_LENGTH_GAUGE = Gauge("session_queue_length", "Redis 队列 session_tasks 的当前长度")
    ALERT_COUNT_COUNTER = Counter("queue_alert_count", "Redis 队列长度告警触发次数", ["type"])
except ImportError:
    QUEUE_LENGTH_GAUGE = None
    ALERT_COUNT_COUNTER = None

logger = logging.getLogger(__name__)
_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
ALERT_TYPE = "queue_length"


def get_queue_length(queue_name: str = "queue:session_tasks") -> int:
    """获取 Redis 列表的当前长度"""
    try:
        return _redis.llen(queue_name)
    except Exception as e:
        logger.error(f"[QueueMonitor] 获取 Redis 队列长度失败: {e}", exc_info=True)
        return -1


def send_queue_alert(is_recovery: bool, queue_name: str, length: int):
    """
    发送队列长度告警或恢复通知
    简化注释：发送队列告警
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    if is_recovery:
        subject = f"[恢复] Redis 队列恢复正常: {queue_name}"
        body = (f"恢复时间: {timestamp}\n队列名称: {queue_name}\n"
                f"当前长度: {length} (已低于阈值 {QUEUE_ALERT_THRESHOLD})")
        dingtalk_msg = f"【队列恢复】{queue_name} 长度 {length} < {QUEUE_ALERT_THRESHOLD}"
    else:
        subject = f"[告警] Redis 队列过长: {queue_name} 长度 {length}"
        body = (f"告警时间: {timestamp}\n队列名称: {queue_name}\n"
                f"当前长度: {length} (已达到或超过阈值 {QUEUE_ALERT_THRESHOLD})")
        dingtalk_msg = f"【队列告警】{queue_name} 长度 {length} ≥ {QUEUE_ALERT_THRESHOLD}"

    logger.info(f"准备发送通知: {subject}")
    if ALERT_PROVIDER == "local":
        LocalAlertAdapter.notify(subject, body)
        from src.adapters.dingtalk_adapter import send_dingbot_text
        send_dingbot_text(dingtalk_msg)
    else:
        CloudAlertAdapter.notify(subject, body)

    if PROMETHEUS_METRICS_ENABLED and ALERT_COUNT_COUNTER:
        alert_type_label = "recovery" if is_recovery else "alert"
        ALERT_COUNT_COUNTER.labels(type=alert_type_label).inc()


async def monitor_queue_length_loop(queue_name: str = "queue:session_tasks"):
    """
    异步定时监控循环 (优化版)
    简化注释：队列监控循环
    """
    logger.info(
        f"队列监控已启动 (优化版), 对象: {queue_name}, 间隔: {JOB_INTERVAL_SECONDS}秒, 阈值: {QUEUE_ALERT_THRESHOLD}")
    while True:
        try:
            current_length = get_queue_length(queue_name)
            if current_length < 0:
                await asyncio.sleep(60)
                continue

            if PROMETHEUS_METRICS_ENABLED and QUEUE_LENGTH_GAUGE:
                QUEUE_LENGTH_GAUGE.set(current_length)

            previous_state = get_alert_state(ALERT_TYPE) or "NORMAL"
            is_over_threshold = current_length >= QUEUE_ALERT_THRESHOLD

            # 状态切换检测
            if is_over_threshold and previous_state == "NORMAL":
                # 从正常变为告警
                logger.warning(f"[QueueMonitor] 状态变化: NORMAL -> ALERTING. 长度: {current_length}")
                send_queue_alert(is_recovery=False, queue_name=queue_name, length=current_length)
                set_alert_state(ALERT_TYPE, "ALERTING", ex=ALERT_STATE_EXPIRY_SECONDS)
            elif not is_over_threshold and previous_state == "ALERTING":
                # 从告警恢复为正常
                logger.info(f"[QueueMonitor] 状态变化: ALERTING -> NORMAL. 长度: {current_length}")
                send_queue_alert(is_recovery=True, queue_name=queue_name, length=current_length)
                set_alert_state(ALERT_TYPE, "NORMAL", ex=ALERT_STATE_EXPIRY_SECONDS)
            else:
                logger.debug(f"[QueueMonitor] 状态未变 ({previous_state}). 长度: {current_length}")

        except Exception as e:
            logger.error(f"[QueueMonitor] 监控循环异常: {e}", exc_info=True)

        await asyncio.sleep(JOB_INTERVAL_SECONDS)