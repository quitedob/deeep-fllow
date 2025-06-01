# 文件路径: src/utils/cache.py
# -*- coding: utf-8 -*-
"""
Redis 客户端封装：支持多种存储方案，包括分片存储、队列、缓存等。
新增告警状态管理功能。
"""

import redis
import json
from typing import Any, Optional, Dict
from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

# 全局 Redis 客户端
_redis_client = None


def get_redis_client():
    """获取Redis客户端单例"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return _redis_client


# --- 单 Key 存储（过期时间：24 小时）---
def set_state(session_id: str, state: Dict[str, Any], ex: int = 86400) -> None:
    """将整个 state 字典以 JSON 存储到 Redis"""
    client = get_redis_client()
    key = f"state:{session_id}"
    client.set(key, json.dumps(state), ex=ex)


def get_state(session_id: str) -> Optional[Dict[str, Any]]:
    """从 Redis 读取整个 state 并刷新 TTL"""
    client = get_redis_client()
    key = f"state:{session_id}"
    data = client.get(key)
    if data:
        client.expire(key, 86400)  # 刷新 TTL
        return json.loads(data)
    return None


def delete_state(session_id: str) -> None:
    """删除指定 session_id 对应的状态"""
    client = get_redis_client()
    key = f"state:{session_id}"
    client.delete(key)


# --- 分片存储（针对大状态）---
def set_state_sharded(session_id: str, state: Dict[str, Any], ex: int = 86400) -> None:
    """将 state 中的大字段拆分存储"""
    client = get_redis_client()
    base = {
        "topic": state.get("topic"),
        "tasks": state.get("tasks"),
        "report_paths": state.get("report_paths"),
        "audio_path": state.get("audio_path"),
        "_session_id": state.get("_session_id"),
        "error": state.get("error")
    }
    research = state.get("research_results", {})
    code = state.get("code_results", {})

    client.set(f"state:{session_id}:base", json.dumps(base), ex=ex)
    client.set(f"state:{session_id}:research", json.dumps(research), ex=ex)
    client.set(f"state:{session_id}:code", json.dumps(code), ex=ex)


def get_state_sharded(session_id: str) -> Optional[Dict[str, Any]]:
    """从分片 Key 中读取各部分数据，并合并成一个完整 state"""
    client = get_redis_client()
    key_base = f"state:{session_id}:base"
    data_base = client.get(key_base)
    if data_base is None:
        return None

    base = json.loads(data_base)
    key_research = f"state:{session_id}:research"
    key_code = f"state:{session_id}:code"

    research_data = client.get(key_research)
    code_data = client.get(key_code)

    research = json.loads(research_data) if research_data is not None else {}
    code = json.loads(code_data) if code_data is not None else {}

    client.expire(key_base, 86400)
    if research_data is not None:
        client.expire(key_research, 86400)
    if code_data is not None:
        client.expire(key_code, 86400)

    merged = {**base, "research_results": research, "code_results": code}
    return merged


def delete_state_sharded(session_id: str) -> None:
    """删除分片存储的所有 Key"""
    client = get_redis_client()
    client.delete(f"state:{session_id}:base", f"state:{session_id}:research", f"state:{session_id}:code")


# --- 任务队列（Redis List）---
QUEUE_NAME = "queue:session_tasks"


def enqueue_session(session_id: str, topic: str) -> None:
    """将 session 任务放到 Redis 列表"""
    client = get_redis_client()
    item = json.dumps({"session_id": session_id, "topic": topic})
    client.lpush(QUEUE_NAME, item)


def dequeue_session(block: bool = True, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """从 Redis 列表取出一个任务"""
    client = get_redis_client()
    data = None
    if block:
        result = client.brpop(QUEUE_NAME, timeout=timeout)
        if result:
            _, data = result
    else:
        data = client.rpop(QUEUE_NAME)

    if data:
        return json.loads(data)
    return None


# --- 二级缓存（用于中间结果）---
def cache_result(cache_key: str, value: Any, ex: int = 3600) -> None:
    """缓存某个中间结果，默认过期时间 1 小时"""
    client = get_redis_client()
    client.set(cache_key, json.dumps(value), ex=ex)


def get_cached(cache_key: str) -> Optional[Any]:
    """读取二级缓存"""
    client = get_redis_client()
    data = client.get(cache_key)
    if data:
        return json.loads(data)
    return None


# --- 告警状态管理 (优化点) ---
def get_alert_state(alert_type: str) -> Optional[str]:
    """
    获取指定告警类型的当前状态 ("NORMAL" 或 "ALERTING")
    简化注释：获取告警状态
    """
    client = get_redis_client()
    key = f"alert:state:{alert_type}"
    state = client.get(key)
    return state  # 返回 "NORMAL", "ALERTING", 或 None


def set_alert_state(alert_type: str, state: str, ex: int) -> None:
    """
    设置指定告警类型的状态，并附加过期时间
    简化注释：设置告警状态
    """
    client = get_redis_client()
    key = f"alert:state:{alert_type}"
    client.set(key, state, ex=ex)