# -*- coding: utf-8 -*-
# 定义和配置搜索工具

import os
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools.arxiv import ArxivQueryRun
from langchain_community.utilities import ArxivAPIWrapper
from src.tavily_search.tavily_search_results_with_images import TavilySearchResultsWithImages
from .decorators import create_logged_tool

# 创建带日志的搜索工具
LoggedTavilySearch = create_logged_tool(TavilySearchResultsWithImages)
LoggedDuckDuckGoSearch = create_logged_tool(DuckDuckGoSearchResults)
LoggedArxivSearch = create_logged_tool(ArxivQueryRun)


def get_web_search_tool(*, engine_name: str, max_search_results: int):
    """
    获取指定搜索引擎的工具实例。
    - engine_name: 要使用的引擎名称 ("TAVILY", "DUCKDUCKGO", "ARXIV")。
    - max_search_results: 最多返回的搜索结果数量。
    简化注释：获取网络搜索工具
    """
    engine_name_upper = engine_name.upper()

    if engine_name_upper == "TAVILY":
        # 确保 TAVILY_API_KEY 环境变量存在
        if "TAVILY_API_KEY" not in os.environ:
            raise ValueError("使用Tavily搜索引擎需要设置 TAVILY_API_KEY 环境变量。")
        return LoggedTavilySearch(
            name="web_search",
            max_results=max_search_results,
            description="一个可以访问Tavily搜索引擎的工具。当你需要回答关于当前事件的问题时，它非常有用。",
        )
    elif engine_name_upper == "DUCKDUCKGO":
        return LoggedDuckDuckGoSearch(
            name="web_search",
            max_results=max_search_results
        )
    elif engine_name_upper == "ARXIV":
        return LoggedArxivSearch(
            name="web_search",
            api_wrapper=ArxivAPIWrapper(
                top_k_results=max_search_results,
                load_max_docs=max_search_results,
            ),
            description="一个可以搜索arXiv上科学论文的工具。当你需要查找学术研究或前沿科技论文时使用它。"
        )
    else:
        raise ValueError(f"不支持的搜索引擎: {engine_name}")