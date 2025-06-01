# src/a# 文件路径：src/api/api_router.py
# # -*- coding: utf-8 -*-
# """
# REST API 路由定义：提供两个查询接口
#   - GET /api/queue_length: 返回当前 Redis 队列长度
#   - GET /api/failure_rate: 返回当前节点故障率
# """
#
# from fastapi import APIRouter, HTTPException, Depends
# from typing import List
#
# from src.workers.queue_monitor import get_queue_length
# from src.workers.alert import get_failure_rate
# from src.config.settings import API_KEYS
#
# # 简单的 API Key 校验依赖
# async def verify_api_key(x_api_key: str = Depends(lambda x_api_key: x_api_key in API_KEYS)):
#     if not x_api_key:
#         raise HTTPException(status_code=401, detail="Unauthorized: Invalid or Missing API Key")
#
# router = APIRouter(dependencies=[Depends(verify_api_key)])
#
# @router.get("/api/queue_length")
# async def api_get_queue_length():
#     """
#     获取当前 Redis 队列 (queue:session_tasks) 的长度
#     返回示例:
#       { "queue_length": 123 }
#     """
#     try:
#         length = get_queue_length("queue:session_tasks")
#         if length == -1:
#             raise HTTPException(status_code=503, detail="无法连接到 Redis 或获取队列长度失败")
#         return {"queue_length": length}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"获取队列长度异常: {e}")
#
# @router.get("/api/failure_rate")
# async def api_get_failure_rate():
#     """
#     获取当前节点故障率（最近 MAX_WINDOW_SIZE 条任务）
#     返回示例:
#       { "failure_rate": 0.07 }
#     """
#     try:
#         rate = get_failure_rate()
#         return {"failure_rate": rate}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"获取失败率异常: {e}")