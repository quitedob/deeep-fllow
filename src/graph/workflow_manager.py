# 文件路径: src/graph/workflow_manager.py
# -*- coding: utf-8 -*-
"""
工作流与任务编排模块。
负责根据用户输入，动态选择并执行合适的Agent来完成任务。
注意：这是一个与主 StateGraph 工作流不同的、独立的实现。
"""

import asyncio
from src.agents.base_agent import BaseAgent
from src.agents import (
    ResearchAgent,
    PPTAgent,
    BlogAgent,
    CounselingAgent,
    LongFormAgent,
)
from src.llms.deepseek import DeepSeekLLM


class WorkflowManager:
    """工作流管理器，支持异步执行和基于意图的动态路由"""

    def __init__(self):
        """
        初始化所有需要的LLM实例和Agent实例。
        简化注释：初始化管理器
        """
        # 使用不同的模型初始化不同角色的LLM
        self.llm_chat = DeepSeekLLM(model="deepseek-chat")
        self.llm_reasoner = DeepSeekLLM(model="deepseek-coder") # 使用更适合推理的模型

        # 实例化所有可用的Agent
        self.agents = {
            "research": ResearchAgent(self.llm_chat),
            "ppt": PPTAgent(self.llm_chat),
            "blog": BlogAgent(self.llm_chat),
            "counseling": CounselingAgent(self.llm_chat),
            "coder": BaseAgent(self.llm_reasoner, system_prompt="你是一个顶级的程序员，请编写代码。"),
            "longform": LongFormAgent(llm=self.llm_chat, outline_generator_llm=self.llm_reasoner)
        }

    def _route_by_intent(self, user_input: str) -> str:
        """
        基于用户输入的简单意图路由。
        修复：为路由逻辑增加优先级，使其更健壮。
        简化注释：意图路由
        """
        lowered_input = user_input.lower()

        # 优先级：长文 > PPT > 博客 > 代码 > 研究 > 通用咨询
        if "详细报告" in lowered_input or "长文" in lowered_input or "写一篇关于" in lowered_input:
            return "longform"
        if "ppt" in lowered_input or "演示文稿" in lowered_input:
            return "ppt"
        if "博客" in lowered_input or "写文章" in lowered_input:
            return "blog"
        if "代码" in lowered_input or "函数" in lowered_input or "算法" in lowered_input:
            return "coder"
        if "研究" in lowered_input or "分析" in lowered_input or "调查" in lowered_input:
            return "research"

        return "counseling"

    async def handle_request(self, user_input: str, scenario: str = None) -> str:
        """
        异步处理用户请求：如果未指定场景，则动态路由。
        简化注释：处理请求
        """
        if not user_input:
            return "请输入您的问题。"

        if scenario is None:
            scenario = self._route_by_intent(user_input)

        print(f"--- [工作流] 已路由到场景: {scenario} ---")

        agent = self.agents.get(scenario)
        if agent is None:
            return f"错误：未找到场景 '{scenario}' 对应的处理器。"

        try:
            result = await agent.run(user_input)
            return result
        except Exception as e:
            print(f"--- [工作流] 执行Agent时发生错误: {e} ---")
            return "抱歉，处理您的请求时遇到了一个内部错误。"

    async def close_all(self):
        """
        安全地关闭所有LLM客户端，释放网络连接。
        简化注释：关闭所有连接
        """
        print("\n--- [工作流] 正在关闭所有连接... ---")
        await self.llm_chat.close()
        await self.llm_reasoner.close()
        print("--- [工作流] 所有连接已关闭。 ---")


async def main():
    """
    一个完整的异步主函数，用于在命令行中与WorkflowManager交互。
    简化注释：交互主函数
    """
    print("欢迎使用AI多功能助手！(输入 'exit' 或 'quit' 退出)")
    manager = WorkflowManager()

    try:
        while True:
            user_input = input("\n您好，有什么可以帮您？\n> ")
            if user_input.lower() in ("exit", "quit"):
                break

            result = await manager.handle_request(user_input)
            print(f"\nAI: {result}")

    except (KeyboardInterrupt, EOFError):
        print("\n检测到中断，正在退出...")
    finally:
        await manager.close_all()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"程序启动失败: {e}")