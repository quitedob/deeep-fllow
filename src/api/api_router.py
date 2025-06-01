# src/api/api_router.py
# -*- coding: utf-8 -*- # Added for consistency
"""
REST API 路由：提供队列长度与节点故障率查询接口
"""
from fastapi import APIRouter, HTTPException
# Assuming workers package and modules are correctly structured for these imports
from src.workers.queue_monitor import get_queue_length # For local queue version
from src.workers.alert import get_failure_rate # For failure rate
# import logging # Logger could be added if desired for endpoint errors

# logger = logging.getLogger(__name__) # Example if logger is added

router = APIRouter()

@router.get("/api/queue_length")
async def api_get_queue_length(): # Renamed from api_get_current_queue_length for brevity
    """
    获取当前队列长度
    """
    try:
        # This get_queue_length is from the queue_monitor that uses the local Python queue.
        length = get_queue_length()
        return {"queue_length": length}
    except Exception as e:
        # logger.error(f"Error in /api/queue_length: {e}", exc_info=True) # Example logging
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/failure_rate")
async def api_get_failure_rate(): # Renamed from api_get_current_failure_rate
    """
    获取当前节点故障率
    """
    try:
        rate = get_failure_rate()
        return {"failure_rate": rate}
    except Exception as e:
        # logger.error(f"Error in /api/failure_rate: {e}", exc_info=True) # Example logging
        raise HTTPException(status_code=500, detail=str(e))
