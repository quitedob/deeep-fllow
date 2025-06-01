# 文件路径: src/llms/base.py
# -*- coding: utf-8 -*-
"""
定义所有大语言模型 (LLM) 封装类的抽象基类。
"""

from abc import ABC, abstractmethod
from typing import List, Dict

class BaseLLM(ABC):
    """
    LLM 的抽象基类。
    所有具体的 LLM 实现（如 DeepSeekLLM）都应继承此类并实现其方法。
    """

    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], temperature: float = 1.0) -> str:
        """
        发送消息列表到 LLM 并获取回复。

        :param messages: 一个包含对话历史的消息列表，格式如 [{"role": "user", "content": "..."}]。
        :param temperature: 控制生成文本的随机性。
        :return: LLM 生成的回复字符串。
        """
        raise NotImplementedError("子类必须实现 'chat' 方法")

    @abstractmethod
    async def close(self):
        """
        关闭与 LLM 的连接，释放资源（例如，HTTP 客户端）。
        """
        raise NotImplementedError("子类必须实现 'close' 方法")