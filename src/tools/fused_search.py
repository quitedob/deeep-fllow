# -*- coding: utf-8 -*-
"""
融合检索工具：异步并发调用多个搜索引擎，并对结果进行去重和排序。
"""
import asyncio
import time
import json
from typing import List, Dict, Any, Optional
from .search import get_web_search_tool
from .vector_search import vector_search_tool
from src.config.configuration import Configuration

# 全局缓存
_cache: Dict[str, tuple] = {}


async def _search_runner(engine_name: str, query: str, config: Configuration) -> List[Dict[str, Any]]:
    """
    异步执行单个搜索引擎
    简化注释：异步运行单个搜索
    """
    loop = asyncio.get_event_loop()
    try:
        if engine_name == "RAG":
            # 修复：将config对象传递给向量搜索工具
            return await loop.run_in_executor(
                None,
                lambda: vector_search_tool(query=query, k=config.max_search_results, config=config)
            )

        tool = get_web_search_tool(engine_name=engine_name, max_search_results=config.max_search_results)
        # Langchain工具的run方法是同步的，所以需要在线程池中运行
        result = await loop.run_in_executor(None, tool.run, query)

        # 对不同格式的返回结果进行归一化处理
        if isinstance(result, str):
            try:
                # 尝试解析JSON字符串
                parsed_result = json.loads(result)
                return parsed_result if isinstance(parsed_result, list) else [
                    {"source": engine_name, "content": str(parsed_result)}]
            except json.JSONDecodeError:
                # 如果不是JSON，则视为普通文本
                return [{"source": engine_name, "content": result}]

        return result if isinstance(result, list) else []

    except Exception as e:
        print(f"--- [引擎运行器] 引擎 {engine_name} 异常: {e} ---")
        return []


async def fused_search_tool(query: str, config: Optional[Configuration] = None) -> List[Dict[str, Any]]:
    """
    异步融合检索工具，从配置中读取启用的引擎。
    简化注释：融合检索
    """
    # 修复：接收config对象，如果未提供则加载默认配置
    if config is None:
        config = Configuration.from_runnable_config()

    # 对引擎列表排序，确保缓存键的一致性
    engines_to_run = sorted(config.fused_search_engines or ["TAVILY"])
    cache_key = f"{query}::{','.join(engines_to_run)}::{config.max_search_results}"

    if config.search_cache_ttl > 0 and cache_key in _cache:
        timestamp, cached_results = _cache[cache_key]
        if time.time() - timestamp < config.search_cache_ttl:
            print(f"--- [融合检索] 命中缓存: {query} ---")
            return cached_results

    # 创建并发任务列表
    tasks = [
        _search_runner(engine_name, query, config)
        for engine_name in engines_to_run
    ]

    # 并发执行所有搜索任务
    results_from_all_engines = await asyncio.gather(*tasks, return_exceptions=True)

    unique_results: Dict[str, Dict] = {}
    for i, results in enumerate(results_from_all_engines):
        engine_name = engines_to_run[i]
        if isinstance(results, Exception):
            print(f"--- [融合检索] 引擎 {engine_name} 异常: {results} ---")
            continue

        for res in results:
            if not isinstance(res, dict): continue

            # 使用URL或链接作为去重的key，如果没有则用部分内容
            key_content = res.get("url") or res.get("link") or str(res.get("content", ""))[:100]
            if not key_content:
                continue

            if key_content not in unique_results:
                unique_results[key_content] = {
                    "url": res.get("url") or res.get("link", "N/A"),
                    "content": res.get("content") or res.get("snippet", ""),
                    "source": engine_name
                }

    final_list = list(unique_results.values())

    # 如果启用了缓存，则存入结果
    if config.search_cache_ttl > 0:
        _cache[cache_key] = (time.time(), final_list)

    print(f"--- [融合检索] 完成，共找到 {len(final_list)} 条不重复结果 ---")
    return final_list