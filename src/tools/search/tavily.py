# 文件路径: src/tools/search/tavily.py
# -*- coding: utf-8 -*-
"""
Tavily 多模态检索示例占位。
真实环境中，需要替换为官方 API 调用并传入 API Key。
"""
import os
import requests
import logging
from typing import List, Dict, Any # Ensure List, Dict, Any are imported

logger = logging.getLogger(__name__)

def tavily_search(query: str, k: int = 5) -> List[Dict[str, Any]]:
    """
    示例返回格式：
    [
      {"title": "...", "content": "...", "url": "...", "score": 0.9, "source": "tavily"},
      ...
    ]
    """
    api_key = os.getenv("TAVILY_API_KEY") # Removed default empty string to make missing key more explicit
    if not api_key:
        logger.warning("TAVILY_API_KEY 环境变量未设置。Tavily 搜索将返回空结果。")
        return []

    # 示例接口，需替换为实际 endpoint 和请求结构
    # Tavily API endpoint for basic search. Advanced search might have a different one.
    endpoint = "https://api.tavily.com/search"

    # Payload structure for Tavily API (example, may need adjustment based on actual API docs)
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic", # "basic" or "advanced"
        "max_results": k,
        # "include_domains": [],
        # "exclude_domains": [],
        # "include_answer": False, # Whether to include a short answer from LLM model
        # "include_raw_content": False, # Whether to include raw content of webpages
        # "include_images": False, # Whether to include image results (if supported by endpoint)
    }

    headers = {
        "Content-Type": "application/json"
    }

    logger.info(f"向 Tavily API 发送查询: '{query}', 最大结果数: {k}")

    try:
        # Tavily uses POST for search requests
        resp = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()  # 如果请求失败 (4xx or 5xx)，则抛出 HTTPError

        data = resp.json()
        results: List[Dict[str, Any]] = []

        # Adjust parsing based on actual Tavily API response structure
        # Common fields are 'title', 'url', 'content' (snippet/summary), 'score'
        api_results = data.get("results", []) # 'results' is a common key for search result lists
        if not api_results and "answer" in data: # If no results but there is an answer
             logger.info(f"Tavily 返回了一个直接答案: {data['answer']}")
             # You might want to format this answer as a result item
             # results.append({"title": "Tavily Answer", "content": data['answer'], "url": "", "score": 1.0, "source": "tavily_answer"})


        for item in api_results:
            results.append({
                "title": item.get("title", "无标题"),
                "content": item.get("content", item.get("snippet", "无内容")), # Use 'snippet' if 'content' is not available
                "url": item.get("url", ""),
                "score": item.get("score", 0.0), # Tavily provides a score
                "source": "tavily"
            })
        logger.info(f"Tavily API 返回 {len(results)} 条结果。")
        return results
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"Tavily API 请求失败 (HTTP错误): {http_err} - 响应内容: {resp.text}", exc_info=True)
        return []
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Tavily API 请求失败 (网络或其他请求错误): {req_err}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"处理 Tavily 搜索结果时发生未知错误: {e}", exc_info=True)
        return []
