# 文件路径: src/agents/long_form_agent.py
# -*- coding: utf-8 -*-
import json
import re
from .base_agent import BaseAgent
from src.llms.base import BaseLLM


class LongFormAgent(BaseAgent):
    """
    一个专门用于生成长篇文章或报告的Agent。
    它通过“生成大纲 -> 逐章扩展”的方式工作，以规避单次输出的token限制。
    """

    def __init__(self, llm: BaseLLM, outline_generator_llm: BaseLLM):
        # 使用一个LLM进行常规内容生成
        super().__init__(llm, system_prompt="你是一位资深的作家或研究员。")
        # 使用另一个（可能更强的）LLM来生成大纲
        self.outline_generator_llm = outline_generator_llm
        self.topic = ""

    async def _generate_outline(self, topic: str) -> dict:
        """第一步：调用LLM生成文章大纲"""
        print(f"--- [长文Agent] 步骤 1: 正在为 '{topic}' 生成大纲 ---")
        prompt = f"""
        请为关于“{topic}”的详细文章或报告，设计一个清晰的结构大纲。
        请严格以JSON格式返回，不要包含任何额外说明。JSON应包含一个`title`字段（文章标题）和一个`sections`字段（一个字符串列表，每个字符串是一个章节的标题）。
        示例JSON:
        {{
          "title": "人工智能发展史",
          "sections": [
            "引言：人工智能的黎明",
            "第一章：符号主义与早期探索 (1950s-1970s)",
            "第二章：知识工程与专家系统的兴衰 (1980s)",
            "第三章：连接主义的复兴与机器学习的崛起 (1990s-2000s)",
            "第四章：深度学习革命与大模型时代 (2010s-至今)",
            "结论：人工智能的未来展望"
          ]
        }}
        """
        # 生成大纲需要逻辑和结构，使用 temperature=0.0 保证稳定性
        response_str = await self.outline_generator_llm.chat([{"role": "user", "content": prompt}], temperature=0.0)
        try:
            # 修复：从返回的文本中稳健地提取JSON对象
            json_match = re.search(r"\{[\s\S]*\}", response_str)
            if not json_match:
                raise json.JSONDecodeError("模型返回的内容中未找到有效的JSON对象", response_str, 0)

            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            print("--- [长文Agent] 错误: 生成的大纲不是有效的JSON。将使用默认大纲。---")
            # 修复：如果失败，创建一个简单的默认大纲以保证流程继续
            return {"title": topic, "sections": [f"关于 {topic} 的详细介绍"]}

    async def _generate_section_content(self, section_title: str, full_context: str) -> str:
        """第二步：根据上下文，生成单个章节的内容"""
        print(f"--- [长文Agent] 步骤 2: 正在撰写章节 '{section_title}' ---")
        prompt = f"""
        我们正在共同撰写一篇关于“{self.topic}”的文章。

        **已经完成的部分如下：**
        ---
        {full_context}
        ---

        现在，请你接续上文，详细撰写标题为“{section_title}”的这一章节。
        请直接开始撰写正文，不要重复文章标题或已经写过的内容。确保内容过渡自然，风格一致。
        """
        # 创意写作场景，可以使用较高的 temperature
        return await self.llm.chat([{"role": "user", "content": prompt}], temperature=0.7)

    async def run(self, topic: str) -> str:
        """执行完整的长文生成任务"""
        self.topic = topic

        # 1. 生成大纲
        outline = await self._generate_outline(topic)
        if not outline or not outline.get("sections"):
            return "抱歉，无法为您生成文章大纲，任务中断。"

        full_text = f"# {outline.get('title', topic)}\n\n"

        # 2. 遍历大纲，逐章生成内容
        for section_title in outline["sections"]:
            section_content = await self._generate_section_content(section_title, full_text)
            full_text += f"## {section_title}\n\n{section_content}\n\n"
            # 为了避免上下文过长，可以考虑在一定长度后截断 full_context
            # 此处为简化实现，传递了全部历史文本

        print("--- [长文Agent] 任务完成: 已生成所有章节。---")
        return full_text