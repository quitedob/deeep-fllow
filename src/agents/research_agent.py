# 文件路径: src/agents/research_agent.py
# -*- coding: utf-8 -*-
"""
研究型 Agent，专注于信息检索和分析。
这是一个非图（non-graph）工作流中的示例Agent。
"""
from .base_agent import BaseAgent
from src.llms.base import BaseLLM
# 修复：从正确的工具位置导入
from src.tools.fused_search import fused_search_tool


class ResearchAgent(BaseAgent):
    """
    研究 Agent，用于执行需要信息检索和深度分析的任务。
    """

    def __init__(self, llm: BaseLLM):
        """
        初始化研究Agent。
        简化注释：初始化
        """
        system_prompt = "你是一名专业的研究员。你的任务是根据用户的问题和提供的上下文信息，提供全面、准确、结构化的回答。"
        super().__init__(llm, system_prompt=system_prompt)

    async def run(self, user_input: str) -> str:
        """
        执行研究任务。
        简化注释：执行研究
        """
        print(f"--- [研究 Agent] 正在处理: {user_input} ---")

        # 修复：调用融合搜索工具来收集信息，而不是返回占位符
        print(f"--- [研究 Agent] 启动融合检索以收集关于 '{user_input}' 的资料 ---")
        # 注意：这里的fused_search_tool调用没有传递config，它会自己加载默认配置
        search_results = await fused_search_tool(user_input)

        if not search_results:
            return "抱歉，未能通过网络检索找到关于此主题的相关信息。"

        # 将搜索结果格式化为上下文
        context = "\n\n".join(
            [f"来源: {res.get('url', 'N/A')}\n内容: {res.get('content', '')}" for res in search_results]
        )

        # 构造新的提示，要求 LLM 基于收集到的信息进行分析
        analysis_prompt = (
            f"关于用户的问题 '{user_input}'，我已经收集到以下信息：\n\n"
            f"--- 检索到的上下文 ---\n"
            f"{context}\n"
            f"--- 结束上下文 ---\n\n"
            f"请你基于以上信息，为用户的问题 '{user_input}' 撰写一份详细的研究报告。请确保你的回答完全基于所提供的上下文，不要使用外部知识。"
        )

        # 调用父类的 run 方法（即调用 LLM）来生成最终报告
        print("--- [研究 Agent] 信息收集完毕，正在生成最终报告 ---")
        response = await super().run(analysis_prompt)

        return response