# 文件路径: src/prompts/intent_model.py
# -*- coding: utf-8 -*-
# 定义意图识别节点的输出模型

from pydantic import BaseModel, Field
from typing import Literal

class IntentOutput(BaseModel):
    """
    意图识别节点 (intent_node) 期望从LLM解析的Pydantic模型。
    简化注释：意图输出模型
    """
    intent: Literal["research", "history_review", "general_chat", "ppt_generation"] = Field(
        ...,
        description="识别出的用户意图"
    )
    reasoning: str = Field(
        ...,
        description="模型做出此意图判断的简要理由"
    )