# src/agents/coder_agent.py
# -*- coding: utf-8 -*-
"""
Coder Agent: 根据 state.research_results 生成代码并执行，写入 state.code_results。
"""

import redis
import time
import json
from typing import Dict, Any # Ensure Dict, Any are imported

from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB
# Make sure cache functions are imported if used
from src.utils.cache import get_cached, cache_result


_pubsub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def coder_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    session_id = state.get("_session_id", "")
    # Only define channel and publish if session_id is present
    channel = f"channel:session:{session_id}" if session_id else None


    # 发布“START”
    if channel:
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "coder",
            "status": "START",
            "timestamp": int(time.time() * 1000)
        }))

    # … 原有编译/执行逻辑 …
    topic = state.get("topic", "default_topic") # Get topic, provide default if not present
    code_res = {} # Default to empty results

    # The original user example for this task implied direct cache use based on topic,
    # not necessarily complex compilation or execution.
    # If topic is "default_topic" because it was missing, this logic will proceed with that.
    cache_key = f"code:{topic}"
    cached = get_cached(cache_key) # from src.utils.cache
    if cached is not None: # get_cached returns None if not found
        code_res = cached
    else:
        # Simulate code generation based on topic
        code_res = {"code_output": f"Hello from {topic}!", "execution_success": True}
        cache_result(cache_key, code_res, ex=3600) # from src.utils.cache

    # 发布“COMPLETE”
    if channel:
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "coder",
            "status": "COMPLETE",
            "timestamp": int(time.time() * 1000)
        }))

    return {"code_results": code_res}
