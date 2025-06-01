# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from typing import List, Optional # Ensure List and Optional are imported
from langgraph.graph import MessagesState

from src.prompts.planner_model import Plan
from src.rag import Resource


class State(MessagesState):
    """State for the agent system, extends MessagesState with next field."""

    # Runtime Variables
    locale: str = "en-US"
    observations: list[str] = []
    resources: list[Resource] = []
    plan_iterations: int = 0
    current_plan: Plan | str = None
    final_report: str = ""
    auto_accepted_plan: bool = False
    enable_background_investigation: bool = True
    background_investigation_results: str = None

    # --- [新增] 输出控制与结果路径 ---
    output_options: Optional[List[str]] = [] # 例如: ["pdf", "ppt", "tts"]
    output_dir: str = "./output_reports" # 默认输出目录

    # [新增] 用于存储生成文件路径的字段
    txt_path: Optional[str] = None
    md_path: Optional[str] = None
    pdf_path: Optional[str] = None
    ppt_path: Optional[str] = None
    tts_path: Optional[str] = None
