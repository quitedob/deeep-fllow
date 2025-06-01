# 文件路径: src/agents/counseling_agent.py
# -*- coding: utf-8 -*-
"""
通用对话/咨询 Agent，作为默认处理器。
这是一个非图（non-graph）工作流中的示例Agent。
"""
from .base_agent import BaseAgent
from src.llms.base import BaseLLM

class CounselingAgent(BaseAgent):
    """
    咨询 Agent，用于处理通用的对话和问答任务。
    """

    def __init__(self, llm: BaseLLM):
        """
        初始化咨询Agent。
        简化注释：初始化
        """
        system_prompt = "你是一个乐于助人的人工智能助手。请友好、清晰地回答用户的问题。"
        super().__init__(llm, system_prompt=system_prompt)

    async def run(self, user_input: str) -> str:
        """
        进行通用对话。
        简化注释：通用对话
        """
        print(f"--- [咨询 Agent] 正在回答: {user_input} ---")
        response = await super().run(user_input)
        return response