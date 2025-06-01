# FilePath: src/tools/fused_search.py
# -*- coding: utf-8 -*-
"""
Multi-engine fused search tool: Unifies results from Tavily / DuckDuckGo / Arxiv / local vector store
into a List[Dict], deduplicates, and scores them.
"""
from typing import List, Dict
from .search.tavily import tavily_search   # Assuming existing wrapper
from .search.duckduckgo import ddg_search
from .search.arxiv_search import arxiv_search
from .retriever_tool import local_vector_search

def fused_search(query: str, top_k: int = 10) -> List[Dict]:
    """Fuses multi-source search results and returns a unified structure."""
    results: List[Dict] = []
    # 1) Retrieve from each engine
    try:
        results.extend(tavily_search(query, k=top_k))
    except Exception as e:
        print(f"Error in tavily_search: {e}")
    try:
        results.extend(ddg_search(query, k=top_k))
    except Exception as e:
        print(f"Error in ddg_search: {e}")
    try:
        results.extend(arxiv_search(query, k=top_k))
    except Exception as e:
        print(f"Error in arxiv_search: {e}")
    try:
        results.extend(local_vector_search(query, k=top_k))
    except Exception as e:
        print(f"Error in local_vector_search: {e}")

    # 2) Simple deduplication (by URL)
    seen_urls = set()
    unique_results = []
    for r in results:
        url = r.get("url")
        if url: # Only consider results with a URL for deduplication
            if url not in seen_urls:
                unique_results.append(r)
                seen_urls.add(url)
        else: # Keep results without URLs as they are (e.g. local data)
            unique_results.append(r)

    # 3) Scoring and sorting: Simple sort by 'score' if present, otherwise keep order.
    #    More sophisticated scoring could consider source reliability, recency, etc.
    #    For now, if 'score' is missing, treat as 0 for sorting purposes.
    unique_results.sort(key=lambda x: x.get("score", 0.0) if isinstance(x.get("score"), (int, float)) else 0.0, reverse=True)

    return unique_results[:top_k]
