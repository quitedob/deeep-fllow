# 文件路径: src/tools/__init__.py
# -*- coding: utf-8 -*-
# 导出所有可用的工具函数和类。

from typing import List

# 统一从正确的模块导入工具，避免重复和冲突
from src.crawler.crawler import crawl_tool
from .fused_search import fused_search_tool
from .output_generator import OutputGenerator
from .ppt_generator import generate_ppt_from_json
from .python_repl import python_repl_tool
from .search import get_web_search_tool
from .vector_search import add_to_vector_store, vector_search_tool, get_retriever_tool
from ..config.loader import load_yaml_config


def get_tools(tool_names: List[str]) -> list:
    """
    根据名称列表获取工具实例
    简化注释：根据名称获取工具
    """
    tools = []

    # 加载配置以获取默认搜索引擎
    config = load_yaml_config()
    default_engine = config.get("SEARCH_ENGINE", "TAVILY")
    max_results = config.get("max_search_results", 3)

    for name in tool_names:
        if name == "web_search_tool":
            tools.append(get_web_search_tool(engine_name=default_engine, max_search_results=max_results))
        elif name == "crawl_tool":
            tools.append(crawl_tool)
        elif name == "vector_search_tool":
            tools.append(vector_search_tool)
        elif name == "python_repl_tool":
            tools.append(python_repl_tool)

    return tools

# 定义 __all__ 以便清晰地暴露公共 API
# 修复：整理__all__列表，确保所有工具都正确导出且无重复
__all__ = [
    "crawl_tool",
    "fused_search_tool",
    "get_web_search_tool",
    "OutputGenerator",
    "generate_ppt_from_json",
    "python_repl_tool",
    "add_to_vector_store",
    "vector_search_tool",
    "get_retriever_tool",
    "get_tools",
]