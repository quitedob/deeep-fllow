# 文件路径: src/server/app.py
# -*- coding: utf-8 -*-
"""
FastAPI 服务：提供 HTTP/REST 和 WebSocket 接口，用于控制和监控 LangGraph 研究流程。

主要功能:
1. API Key 权限校验。
2. 异步启动流程接口 (`/api/start`)：将任务入队交由 Worker 处理。
3. 同步执行流程接口 (`/api/run_now`)：立即执行流程并等待结果。
4. 状态查询接口 (`/api/status/{session_id}`)。
5. 结果获取接口 (`/api/get_report/{session_id}`, `/api/get_audio/{session_id}`)。
6. 会话重置接口 (`/api/reset/{session_id}`)。
7. WebSocket 实时进度推送 (`/ws/{session_id}`)。
"""

import os
import json
import logging
import uuid  # 用于在 /api/start 未提供 session_id 时生成
import time  # 未直接使用，但 WebSocket 逻辑中常备
import threading  # 用于 WebSocket 后台监听线程
import asyncio  # 用于 run_coroutine_threadsafe

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, Depends
from fastapi.responses import JSONResponse  # 虽然未使用，但 FastAPI 常备
from pydantic import BaseModel, Field  # 用于请求体校验
from typing import Optional, Dict, Any, List
from starlette.websockets import WebSocketState  # 用于检查 WebSocket 连接状态

import redis  # 用于 WebSocket 的 PubSub 客户端

from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, API_KEYS
from src.graph.builder import run_langgraph, get_existing_state, reset_session
from src.utils.cache import enqueue_session  # 显式导入用于 /api/start
from src.utils.logging import init_logger

# 初始化日志
init_logger("INFO")  # 确保日志已配置
logger = logging.getLogger(__name__)

# 全局 Redis Pub/Sub 客户端 (用于 WebSocket)
_redis_pubsub_client = None


def get_redis_pubsub_client():
    """获取 Redis Pub/Sub 客户端单例 (用于 WebSocket)"""
    global _redis_pubsub_client
    if _redis_pubsub_client is None:
        _redis_pubsub_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return _redis_pubsub_client


app = FastAPI(title="DeerFlow 带记忆服务", version="1.0.0")


# --- 权限校验依赖注入 ---
async def verify_api_key(x_api_key: str = Header(None, description="API 访问凭证")):
    """
    从 Header 中获取 X-API-KEY，校验其合法性。
    如果不合法或缺失，则抛出 401 HTTPException。
    """
    if not x_api_key:
        logger.warning("请求头中缺少 X-API-KEY。")
        raise HTTPException(status_code=401, detail="请求头 X-API-KEY 缺失")
    if x_api_key not in API_KEYS:
        logger.warning(f"无效的 API Key: {x_api_key}")
        raise HTTPException(status_code=401, detail="未授权：无效的 API Key")
    return x_api_key


# --- 请求体模型 ---
class StartRequest(BaseModel):
    topic: str = Field(..., description="研究主题")
    session_id: Optional[str] = Field(None, description="可选的会话ID，若不提供则自动生成")


class RunNowRequest(BaseModel):
    topic: str = Field(..., description="研究主题")
    session_id: Optional[str] = Field(None, description="可选的会话ID")
    use_sharded: bool = Field(True, description="是否使用分片存储Redis状态")
    initial_state: Optional[Dict[str, Any]] = Field(None, description="可选的完整初始状态字典")


# --- API 端点定义 ---

@app.post("/api/start", dependencies=[Depends(verify_api_key)], summary="异步启动研究流程")
async def api_start(payload: StartRequest) -> Dict[str, Any]:
    """
    异步启动 LangGraph 流程：将任务（topic 和 session_id）放入 Redis 队列。
    由后台的 session_worker.py 消费队列并实际执行 run_langgraph。
    - **topic**: 必要的研究主题。
    - **session_id**: 可选。如果提供，则使用此ID；否则自动生成UUID。
    返回包含 `_session_id` 和入队消息的字典。
    """
    sid = payload.session_id if payload.session_id else str(uuid.uuid4())
    logger.info(f"API /api/start: 接收到主题 '{payload.topic}'，会话ID: {sid}，准备入队。")

    # 实际的入队操作，交由 src.utils.cache.enqueue_session 处理
    enqueue_session(sid, payload.topic)

    return {"_session_id": sid, "message": "任务已成功入队，将由后台 Worker 异步处理。"}


