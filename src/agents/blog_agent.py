# 文件路径: src/agents/blog_agent.py
# -*- coding: utf-8 -*-
"""
博客写作 Agent，用于生成具有吸引力的文章。
这是一个非图（non-graph）工作流中的示例Agent。
"""
from .base_agent import BaseAgent
from src.llms.base import BaseLLM


class BlogAgent(BaseAgent):
    """
    博客 Agent，用于撰写风格轻松、引人入胜的文章。
    """

    def __init__(self, llm: BaseLLM):
        """
        初始化博客Agent。
        简化注释：初始化
        """
        system_prompt = "你是一位受欢迎的博主。你的任务是根据用户提供的主题，撰写一篇内容翔实、语言生动、结构清晰的博客文章。"
        super().__init__(llm, system_prompt=system_prompt)

    async def run(self, user_input: str) -> str:
        """
        撰写博客文章。
        简化注释：写博客
        """
        print(f"--- [博客 Agent] 正在撰写关于 '{user_input}' 的文章 ---")
        response = await super().run(user_input)
        return f"这是关于“{user_input}”的博客文章草稿：\n\n{response}"