# 文件路径: src/agents/ppt_agent.py
# -*- coding: utf-8 -*-
"""
PPT 生成 Agent，专注于将内容结构化为演示文稿。
这是一个非图（non-graph）工作流中的示例Agent。
"""
import json
import os
import re
from datetime import datetime
from .base_agent import BaseAgent
from src.llms.base import BaseLLM
# 修复：从正确的工具位置导入
from src.tools.ppt_generator import generate_ppt_from_json


class PPTAgent(BaseAgent):
    """
    PPT Agent，用于根据主题生成演示文稿大纲并创建PPT文件。
    """

    def __init__(self, llm: BaseLLM):
        # 修复：优化系统提示，强制要求 LLM 输出严格的、纯净的 JSON 格式
        system_prompt = (
            "你是一位演示文稿设计专家。根据用户的主题，生成一份清晰、简洁的PPT大纲。"
            "你的任务是只输出一个JSON对象，不要包含任何额外的解释、注释或Markdown标记，例如```json。你的输出必须能直接被 `json.loads()` 解析。"
            "JSON结构必须如下：\n"
            "{\n"
            "  \"title\": \"报告主标题\",\n"
            "  \"slides\": [\n"
            "    {\"title\": \"页面标题\", \"points\": [\"要点1\", \"要点2\"]},\n"
            "    {\"title\": \"另一页标题\", \"points\": [\"要点A\", \"要点B\"]}\n"
            "  ]\n"
            "}"
        )
        super().__init__(llm, system_prompt=system_prompt)

    async def run(self, user_input: str) -> str:
        """
        生成PPT大纲的JSON，并调用工具创建.pptx文件。
        简化注释：生成PPT
        """
        print(f"--- [PPT Agent] 正在为 '{user_input}' 创建大纲JSON ---")

        # 1. 调用 LLM 生成结构化的 JSON 字符串
        response_str = await super().run(user_input)

        # 2. 解析 JSON 字符串
        try:
            # 修复：从返回的文本中稳健地提取JSON对象
            json_match = re.search(r"\{[\s\S]*\}", response_str)
            if not json_match:
                raise json.JSONDecodeError("模型返回的内容中未找到有效的JSON对象", response_str, 0)

            cleaned_json_str = json_match.group(0)
            ppt_data = json.loads(cleaned_json_str)
        except json.JSONDecodeError as e:
            error_msg = f"生成PPT失败：模型返回的不是有效的JSON格式。\n错误: {e}\n接收到的内容：\n{response_str}"
            print(f"--- [PPT Agent] {error_msg} ---")
            return error_msg

        # 3. 调用工具函数生成 .pptx 文件
        print("--- [PPT Agent] JSON解析成功，正在生成PPT文件 ---")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 确保输出目录存在
        output_dir = "output_reports"  # 与 conf.yaml 保持一致
        os.makedirs(output_dir, exist_ok=True)

        # 使用os.path.join来构建跨平台的路径
        output_path = os.path.join(output_dir, f"report_{timestamp}.pptx")

        try:
            status = generate_ppt_from_json(ppt_data, output_path)
            print(f"--- [PPT Agent] {status} ---")
            return status
        except Exception as e:
            error_msg = f"生成PPT文件时发生意外错误: {e}"
            print(f"--- [PPT Agent] {error_msg} ---")
            return error_msg