@app.post("/api/run_now", dependencies=[Depends(verify_api_key)], summary="同步执行研究流程")
async def api_run_now(payload: RunNowRequest) -> Dict[str, Any]:
    """
    同步阻塞执行 LangGraph 流程。
    直接调用 `run_langgraph`，等待其完成后返回最终状态。
    - **topic**: 必要的研究主题 (除非在 initial_state 中提供)。
    - **session_id**: 可选。
    - **use_sharded**: 是否使用分片存储，默认 True。
    - **initial_state**: 可选，用于传递更复杂的初始状态。
    如果流程执行中发生错误（如获取锁失败、内部异常），会返回包含 "error" 字段的响应。
    """
    effective_initial_state = payload.initial_state if payload.initial_state else {}
    if "topic" not in effective_initial_state and payload.topic:
        effective_initial_state["topic"] = payload.topic

    if not effective_initial_state.get("topic"):
        logger.error("API /api/run_now: 调用时缺少 'topic'。")
        raise HTTPException(status_code=400, detail="必须在 'topic' 字段或 'initial_state' 内部提供主题。")

    logger.info(
        f"API /api/run_now: 开始同步执行流程，主题 '{effective_initial_state['topic']}'，会话ID: {payload.session_id or '将自动生成'}")
    result = run_langgraph(
        initial_state=effective_initial_state,
        session_id=payload.session_id,
        use_sharded=payload.use_sharded
    )

    if "error" in result:
        logger.error(f"API /api/run_now: 流程执行出错，会话ID {result.get('_session_id')}，错误: {result['error']}")
        if result["error"] == "会话正在执行，请稍后重试":
            raise HTTPException(status_code=429, detail=result["error"])  # 429 Too Many Requests
        raise HTTPException(status_code=500, detail=result["error"])  # 其他错误按500处理
    return result


@app.get("/api/status/{session_id}", dependencies=[Depends(verify_api_key)], summary="查询会话状态")
async def api_status(session_id: str) -> Dict[str, Any]:
    """
    返回指定 `session_id` 的当前完整状态。
    如果会话不存在或已过期，返回 404。
    """
    logger.debug(f"API /api/status: 查询会话 {session_id} 的状态。")
    state = get_existing_state(session_id, use_sharded=True)  # 默认使用分片读取
    if not state:
        logger.warning(f"API /api/status: 会话 {session_id} 未找到。")
        raise HTTPException(status_code=404, detail="会话未找到或已过期")
    return state


@app.get("/api/get_report/{session_id}", dependencies=[Depends(verify_api_key)], summary="获取报告路径")
async def api_get_report(session_id: str) -> Dict[str, Any]:
    """
    返回指定 `session_id` 生成的报告文件路径。
    路径信息存储在会话状态的 "report_paths" 字段中。
    """
    logger.debug(f"API /api/get_report: 获取会话 {session_id} 的报告路径。")
    state = get_existing_state(session_id, use_sharded=True)
    if not state:
        raise HTTPException(status_code=404, detail="会话未找到")

    report_paths = state.get("report_paths")
    if report_paths is None:  # 显式检查 None，空字典 {} 是有效但无路径的情况
        return {"message": "报告尚未生成或无报告路径信息。", "report_paths": {}}
    return {"report_paths": report_paths}


@app.get("/api/get_audio/{session_id}", dependencies=[Depends(verify_api_key)], summary="获取音频路径")
async def api_get_audio(session_id: str) -> Dict[str, Any]:
    """
    返回指定 `session_id` 生成的音频文件路径。
    路径信息存储在会话状态的 "audio_path" 字段中。
    """
    logger.debug(f"API /api/get_audio: 获取会话 {session_id} 的音频路径。")
    state = get_existing_state(session_id, use_sharded=True)
    if not state:
        raise HTTPException(status_code=404, detail="会话未找到")

    audio_path = state.get("audio_path")
    if audio_path is None:  # 显式检查 None
        return {"message": "音频尚未生成或无音频路径信息。", "audio_path": None}
    return {"audio_path": audio_path}


