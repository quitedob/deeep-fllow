# src/main.py
# -*- coding: utf-8 -*- # Added for consistency
"""
应用入口：启动监控协程并运行 FastAPI 应用
"""
import uvicorn
import asyncio # Ensure asyncio is imported
from fastapi import FastAPI
import logging # Import logging for the main module logger
import os # Needed for uvicorn.run app_dir if used, or other path manipulations

# Assuming settings and router are imported correctly
from src.config.settings import API_HOST, API_PORT, JOB_INTERVAL_SECONDS # JOB_INTERVAL_SECONDS imported here
from src.workers.queue_monitor import start_monitoring as start_queue_monitoring # Aliased for clarity
from src.workers.alert import evaluate_node_health # This is the function to be called periodically
from src.api.api_router import router as api_router # Aliased for clarity

# Configure logger for this module
logger = logging.getLogger(__name__)
# Basic logging configuration should ideally be done once for the entire application.
# If not already configured by another module (like queue_monitor's basicConfig),
# some default configuration might be needed here for these logs to appear.
# Example: (ensuring it only runs if no handlers are configured for root logger)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler()] # Default to stream if no file handlers from other modules
    )


app = FastAPI(title="DeerFlow Monitoring Service") # Added title

# 注册路由
app.include_router(api_router) # Use aliased router

@app.on_event("startup")
async def startup_event():
    """
    应用启动时：开启队列监控协程，并定时评估节点健康状态
    """
    # 启动队列长度监控
    logger.info("Initializing queue length monitoring...")
    start_queue_monitoring() # This was from queue_monitor.py (local queue version)

    # 启动节点故障率定时评估
    logger.info("Initializing node failure rate monitoring...")
    async def monitor_failure_rate_task():
        while True:
            try:
                logger.debug("Evaluating node health for failure rate...")
                evaluate_node_health() # From src.workers.alert
                await asyncio.sleep(JOB_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Error in monitor_failure_rate_task: {e}", exc_info=True)
                # Wait before retrying to prevent tight loop on persistent error
                await asyncio.sleep(JOB_INTERVAL_SECONDS)

    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed(): # Check if the default loop is closed
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError: # If no current event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.create_task(monitor_failure_rate_task())
    logger.info("Background monitoring tasks scheduled.")


# Add a root endpoint for basic check
@app.get("/")
async def root():
    return {"message": "DeerFlow Monitoring Service is running."}


if __name__ == "__main__":
    # 本地开发时直接运行
    logger.info(f"Starting Uvicorn server on {API_HOST}:{API_PORT}")
    # User's snippet: uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
    # This works if this file (main.py) is in the root of the Python path Uvicorn uses,
    # or if `src` is added to PYTHONPATH and then `main:app` refers to `src.main:app`.
    # For direct execution `python src/main.py`, to make "main:app" resolve correctly
    # without complex PYTHONPATH setups, one might need to specify app_dir or use "src.main:app".
    # Sticking to user's snippet assuming their execution environment handles it.
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True)
