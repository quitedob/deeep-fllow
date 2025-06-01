# 文件路径: src/utils/lock.py
# -*- coding: utf-8 -*-
"""
提供基于 Redis 的分布式锁封装，确保同一个 session_id 同一时刻只有一个执行流。
"""
import redis
import uuid
import time
from typing import Optional
from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

# 全局 Redis 连接
_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    return _redis_client

def acquire_lock(session_id: str, timeout: int = 10, wait: int = 5) -> Optional[str]:
    """
    尝试获取针对 session_id 的锁，获取不到则等待最多 wait 秒。获取成功返回 lock_id，否则返回 None。
    - timeout: 锁自动过期时间，避免死锁
    - wait: 最大等待时间
    """
    client = get_redis_client()
    lock_key = f"lock:session:{session_id}"
    lock_id = str(uuid.uuid4())
    deadline = time.time() + wait
    while time.time() < deadline:
        if client.set(lock_key, lock_id, nx=True, ex=timeout):
            return lock_id
        time.sleep(0.05) # User specified 0.05 in their final lock.py
    return None

def release_lock(session_id: str, lock_id: str) -> bool:
    """
    仅当 key 对应的值等于 lock_id 时才删除锁，保证不会误释放别人的锁。
    使用 Lua 脚本实现原子性。
    """
    client = get_redis_client()
    lock_key = f"lock:session:{session_id}"
    lua = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """
    try:
        result = client.eval(lua, 1, lock_key, lock_id)
        return result == 1
    except redis.RedisError: # Catch generic RedisError as per user's spec
        # In a real app, log this error
        # logger.error(f"Redis error during lock release for {session_id}: {e}", exc_info=True)
        return False
