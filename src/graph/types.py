# 文件路径: src/graph/types.py
# -*- coding: utf-8 -*-
"""
扩展 State 类，包含输出选项与多格式文件路径等字段，为后续报告生成与音频合成提供存储。
"""
from typing import Any, Dict, List # Ensure these are imported
from dataclasses import dataclass, field

@dataclass
class Task:
    name: str
    prompt: str
    results: List[Dict[str, Any]] = field(default_factory=list)
    code: str = ""
    code_result: Dict[str, Any] = field(default_factory=dict)

@dataclass
class State:
    topic: str
    tasks: List[Task] = field(default_factory=list)
    # 新增输出相关字段
    output_options: Dict[str, Any] = field(default_factory=lambda: {"txt": True, "pdf": True, "ppt": True, "audio": True})
    output_dir: str = "outputs" # 确保这个目录与 agent/reporter.py 和 agent/voice_agent.py.py 中使用的目录一致
    report_paths: Dict[str, str] = field(default_factory=dict)
    audio_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
