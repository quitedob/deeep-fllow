# 文件路径: src/config/settings.py
# -*- coding: utf-8 -*-
"""
从环境变量加载配置。
这个文件用于存放敏感信息（如API Key）或经常变化的配置，与 `configuration.py` 中的静态配置分离。
"""

import os
from dotenv import load_dotenv
from enum import Enum
from .loader import load_yaml_config

# 加载项目根目录下的 .env 文件中的环境变量
# 修复：确保能正确找到.env文件
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

# --- 新增：搜索引擎枚举 ---
class SearchEngine(Enum):
    """定义支持的搜索引擎"""
    TAVILY = "TAVILY"
    DUCKDUCKGO = "DUCKDUCKGO"
    ARXIV = "ARXIV"
    RAG = "RAG"

# --- 模型与API配置 ---

# API Key
# 简化注释：从环境变量读取 DeepSeek API Key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# API Base URL
# 简化注释：允许自定义 DeepSeek API 的接入点
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

# 默认使用的模型名称 (此处的设置可以被 conf.yaml 覆盖)
# 简化注释：默认对话模型
DEFAULT_CHAT_MODEL = os.getenv("DEFAULT_CHAT_MODEL", "deepseek-chat")
# 简化注释：默认推理模型
REASONING_MODEL = os.getenv("REASONING_MODEL", "deepseek-coder")


# --- 搜索配置 ---
# 从 YAML 配置中读取默认搜索引擎
_conf_yaml_path = os.path.join(os.path.dirname(__file__), '..', '..', 'conf.yaml')
_config_from_yaml = load_yaml_config(_conf_yaml_path)
# 修复：确保即使 yaml 文件中没有 search_engine 也能正常工作
_default_search_engine_from_yaml = _config_from_yaml.get('search_engine', "TAVILY")
# 优先使用环境变量，否则使用YAML配置，最后使用硬编码默认值
DEFAULT_SEARCH_ENGINE = os.getenv("SEARCH_ENGINE", _default_search_engine_from_yaml).upper()
# 定义一个常量，以供 background_investigation_node 使用
SELECTED_SEARCH_ENGINE = DEFAULT_SEARCH_ENGINE


# --- 请求参数 ---

# 请求超时时长（秒）
# 简化注释：API 请求超时时间
# 修复：确保从环境变量加载的是浮点数，并将默认值修改为 300.0
try:
    REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300.0"))
except (ValueError, TypeError):
    REQUEST_TIMEOUT = 300.0


# 是否默认使用流式输出
# 简化注释：是否启用流式输出
USE_STREAM = os.getenv("USE_STREAM", "False").lower() in ('true', '1', 't')