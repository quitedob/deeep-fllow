# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from .loader import load_yaml_config
from .questions import BUILT_IN_QUESTIONS, BUILT_IN_QUESTIONS_ZH_CN
# SELECTED_SEARCH_ENGINE and SearchEngine are no longer in the current settings.py
# from .settings import SELECTED_SEARCH_ENGINE, SearchEngine

# Redundant imports removed for cleanliness
# from .loader import load_yaml_config
# from .questions import BUILT_IN_QUESTIONS, BUILT_IN_QUESTIONS_ZH_CN

# 从 .env 文件加载环境变量
# from dotenv import load_dotenv # load_dotenv is already called in settings.py
# Redundant load_dotenv call also removed. settings.py handles this.

# Team configuration
TEAM_MEMBER_CONFIGRATIONS = {
    "researcher": {
        "name": "researcher",
        "desc": (
            "Responsible for searching and collecting relevant information, understanding user needs and conducting research analysis"
        ),
        "desc_for_llm": (
            "Uses search engines and web crawlers to gather information from the internet. "
            "Outputs a Markdown report summarizing findings. Researcher can not do math or programming."
        ),
        "is_optional": False,
    },
    "coder": {
        "name": "coder",
        "desc": (
            "Responsible for code implementation, debugging and optimization, handling technical programming tasks"
        ),
        "desc_for_llm": (
            "Executes Python or Bash commands, performs mathematical calculations, and outputs a Markdown report. "
            "Must be used for all mathematical computations."
        ),
        "is_optional": True,
    },
}

TEAM_MEMBERS = list(TEAM_MEMBER_CONFIGRATIONS.keys())

# __all__ 定义了从该包（config）中 'from src.config import *' 时会导入的名称
__all__ = [
    # "SELECTED_SEARCH_ENGINE", # Removed
    # "SearchEngine", # Removed
    "load_yaml_config",
    "BUILT_IN_QUESTIONS",
    "BUILT_IN_QUESTIONS_ZH_CN",
]