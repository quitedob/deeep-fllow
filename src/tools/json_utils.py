# 文件路径: src/utils/json_utils.py
# -*- coding: utf-8 -*-
# 提供JSON处理相关的工具函数

import re
import json

def repair_json_output(raw_text: str) -> str:
    """
    从可能包含额外文本的字符串中提取最外层的 JSON 对象。
    这对于处理 LLM 可能在 JSON 前后添加解释性文本的情况很有用。
    简化注释：修复并提取JSON
    """
    # 使用正则表达式查找第一个 '{' 和最后一个 '}' 之间的内容
    # 这是一种健壮的方法，可以处理 JSON 前后的 markdown 标记或解释
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if json_match:
        return json_match.group(0)

    # 如果正则匹配失败，可以尝试一些回退策略，例如直接解析
    try:
        json.loads(raw_text)
        return raw_text
    except json.JSONDecodeError:
        # 如果所有方法都失败，则返回一个表示空的JSON对象
        return "{}"