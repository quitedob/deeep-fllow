# 文件路径: src/server/app.py
# -*- coding: utf-8 -*-
"""
FastAPI 服务：提供 HTTP/REST 和 WebSocket 接口
Phase 1 requirements:
1. 所有接口必须校验 X-API-KEY
2. 提供 /api/start, /api/status/{session_id}, /api/get_report/{session_id}, /api/get_audio/{session_id}
3. 提供 /ws/{session_id} WebSocket 用于实时推送进度
4. 提供 /api/reset/{session_id}
"""

import os
import json
import logging
import uuid # For generating session_id if not provided in /api/start
import time # For WebSocket, though not directly used in this version of forward_messages
import threading # For WebSocket background thread
import asyncio # Required for run_coroutine_threadsafe

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field # For request body validation
from typing import Optional, Dict, Any
from starlette.websockets import WebSocketState # Correct import for WebSocketState


import redis # For PubSub client in WebSocket

# Assuming these are the correct paths based on current project structure
from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB, API_KEYS
from src.graph.builder import run_langgraph, get_existing_state, reset_session
# enqueue_session is now part of run_langgraph via _enqueue flag.
# If direct enqueue is needed, it would be from src.utils.cache
from src.utils.cache import enqueue_session # Explicitly import for /api/start if direct enqueue is preferred
from src.utils.logging import init_logger


# 初始化日志
init_logger("INFO") # Ensure logging is configured
logger = logging.getLogger(__name__)

# Redis 用于 Pub/Sub
_redis_pubsub_client = None

def get_redis_pubsub_client():
    global _redis_pubsub_client
    if _redis_pubsub_client is None:
        _redis_pubsub_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return _redis_pubsub_client

app = FastAPI(title="DeerFlow 带记忆服务 (Phase 1)", version="1.0.0")

# --- 权限校验依赖注入 ---
async def verify_api_key(x_api_key: str = Header(None)): # Changed to Header(None) for better error handling
    """
    从 Header 中获取 X-API-KEY，校验合法性。如果不合法抛出 401。
    """
    if not x_api_key:
        logger.warning("Missing X-API-KEY header.")
        raise HTTPException(status_code=401, detail="X-API-KEY header missing")
    if x_api_key not in API_KEYS:
        logger.warning(f"非法 API Key: {x_api_key}")
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid API Key")
    return x_api_key

# --- Request Models ---
class StartRequest(BaseModel):
    topic: str
    session_id: Optional[str] = None
    # use_sharded: bool = True # This could be a query param or part of payload if needed for run_now

class RunNowRequest(BaseModel):
    topic: str
    session_id: Optional[str] = None
    use_sharded: bool = True
    initial_state: Optional[Dict[str, Any]] = None # Allow passing full initial state


# --- API Endpoints ---

@app.post("/api/start", dependencies=[Depends(verify_api_key)])
async def api_start(payload: StartRequest) -> Dict[str, Any]:
    """
    异步启动流程：将任务入队。
    请求示例：{ "topic": "某个主题", "session_id": "可选" }
    返回：{ "_session_id": "...", "message": "任务已入队，稍后执行" }
    """
    sid = payload.session_id if payload.session_id else str(uuid.uuid4())

    # Option 1: Use run_langgraph with _enqueue flag
    # This assumes run_langgraph is adapted to handle initial_state construction for enqueue if only topic is given
    initial_state_for_enqueue = {"topic": payload.topic, "_enqueue": True}
    # run_langgraph itself will generate session_id if payload.session_id is None and passed as None to it
    # However, we want to return the sid consistently, so generate/use it here.
    result = run_langgraph(initial_state_for_enqueue, session_id=sid) # use_sharded is not relevant for enqueue

    # Option 2: Direct call to enqueue_session (simpler if run_langgraph's enqueue is just a passthrough)
    # enqueue_session(sid, payload.topic)
    # result = {"_session_id": sid, "message": "任务已入队，稍后执行"}

    if "error" in result:
        # This might happen if topic is missing and run_langgraph's enqueue validation catches it.
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/run_now", dependencies=[Depends(verify_api_key)])
async def api_run_now(payload: RunNowRequest) -> Dict[str, Any]:
    """
    同步执行带记忆流程。
    请求示例：{ "topic": "某主题", "session_id": "可选", "use_sharded": true, "initial_state": { ... } }
    返回最终状态（阻塞直到执行完成）。
    """
    # Prepare initial_state for run_langgraph. If payload.initial_state is provided, use it.
    # Otherwise, construct from topic.
    effective_initial_state = payload.initial_state if payload.initial_state else {}
    if "topic" not in effective_initial_state and payload.topic:
         effective_initial_state["topic"] = payload.topic

    if not effective_initial_state.get("topic"):
         raise HTTPException(status_code=400, detail="Topic is required either in 'topic' field or within 'initial_state'")

    result = run_langgraph(
        initial_state=effective_initial_state,
        session_id=payload.session_id,
        use_sharded=payload.use_sharded
    )
    if "error" in result:
        # Distinguish between client errors (e.g., bad input) and server errors (e.g., lock timeout)
        # For now, just return 500 if an error field is present, assuming it's a processing error.
        # Lock error from run_langgraph already returns a specific structure.
        if result["error"] == "会话正在执行，请稍后再试":
            raise HTTPException(status_code=429, detail=result["error"]) # Too Many Requests / Locked
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@app.get("/api/status/{session_id}", dependencies=[Depends(verify_api_key)])
async def api_status(session_id: str) -> Dict[str, Any]:
    """
    返回指定 session_id 的当前状态，如果不存在则返回 404。
    Defaulting to use_sharded=True as per user's run_langgraph spec.
    """
    state = get_existing_state(session_id, use_sharded=True)
    if not state:
        raise HTTPException(status_code=404, detail="会话未找到或已过期")
    return state

