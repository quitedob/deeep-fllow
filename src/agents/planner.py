# src/agents/planner.py
# -*- coding: utf-8 -*-
"""
Planner Agent: 接收 state.topic，生成 state.tasks 列表。
"""

import redis
import time
import json
from typing import Dict, Any # Ensure Dict, Any are imported

from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

_pubsub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def planner_agent(state: Dict[str, Any]) -> Dict[str, Any]: # Ensure function name is planner_agent
    session_id = state.get("_session_id", "")
    # Only define channel and publish if session_id is present
    channel = f"channel:session:{session_id}" if session_id else None

    # 发布“START”
    if channel:
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "planner",
            "status": "START",
            "timestamp": int(time.time() * 1000)
        }))

    # … 原有规划逻辑 …
    topic = state.get("topic")
    tasks = [] # Initialize tasks as an empty list

    if not topic:
        # Handle missing topic, tasks remain empty
        # logger.warning(f"Planner agent called for session {session_id} without a topic.")
        pass
    else:
        tasks = [f"Research about {topic}", f"Code for {topic}", f"Report on {topic}"]


    # 发布“COMPLETE”
    if channel:
        _pubsub.publish(channel, json.dumps({
            "session_id": session_id,
            "node": "planner",
            "status": "COMPLETE",
            "timestamp": int(time.time() * 1000)
        }))

    return {"tasks": tasks}
