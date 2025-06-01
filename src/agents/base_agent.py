# 文件路径: src/agents/base_agent.py
# -*- coding: utf-8 -*-
from src.llms.base import BaseLLM
from typing import List, Dict, Union
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

# 统一定义消息类型
# 简化注释：消息字典
Message = Dict[str, str]
# 简化注释：对话轮次
Turn = List[Message]

class BaseAgent:
    """Agent 基类，封装通用的异步对话与任务执行逻辑"""

    def __init__(self, llm: BaseLLM, system_prompt: str = "", max_memory_turns: int = 10):
        """
        初始化Agent。
        简化注释：初始化
        """
        self.llm = llm
        self.system_prompt = system_prompt
        # 修复：内存结构改为按“轮”存储，每轮是一个包含用户和助手消息的列表
        self.memory: List[Turn] = []
        self.max_memory_turns = max_memory_turns

    def _trim_memory(self):
        """
        修剪记忆，防止上下文过长。保留最近的 `max_memory_turns` 轮对话。
        简化注释：修剪记忆
        """
        # 修复：按轮次进行裁剪
        if len(self.memory) > self.max_memory_turns:
            self.memory = self.memory[-self.max_memory_turns:]

    def build_messages(self, user_input: str) -> List[Message]:
        """
        构造发送给 LLM 的消息列表。
        简化注释：构造消息列表
        """
        self._trim_memory()

        messages: List[Message] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # 修复：将按轮存储的记忆扁平化为消息列表
        for turn in self.memory:
            messages.extend(turn)

        messages.append({"role": "user", "content": user_input})
        return messages

    async def run(self, user_input: str) -> str:
        """
        执行一次 Agent 异步任务。
        简化注释：执行Agent任务
        """
        messages = self.build_messages(user_input)

        # 假设 self.llm.chat 期望的格式是 List[Dict[str, str]]
        reply = await self.llm.chat(messages)

        # 修复：将本次对话作为一个完整的“轮次”存入记忆
        current_turn: Turn = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": reply}
        ]
        self.memory.append(current_turn)

        return reply