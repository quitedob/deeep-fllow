# 文件路径: src/tools/search/duckduckgo.py
# -*- coding: utf-8 -*-
"""
DuckDuckGo 网页检索示例。
使用 duckduckgo_search Python 库。
"""
from typing import List, Dict, Any # Ensure List, Dict, Any are imported
import logging

logger = logging.getLogger(__name__)

try:
    from duckduckgo_search import DDGS # Use the new DDGS class
except ImportError:
    logger.error("duckduckgo_search 库未安装。请运行 'pip install duckduckgo_search'。")
    # Define a dummy DDGS so the rest of the file can be parsed,
    # but it will effectively disable DDG search if the import fails.
    class DDGS: # type: ignore
        def __init__(self, headers=None, proxies=None, timeout=None):
            pass
        def text(self, query, region='wt-wt', safesearch='moderate', timelimit=None, max_results=None):
            logger.warning("duckduckgo_search 库未正确导入，DDG 搜索将返回空结果。")
            return []

def ddg_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    使用 duckduckgo_search 库执行搜索。
    示例返回格式：
    [
      {"title": "...", "content": "...", "url": "...", "score": 0.0, "source": "duckduckgo"},
      ...
    ]
    """
    logger.info(f"开始 DuckDuckGo 搜索，查询: '{query}', 最大结果数: {k}")

    results: List[Dict[str, Any]] = []

    # Check if the DDGS class was properly imported or is the dummy
    if DDGS.__module__ == __name__ and DDGS.__name__ == 'DDGS': # This checks if it's our dummy
        logger.warning("由于 duckduckgo_search 库未加载，DuckDuckGo 搜索跳过。")
        return []

    try:
        # DDGS().text() returns a list of dictionaries
        # The library handles making requests internally
        with DDGS(timeout=10) as ddgs: # timeout can be specified
            search_results = ddgs.text(
                keywords=query,
                region='wt-wt',       # World Wide
                safesearch='moderate',
                max_results=k
            )

        if search_results:
            for item in search_results:
                results.append({
                    "title": item.get("title", "无标题"),
                    "content": item.get("body", "无内容"), # 'body' usually contains the snippet
                    "url": item.get("href", ""),      # 'href' is the URL
                    "score": 0.0, # DDG search library doesn't typically provide a relevance score directly
                    "source": "duckduckgo"
                })
            logger.info(f"DuckDuckGo 搜索返回 {len(results)} 条结果。")
        else:
            logger.info("DuckDuckGo 搜索没有返回结果。")

        return results
    except Exception as e:
        logger.error(f"DuckDuckGo 搜索过程中发生错误: {e}", exc_info=True)
        return []
