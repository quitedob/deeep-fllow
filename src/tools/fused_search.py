# 文件路径: src/tools/fused_search.py
# -*- coding: utf-8 -*-
"""
融合多源检索工具：调用 Tavily、DuckDuckGo、ArXiv、本地向量检索，
合并结果并去重、排序，最终返回统一结构的列表。
"""
from typing import List, Dict
from src.tools.search.tavily import tavily_search
from src.tools.search.duckduckgo import ddg_search
from src.tools.search.arxiv_search import arxiv_search
from src.tools.search.local_vector_search import local_vector_search
import logging # Added for logging

logger = logging.getLogger(__name__) # Added for logging

def fused_search(query: str, top_k: int = 5) -> List[Dict]:
    """
    输入：query（字符串） ； top_k（每个来源返回的最多条数）
    输出：去重后的统一结构检索结果列表，形式如下：
      [
        {
          "title": "...",
          "content": "...",
          "url": "...",
          "score": 0.95,
          "source": "tavily"
        },
        ...
      ]
    """
    results: List[Dict] = []
    logger.info(f"开始融合搜索，查询：'{query}', Top K: {top_k}")

    # 1. 从各个检索模块获取结果
    search_sources = {
        "Tavily": tavily_search,
        "DuckDuckGo": ddg_search,
        "ArXiv": arxiv_search,
        "LocalVector": local_vector_search,
    }

    for source_name, search_func in search_sources.items():
        try:
            logger.debug(f"正在从 {source_name} 检索...")
            source_results = search_func(query, k=top_k)
            if source_results:
                results.extend(source_results)
            logger.debug(f"从 {source_name} 获得 {len(source_results) if source_results else 0} 条结果。")
        except Exception as e:
            logger.error(f"从 {source_name} 检索时发生错误: {e}", exc_info=True)
            pass # 继续尝试其他搜索引擎

    logger.info(f"所有源共获得 {len(results)} 条原始结果。")

    # 2. 简单去重（以 URL 为准）
    seen_urls = set()
    unique_results = []
    if not results: # 如果没有结果，直接返回空列表
        logger.info("没有检索到任何结果。")
        return []

    for item in results:
        if not isinstance(item, dict): # 确保 item 是字典
            logger.warning(f"检索结果中发现非字典类型项目: {item}")
            continue

        url = item.get("url", "")
        # 只有当URL存在且非空时，才进行去重判断；否则直接添加（例如无URL的本地数据）
        if url and url.strip():
            if url not in seen_urls:
                unique_results.append(item)
                seen_urls.add(url)
            else:
                logger.debug(f"发现重复URL，已跳过: {url}")
        else:
            unique_results.append(item) # 保留没有URL或URL为空的结果

    logger.info(f"去重后剩余 {len(unique_results)} 条结果。")

    # 3. 排序（按 score 降序）
    # 确保 score 是数值类型，如果不是或不存在，则默认为0.0以便排序
    unique_results.sort(key=lambda x: x.get("score", 0.0) if isinstance(x.get("score", 0.0), (int, float)) else 0.0, reverse=True)
    logger.debug("结果已按分数排序。")

    # 4. 返回 top_k (此处 top_k 应用于最终的合并列表，而不是每个源的 top_k 之和)
    final_results = unique_results[:top_k]
    logger.info(f"最终返回 {len(final_results)} 条融合搜索结果。")

    return final_results