@app.get("/api/get_report/{session_id}", dependencies=[Depends(verify_api_key)])
async def api_get_report(session_id: str) -> Dict[str, Any]:
    """
    返回该 session_id 生成的报告的存储路径。
    """
    state = get_existing_state(session_id, use_sharded=True)
    if not state:
        raise HTTPException(status_code=404, detail="会话未找到")
    report_paths = state.get("report_paths")
    if report_paths is None: # Check for None explicitly, as empty dict {} is a valid but empty result
        return {"message": "报告尚未生成或无报告信息", "report_paths": {}}
    return {"report_paths": report_paths}


@app.get("/api/get_audio/{session_id}", dependencies=[Depends(verify_api_key)])
async def api_get_audio(session_id: str) -> Dict[str, Any]:
    """
    返回该 session_id 生成的音频文件路径。
    """
    state = get_existing_state(session_id, use_sharded=True)
    if not state:
        raise HTTPException(status_code=404, detail="会话未找到")
    audio_path = state.get("audio_path")
    if audio_path is None: # Check for None explicitly
        return {"message": "音频尚未生成或无音频路径", "audio_path": None}
    return {"audio_path": audio_path}

@app.delete("/api/reset/{session_id}", dependencies=[Depends(verify_api_key)])
async def api_reset(session_id: str) -> Dict[str, str]:
    """
    删除指定会话的所有缓存状态。
    """
    reset_session(session_id, use_sharded=True) # Defaulting to sharded as per user spec for run_langgraph
    return {"message": f"会话 {session_id} 已重置"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, x_api_key: str = Header(None)):
    """
    WebSocket 端点：客户端需带 X-API-KEY，连接后订阅 Redis Pub/Sub 频道 "channel:session:{session_id}"，
    并把收到的消息转发给客户端。
    """
    # API Key Verification for WebSocket
    if not x_api_key:
        await websocket.close(code=1008, reason="X-API-KEY header missing")
        return
    if x_api_key not in API_KEYS:
        await websocket.close(code=1008, reason="Unauthorized: Invalid API Key")
        return

    await websocket.accept()

    redis_cli = get_redis_pubsub_client()
    pubsub = redis_cli.pubsub(ignore_subscribe_messages=True)
    channel = f"channel:session:{session_id}"

    stop_event = threading.Event()
    loop = asyncio.get_event_loop() # Get the current event loop for the main thread

    def forward_messages():
        try:
            pubsub.subscribe(channel)
            logger.info(f"WebSocket subscribed to {channel}")
            for message in pubsub.listen():
                if stop_event.is_set():
                    break
                if message and message.get("type") == "message":
                    try:
                        # Ensure websocket is still open before sending
                        if websocket.client_state == WebSocketState.CONNECTED: # Use imported WebSocketState
                           asyncio.run_coroutine_threadsafe(websocket.send_text(message["data"]), loop)
                        else:
                            logger.warning(f"WebSocket no longer connected for {session_id}, stopping listener.")
                            break
                    except Exception as e_ws_send:
                        logger.error(f"Error sending message to WebSocket for {session_id}: {e_ws_send}")
                        break
        except redis.exceptions.ConnectionError as e_redis:
            logger.error(f"Redis connection error in WebSocket listener for {session_id}: {e_redis}")
        except Exception as e_outer:
            logger.error(f"Outer exception in WebSocket listener for {session_id}: {e_outer}")
        finally:
            logger.info(f"Unsubscribing WebSocket from {channel}")
            if pubsub.subscribed:
                try:
                    pubsub.unsubscribe(channel)
                    pubsub.close()
                except Exception as e_unsub:
                    logger.error(f"Error during pubsub unsubscribe/close for {session_id}: {e_unsub}")

    listener_thread = threading.Thread(target=forward_messages, daemon=True)
    listener_thread.start()

    try:
        while True:
            data = await websocket.receive_text()
            # logger.debug(f"Received from client for {session_id}: {data}") # Optional: log client messages
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for {session_id}")
    except Exception as e_main_ws:
        logger.error(f"Exception in main WebSocket loop for {session_id}: {e_main_ws}")
    finally:
        logger.info(f"Stopping listener thread for {session_id}...")
        stop_event.set()
        listener_thread.join(timeout=5)
        if listener_thread.is_alive():
            logger.warning(f"Listener thread for {session_id} did not stop in time.")
        if websocket.client_state != WebSocketState.DISCONNECTED: # Use imported WebSocketState
            await websocket.close()
        logger.info(f"WebSocket resources cleaned up for {session_id}")

if __name__ == "__main__":
    logger.info("FastAPI app defined. Run with Uvicorn: uvicorn src.server.app:app --reload --host 0.0.0.0 --port 8000")
