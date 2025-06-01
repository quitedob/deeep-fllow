# src/workers/session_worker.py
# -*- coding: utf-8 -*-

import json
import time
import logging
from typing import Optional, Dict, Any # Ensure these are imported

import redis

# 引入我们在 builder.py 中实现的 run_langgraph
from src.graph.builder import run_langgraph

# 从 cache.py 导入用于检查已有状态的函数
# User's snippet included delete_state_sharded, but it's not used in the worker logic they provided.
# Keeping it for now as per their import list.
from src.utils.cache import get_state_sharded, delete_state_sharded

# 引入配置
from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

# 日志初始化（可自定义为写入文件worker.log）
# Check if a logger named 'worker' or similar is already configured elsewhere to avoid conflicts.
# For now, applying as specified.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("worker.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 全局 Redis 客户端
_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)

def consume_queue(block: bool = True, timeout: int = 5) -> Optional[Dict[str, str]]:
    """
    从 Redis 列表 'queue:session_tasks' 中取出一条任务：
    - 如果 block=True，则使用 BRPOP 阻塞等待；timeout 为阻塞时长（秒）。
    - 返回的 dict 格式：{"session_id": "...", "topic": "..."}；若队列空或超时，返回 None。
    """
    if block:
        result = _redis.brpop("queue:session_tasks", timeout=timeout)
        if not result:
            return None
        # result 格式：(list_name_bytes, json_string_bytes) if decode_responses=False
        # result 格式：(list_name_str, json_string_str) if decode_responses=True
        _, data = result
    else:
        data = _redis.rpop("queue:session_tasks")
        if not data:
            return None

    try:
        task = json.loads(data)
        session_id = task.get("session_id")
        topic = task.get("topic")
        if not session_id or not topic: # Ensure both are present
            logger.warning(f"从队列获取到无效任务数据：{data}")
            return None
        return {"session_id": session_id, "topic": topic}
    except json.JSONDecodeError:
        logger.error(f"任务数据 JSON 解析失败：{data}", exc_info=True) # Added exc_info
        return None

def has_completed(session_id: str) -> bool:
    """
    检查该 session_id 是否已有 final result（report_paths 或 error）。
    如果存在 report_paths，说明报告已生成；如果 error 字段，说明之前执行已出错。
    返回 True 表示跳过，不再重复执行。
    """
    state = get_state_sharded(session_id) # Assumes use_sharded=True for worker checks
    if not state:
        return False
    # 如果已经有 report_paths 或 audio_path，也当作已完成
    # Also checking for 'error' field as per user's description
    if state.get("report_paths") or state.get("audio_path") or state.get("error"):
        return True
    return False

def session_worker_loop():
    """
    后台 Worker 主循环：
    1. 不断从 Redis 队列中取任务。
    2. 对每一个 task：检查是否已执行过，若无，调用 run_langgraph 执行。
    3. 捕获 run_langgraph 的结果或异常，在日志中写入，并继续循环。
    """
    logger.info("Session Worker 已启动，开始监听 queue:session_tasks ...")
    while True:
        try:
            task = consume_queue(block=True, timeout=10) # User specified 10s timeout
            if not task:
                time.sleep(0.5) # As per user's loop example
                continue

            session_id = task["session_id"]
            topic = task["topic"]
            logger.info(f"[Worker] 收到任务：session_id={session_id}, topic={topic}")

            if has_completed(session_id):
                logger.info(f"[Worker] 会话 {session_id} 已完成或曾出错，跳过执行。") # Clarified log
                continue

            result = run_langgraph({"topic": topic}, session_id=session_id, use_sharded=True)

            if result.get("error"):
                logger.error(f"[Worker] session_id={session_id} 执行出错（由 run_langgraph报告）：{result['error']}")
            else:
                logger.info(f"[Worker] session_id={session_id} 执行完成（由 run_langgraph报告），继续等待下一个任务。")

        except Exception as exc:
            logger.exception(f"[Worker] session_worker_loop 出现未处理异常：{exc}")
            time.sleep(5)

def main():
    """
    入口：启动 Worker 主循环。
    """
    try:
        session_worker_loop()
    except KeyboardInterrupt:
        logger.info("Session Worker 收到 KeyboardInterrupt，准备退出。")
    except Exception as exc:
        logger.exception(f"Session Worker 致命错误，退出：{exc}")

if __name__ == "__main__":
    main()
