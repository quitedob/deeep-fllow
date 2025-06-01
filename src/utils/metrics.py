# 文件路径：src/utils/metrics.py
# -*- coding: utf-8 -*-
"""
Prometheus 指标工具模块：
    - 定义 Gauge 和 Counter 指标
    - 提供更新指标的方法
    - 提供在 FastAPI 中注册 /metrics 路由的方法
使用方式：
    在 monitor_queue_length_loop 和 monitor_failure_rate_loop 中调用 update_* 方法更新指标
    在 main.py 中调用 register_metrics_route(app) 添加 /metrics 路由
"""

from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Response

# -----------------------------
# 1. 定义 Prometheus 指标
# -----------------------------
# 当前 session_tasks 队列长度
QUEUE_LENGTH_GAUGE = Gauge("session_queue_length", "当前 Redis 队列 session_tasks 长度")
# 节点任务失败率
FAILURE_RATE_GAUGE = Gauge("node_failure_rate", "当前节点任务失败率")
# 队列告警触发次数
QUEUE_ALERT_COUNT = Counter("queue_alert_count", "Redis 队列长度告警触发次数")
# 节点告警触发次数
FAILURE_ALERT_COUNT = Counter("failure_alert_count", "节点故障率告警触发次数")

# -----------------------------
# 2. 更新指标方法
# -----------------------------
def update_queue_length_metric(length: int):
    """
    更新队列长度 Gauge 指标
    参数：
      length: 当前队列长度
    """
    QUEUE_LENGTH_GAUGE.set(length)

def update_failure_rate_metric(rate: float):
    """
    更新节点失败率 Gauge 指标
    参数：
      rate: 当前失败率 (0.0~1.0)
    """
    FAILURE_RATE_GAUGE.set(rate)

def increment_queue_alert_count():
    """
    队列告警触发时调用，告警次数 +1
    """
    QUEUE_ALERT_COUNT.inc()

def increment_failure_alert_count():
    """
    节点告警触发时调用，告警次数 +1
    """
    FAILURE_ALERT_COUNT.inc()

# -----------------------------
# 3. 在 FastAPI 中注册 /metrics 路由
# -----------------------------
def register_metrics_route(app: FastAPI):
    """
    在 FastAPI 应用中添加 /metrics 路由，供 Prometheus 抓取指标
    应在应用启动后调用，如：
        from src.utils.metrics import register_metrics_route
        register_metrics_route(app)
    """
    @app.get("/metrics")
    def metrics():
        """
        返回所有 Prometheus 指标。
        Prometheus Server 定期抓取此接口数据。
        """
        data = generate_latest()
        return Response(data, media_type=CONTENT_TYPE_LATEST)