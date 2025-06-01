# 文件路径：src/main.py
# -*- coding: utf-8 -*-
"""
应用入口：启动 FastAPI 服务并创建后台监控协程 (优化版)
    - on_startup: 创建队列长度和节点故障率的后台监控协程。
    - /metrics: (可选) 暴露 Prometheus 监控指标。
"""

import uvicorn
import asyncio
import logging

from fastapi import FastAPI

from src.config.settings import (
    API_HOST, API_PORT, PROMETHEUS_METRICS_ENABLED
)
from src.workers.queue_monitor import monitor_queue_length_loop
from src.workers.alert import monitor_failure_rate_loop
from src.api.api_router import router as api_router

# 配置主模块日志
logger = logging.getLogger(__name__)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()]
    )

app = FastAPI(title="DeerFlow 监控服务 (优化版)")

# 注册 REST API 路由
app.include_router(api_router)

# 优化点：根据配置决定是否挂载 Prometheus 指标路由
if PROMETHEUS_METRICS_ENABLED:
    try:
        from prometheus_client import make_asgi_app
        # 创建一个 ASGI 应用用于暴露指标
        metrics_app = make_asgi_app()
        # 将 /metrics 路由挂载到主应用
        app.mount("/metrics", metrics_app)
        logger.info("Prometheus /metrics 端点已启用。")
    except ImportError:
        logger.warning("prometheus_client 未安装，/metrics 端点将不可用。请运行 `pip install prometheus_client`。")


@app.on_event("startup")
async def startup_event():
    """
    应用启动时：创建后台异步任务
    """
    logger.info("初始化后台监控任务...")
    loop = asyncio.get_event_loop()
    # 启动队列长度监控
    loop.create_task(monitor_queue_length_loop())
    # 启动节点故障率监控
    loop.create_task(monitor_failure_rate_loop())
    logger.info("后台监控协程已启动。")

@app.get("/")
async def root():
    """应用根路径，用于健康检查"""
    return {"message": "DeerFlow Monitoring Service is running."}

if __name__ == "__main__":
    logger.info(f"启动 Uvicorn 服务器: host={API_HOST}, port={API_PORT}")
    uvicorn.run("src.main:app", host=API_HOST, port=API_PORT, reload=True)