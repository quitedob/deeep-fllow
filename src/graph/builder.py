# src/graph/builder.py
# -*- coding: utf-8 -*-
"""
带记忆的 Graph 引擎：run_langgraph() 集成分布式锁、Pub/Sub、持久化、异常处理。
"""

import os
import json
import logging
import time
import uuid # Ensure uuid is imported
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from src.utils.logging import init_logger
from src.utils.cache import (
    get_state_sharded, set_state_sharded, delete_state_sharded, # For clarity, keep both sets of imports
    get_state, set_state, delete_state # Even if only one set is chosen by use_sharded
)
from src.utils.lock import acquire_lock, release_lock
from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

import redis

# 初始化日志
init_logger("INFO") # Ensure this is called
logger = logging.getLogger(__name__)

# Pub/Sub 客户端（发布“全流程 START/COMPLETE/ERROR”）
_pubsub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

# StateSchema 定义
class StateSchema(TypedDict, total=False):
    topic: str
    tasks: list[str]
    research_results: dict
    code_results: dict
    report_paths: dict
    audio_path: str
    error: Optional[str]  # 用于存储异常信息. Changed to Optional[str]
    _session_id: Optional[str] # Ensure _session_id is in schema for agents

def build_graph() -> StateGraph:
    """
    读取 langgraph.json 并注册节点至 StateGraph，不含持久化/插件逻辑。
    """
    try:
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except NameError:
        base_path = os.getcwd()

    lg_path = os.path.join(base_path, "langgraph.json")

    if not os.path.exists(lg_path):
        logger.error(f"langgraph.json 未找到，预期路径: {lg_path}")
        raise FileNotFoundError(f"langgraph.json 未找到，预期路径: {lg_path}")

    with open(lg_path, "r", encoding="utf-8") as f:
        graph_def = json.load(f)

    graph = StateGraph(StateSchema)
    for node_name, node_info in graph_def.get("nodes", {}).items():
        module_path = node_info.get("module", "")
        func_name   = node_info.get("func", "")
        if not module_path.startswith("src."):
            module_path = f"src.{module_path}"
        comps = module_path.split(".")
        try:
            mod = __import__(module_path, fromlist=[comps[-1]])
            func = getattr(mod, func_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"无法导入节点 {module_path}.{func_name}: {e}", exc_info=True)
            raise

        graph.add_node(node_name, func)
        logger.info(f"已注册节点 '{node_name}' -> {module_path}.{func_name}")

    for edge in graph_def.get("edges", []):
        from_node = edge.get("from")
        to_node   = edge.get("to")
        graph.add_edge(from_node, to_node)
        logger.info(f"已连接边 '{from_node}' -> '{to_node}'")

    graph.set_entry_point("planner")
    graph.add_edge("voice", END)
    logger.info("StateGraph 构建完成（无记忆模式）。")
    return graph

def build_graph_with_memory() -> StateGraph:
    """
    带记忆模式下的 Graph 构建：目前直接调用 build_graph()。
    """
    graph = build_graph()
    logger.info("带记忆模式：Graph 已就绪（build_graph_with_memory）。")
    return graph

# Helper to choose state functions based on use_sharded flag
def _get_state_persister(use_sharded: bool):
    if use_sharded:
        return get_state_sharded, set_state_sharded, delete_state_sharded
    else:
        return get_state, set_state, delete_state

def run_langgraph(initial_state: Dict[str, Any],
                  session_id: Optional[str] = None,
                  use_sharded: bool = True) -> Dict[str, Any]:
    """
    带记忆流程入口，集成锁、Pub/Sub、持久化、异常处理。
    """
    get_state_func, set_state_func, _ = _get_state_persister(use_sharded)

    current_state: StateSchema

    # — Step 1: Session Management —
    if session_id:
        loaded_s = get_state_func(session_id)
        current_state = loaded_s if loaded_s is not None else {} # type: ignore
        logger.info(f"[Session={session_id}] 已加载状态：{bool(current_state)}")
    else:
        session_id = str(uuid.uuid4())
        current_state = {} # type: ignore
        logger.info(f"[Session={session_id}] 新会话已创建")

    current_state.update(initial_state)
    current_state["_session_id"] = session_id

    # — Step 2: Acquire Distributed Lock —
    lock_id = acquire_lock(session_id, timeout=30, wait=10)
    if not lock_id:
        logger.warning(f"[Session={session_id}] 获取锁失败 => 已有执行中")
        return {"_session_id": session_id, "error": "会话正在执行，请稍后重试"}

    channel = f"channel:session:{session_id}"

    try:
        # — Step 3: Ensure topic present —
        if "topic" not in current_state or not current_state.get("topic"):
            raise ValueError("缺少 'topic'，无法继续执行")

        # — Step 4: Publish “ALL START” —
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "ALL",
            "status": "START",
            "timestamp": int(time.time() * 1000)
        }))

        # — Step 5: Build & Invoke Graph —
        graph = build_graph_with_memory()
        runnable = graph.compile()

        final_state: StateSchema = runnable.invoke(current_state) # type: ignore

        # — Step 5.1: Publish “ALL COMPLETE” —
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "ALL",
            "status": "COMPLETE",
            "timestamp": int(time.time() * 1000)
        }))

        # — Step 6: Persist state to Redis —
        set_state_func(session_id, final_state)
        logger.info(f"[Session={session_id}] 状态已持久化（use_sharded={use_sharded}）")

        # — Step 7: Return result —
        response = dict(final_state)
        if "_session_id" not in response:
             response["_session_id"] = session_id
        return response

    except Exception as ex:
        logger.error(f"[Session={session_id}] 执行异常：{ex}", exc_info=True)
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "ALL",
            "status": "ERROR",
            "error": str(ex),
            "timestamp": int(time.time() * 1000)
        }))
        current_state_with_error = current_state.copy()
        current_state_with_error["error"] = str(ex)
        set_state_func(session_id, current_state_with_error) # type: ignore

        return {"_session_id": session_id, "error": str(ex)}

    finally:
        # Step 8: Release Lock
        if lock_id:
            released = release_lock(session_id, lock_id)
            if released:
                logger.info(f"[Session={session_id}] 锁已释放")
            else:
                logger.warning(f"[Session={session_id}] 锁释放失败或已超时")

def get_existing_state(session_id: str, use_sharded: bool = True) -> Optional[Dict[str, Any]]:
    get_state_func, _, _ = _get_state_persister(use_sharded)
    return get_state_func(session_id)

def reset_session(session_id: str, use_sharded: bool = True) -> None:
    _, _, delete_state_func = _get_state_persister(use_sharded)
    delete_state_func(session_id)
    logger.info(f"会话 {session_id} (sharded={use_sharded}) 已重置。")