@app.delete("/api/reset/{session_id}", dependencies=[Depends(verify_api_key)], summary="重置会话状态")
async def api_reset(session_id: str) -> Dict[str, str]:
    """
    删除指定 `session_id` 在 Redis 中存储的所有状态（包括分片）。
    这允许重新执行该会话。
    """
    logger.info(f"API /api/reset: 请求重置会话 {session_id}。")
    reset_session(session_id, use_sharded=True)  # 默认重置分片存储
    return {"message": f"会话 {session_id} 的状态已成功重置。"}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str,
                             x_api_key: str = Header(None, description="API 访问凭证")):
    """
    WebSocket 端点：
    1. 客户端连接时需在请求头中提供有效的 `X-API-KEY`。
    2. 连接成功后，服务器会订阅 Redis Pub/Sub 频道 `channel:session:{session_id}`。
    3. 从该频道收到的任何消息（通常是JSON字符串，表示节点进度）将直接转发给此 WebSocket 客户端。
    4. 客户端可以发送消息，但当前服务端实现仅记录日志，不作处理。
    """
    # WebSocket 连接的 API Key 校验
    if not x_api_key:
        await websocket.close(code=1008, reason="X-API-KEY header missing")
        return
    if x_api_key not in API_KEYS:
        await websocket.close(code=1008, reason="Unauthorized: Invalid API Key")
        return

    await websocket.accept()
    logger.info(f"WebSocket: 客户端已连接，会话ID: {session_id}")

    redis_cli = get_redis_pubsub_client()
    pubsub = redis_cli.pubsub(ignore_subscribe_messages=True)
    channel = f"channel:session:{session_id}"

    stop_event = asyncio.Event()  # 使用 asyncio.Event 替换 threading.Event
    main_event_loop = asyncio.get_running_loop()  # 获取当前 FastAPI/Uvicorn 运行的事件循环

    async def forward_messages_async():
        """异步监听 Redis Pub/Sub 并转发消息给 WebSocket 客户端"""
        try:
            await pubsub.subscribe(channel)
            logger.info(f"WebSocket: 已订阅 Redis 频道 {channel} (会话ID: {session_id})")
            while not stop_event.is_set():
                try:
                    # pubsub.get_message 现在需要异步处理或在 executor 中运行
                    # 为简单起见，我们使用一个小的非阻塞超时来模拟异步行为
                    # 注意：fakeredis 的 pubsub.get_message(timeout=...) 行为可能与真实 Redis 不同
                    # 更健壮的方式是使用 aioredis 库，或者在线程中运行阻塞的 pubsub.listen()
                    message = await main_event_loop.run_in_executor(None, pubsub.get_message, True, 0.1)  # timeout 0.1s
                    if message and message.get("type") == "message":
                        if websocket.client_state == WebSocketState.CONNECTED:
                            await websocket.send_text(message["data"])
                        else:
                            logger.warning(f"WebSocket: 连接已断开 (会话ID: {session_id})，停止消息转发。")
                            break
                    elif stop_event.is_set():  # 再次检查，确保快速响应停止信号
                        break
                    # 如果没有消息，短暂休眠避免CPU空转 (如果get_message是真阻塞则不需要)
                    # await asyncio.sleep(0.01)
                except redis.exceptions.ConnectionError as e_redis_conn:
                    logger.error(f"WebSocket: Redis Pub/Sub 连接错误 (会话ID: {session_id}): {e_redis_conn}",
                                 exc_info=True)
                    await asyncio.sleep(5)  # 连接错误时等待较长时间再重试
                except Exception as e_ws_send:
                    logger.error(f"WebSocket: 发送消息至客户端失败 (会话ID: {session_id}): {e_ws_send}", exc_info=True)
                    break  # 发送失败通常意味着连接问题，中断循环
        except Exception as e_outer:  # 捕获订阅失败等外部错误
            logger.error(f"WebSocket: 消息转发协程发生外部错误 (会话ID: {session_id}): {e_outer}", exc_info=True)
        finally:
            logger.info(f"WebSocket: 准备取消订阅 Redis 频道 {channel} (会话ID: {session_id})")
            if pubsub.subscribed:
                try:
                    # pubsub.unsubscribe/close 可能不是异步的，需要确认
                    # 对于标准 redis-py，它们是同步的
                    await main_event_loop.run_in_executor(None, pubsub.unsubscribe, channel)
                    await main_event_loop.run_in_executor(None, pubsub.close)
                    logger.info(f"WebSocket: 已取消订阅并关闭 PubSub (会话ID: {session_id})")
                except Exception as e_unsub:
                    logger.error(f"WebSocket: 取消 PubSub 订阅或关闭时出错 (会话ID: {session_id}): {e_unsub}",
                                 exc_info=True)

    forward_task = asyncio.create_task(forward_messages_async())

    try:
        while True:
            # 接收客户端可能发送的消息 (当前实现仅记录日志)
            data = await websocket.receive_text()
            logger.debug(f"WebSocket: 收到客户端消息 (会话ID: {session_id}): {data[:100]}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket: 客户端主动断开连接 (会话ID: {session_id})。")
    except Exception as e_main_ws:
        logger.error(f"WebSocket: 主循环发生异常 (会话ID: {session_id}): {e_main_ws}", exc_info=True)
    finally:
        logger.info(f"WebSocket: 开始清理资源 (会话ID: {session_id})...")
        stop_event.set()  # 通知转发协程停止

        # 等待转发任务完成
        if forward_task and not forward_task.done():
            try:
                await asyncio.wait_for(forward_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket: 消息转发协程未在5秒内停止 (会话ID: {session_id})。")
            except Exception as e_task_cancel:
                logger.error(f"WebSocket: 等待转发协程完成时发生错误: {e_task_cancel}", exc_info=True)

        if websocket.client_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        logger.info(f"WebSocket: 资源清理完毕 (会话ID: {session_id})。")


if __name__ == "__main__":
    logger.info(
        "FastAPI 应用已定义。请使用 Uvicorn 运行，例如: uvicorn src.server.app:app --reload --host 0.0.0.0 --port 8000")