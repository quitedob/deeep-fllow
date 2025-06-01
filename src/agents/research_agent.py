# src/agents/research_agent.py
# -*- coding: utf-8 -*-
"""
Researcher Agent: 根据 state.tasks 中的具体任务执行检索，并把结果写入 state.research_results。
"""

import redis
import time
import json
from typing import Dict, Any # Ensure Dict, Any are imported

from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB
# Make sure cache functions are imported if used
from src.utils.cache import get_cached, cache_result

_pubsub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def research_agent(state: Dict[str, Any]) -> Dict[str, Any]: # Ensure function name is research_agent
    session_id = state.get("_session_id", "")
    # Only define channel and publish if session_id is present
    channel = f"channel:session:{session_id}" if session_id else None

    # 发布“START”
    if channel:
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "researcher",
            "status": "START",
            "timestamp": int(time.time() * 1000)
        }))

    # … 原有检索逻辑 … （示例用缓存或模拟结果）
    topic = state.get("topic")
    results = [] # Default to empty results

    if not topic:
        # Handle missing topic, results remain empty
        # logger.warning(f"Researcher agent called for session {session_id} without a topic.")
        pass
    else:
        cache_key = f"search:{topic}"
        cached = get_cached(cache_key) # from src.utils.cache
        if cached is not None: # Explicitly check for None, as an empty list/dict from cache could be valid.
            results = cached
        else:
            # Simulate research
            results = [{"title": f"Result 1 for {topic}"}, {"title": f"Result 2 for {topic}"}]
            cache_result(cache_key, results, ex=3600) # from src.utils.cache

    # 发布“COMPLETE”
    if channel:
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "researcher",
            "status": "COMPLETE",
            "timestamp": int(time.time() * 1000)
        }))

    return {"research_results": results}
