# 文件路径：src/workers/alert.py
# -*- coding: utf-8 -*-
"""
节点故障率监控模块 (优化版):
    - 引入状态机 (NORMAL/ALERTING)，实现告警去重和恢复通知。
"""
import asyncio
import time
import logging
from collections import deque
from typing import Deque

from src.config.settings import (
    FAILURE_RATE_THRESHOLD, ALERT_PROVIDER,
    JOB_INTERVAL_SECONDS, ALERT_STATE_EXPIRY_SECONDS
)
from src.adapters.local_alert_adapter import LocalAlertAdapter
from src.adapters.cloud_alert_adapter import CloudAlertAdapter
from src.utils.cache import get_alert_state, set_alert_state

# 可选 Prometheus 埋点
try:
    from prometheus_client import Gauge, Counter

    FAILURE_RATE_GAUGE = Gauge("node_failure_rate", "节点任务执行失败率")
    ALERT_COUNT_COUNTER = Counter("failure_alert_count", "节点故障率告警触发次数", ["type"])
except ImportError:
    FAILURE_RATE_GAUGE = None
    ALERT_COUNT_COUNTER = None

logger = logging.getLogger(__name__)
MAX_WINDOW_SIZE = 100
node_result_window: Deque[bool] = deque(maxlen=MAX_WINDOW_SIZE)
ALERT_TYPE = "failure_rate"


def record_task_result(success: bool):
    """记录任务执行结果到滑动窗口"""
    node_result_window.append(success)
    logger.debug(f"[NodeAlert] 记录任务结果: {'成功' if success else '失败'}，窗口长度: {len(node_result_window)}")


def get_failure_rate() -> float:
    """计算当前滑动窗口中的失败率"""
    if not node_result_window:
        return 0.0
    return node_result_window.count(False) / len(node_result_window)


def send_failure_alert(is_recovery: bool, rate: float):
    """
    发送故障率告警或恢复通知
    简化注释：发送故障率告警
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    if is_recovery:
        subject = f"[恢复] 节点故障率恢复正常"
        body = (f"恢复时间: {timestamp}\n当前失败率: {rate * 100:.2f}%\n"
                f"已低于阈值: {FAILURE_RATE_THRESHOLD * 100:.2f}%")
        dingtalk_msg = f"【节点恢复】失败率 {rate * 100:.2f}% < {FAILURE_RATE_THRESHOLD * 100:.2f}%"
    else:
        subject = f"[告警] 节点故障率过高: {rate * 100:.2f}%"
        body = (f"告警时间: {timestamp}\n当前失败率: {rate * 100:.2f}%\n"
                f"已超过阈值: {FAILURE_RATE_THRESHOLD * 100:.2f}%")
        dingtalk_msg = f"【节点告警】失败率 {rate * 100:.2f}% > {FAILURE_RATE_THRESHOLD * 100:.2f}%"

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


async def monitor_failure_rate_loop():
    """
    异步定时监控节点故障率 (优化版)
    简化注释：故障率监控循环
    """
    logger.info(
        f"节点故障率监控已启动 (优化版), 间隔: {JOB_INTERVAL_SECONDS}秒, 阈值: {FAILURE_RATE_THRESHOLD * 100:.2f}%")
    while True:
        try:
            current_rate = get_failure_rate()

            if PROMETHEUS_METRICS_ENABLED and FAILURE_RATE_GAUGE:
                FAILURE_RATE_GAUGE.set(current_rate)

            previous_state = get_alert_state(ALERT_TYPE) or "NORMAL"
            is_over_threshold = current_rate > FAILURE_RATE_THRESHOLD

            if is_over_threshold and previous_state == "NORMAL":
                logger.warning(f"[NodeAlert] 状态变化: NORMAL -> ALERTING. 失败率: {current_rate * 100:.2f}%")
                send_failure_alert(is_recovery=False, rate=current_rate)
                set_alert_state(ALERT_TYPE, "ALERTING", ex=ALERT_STATE_EXPIRY_SECONDS)
            elif not is_over_threshold and previous_state == "ALERTING":
                logger.info(f"[NodeAlert] 状态变化: ALERTING -> NORMAL. 失败率: {current_rate * 100:.2f}%")
                send_failure_alert(is_recovery=True, rate=current_rate)
                set_alert_state(ALERT_TYPE, "NORMAL", ex=ALERT_STATE_EXPIRY_SECONDS)
            else:
                logger.debug(f"[NodeAlert] 状态未变 ({previous_state}). 失败率: {current_rate * 100:.2f}%")

        except Exception as e:
            logger.error(f"[NodeAlert] 监控循环异常: {e}", exc_info=True)

        await asyncio.sleep(JOB_INTERVAL_SECONDS)