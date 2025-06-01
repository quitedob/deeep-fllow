# 文件路径: src/agents/planner.py
# -*- coding: utf-8 -*-
"""
Planner Agent：将用户输入的主题拆解为若干子任务，并生成初始计划 State。
"""
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

# 修复：修改函数签名以接收完整的初始状态
def run_planner(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入 (一个字典，代表完整的初始状态):
      - state: {
          "topic": "...",
          "output_dir": "...",
          "output_options": [...]
        }
    输出 (一个字典，将作为 langgraph 中名为 'plan' 的状态字段):
      - plan: 包含拆分后的子任务列表及全局配置，例如：
        {
          "topic": "...",
          "tasks": [ ... ],
          "output_dir": "...",
          "output_options": [...]
        }
    """
    # 修复：从 state 字典中提取所需信息
    topic = state.get("topic", "")
    output_dir = state.get("output_dir", "outputs")
    output_options = state.get("output_options", ["md", "txt", "pdf", "ppt", "audio"])

    if not topic:
        logger.error("Planner Agent 错误：输入的 state 中没有 'topic'。")
        # 返回一个包含错误信息的状态，或直接引发异常
        return {**state, "tasks": [], "error": "Missing topic"}

    logger.info(f"Planner Agent 开始运行，主题: '{topic}'")

    # 简单模板拆分
    tasks_data: List[Dict[str, Any]] = [
        {
            "name": "定义与背景",
            "prompt": f"请简要介绍『{topic}』的背景与定义。",
            "results": [],
            "code": "",
            "code_result": {}
        },
        {
            "name": "相关工作",
            "prompt": f"请列出与『{topic}』相关的主要文献和进展，附上简单评价。",
            "results": [],
            "code": "",
            "code_result": {}
        },
        {
            "name": "技术细节",
            "prompt": f"请详细描述实现『{topic}』所需的关键技术和算法步骤，并给出示例代码。",
            "results": [],

            "code": "",
            "code_result": {}
        },
        {
            "name": "实验与结果",
            "prompt": f"设计一个实验方案来验证『{topic}』的有效性，包含数据、方法与指标。",
            "results": [],
            "code": "",
            "code_result": {}
        },
        {
            "name": "总结与展望",
            "prompt": f"请对『{topic}』的未来发展进行预测和展望。",
            "results": [],
            "code": "",
            "code_result": {}
        }
    ]

    # 构造输出，这个字典将成为图状态中的 'plan' 对象
    # 修复：将 output_dir 和 output_options 一并放入返回的 plan 中，以便后续节点使用
    plan_output_for_langgraph = {
        "topic": topic,
        "tasks": tasks_data,
        "output_dir": output_dir,
        "output_options": output_options,
        "report_paths": state.get("report_paths", {}), # 保持传递
        "audio_path": state.get("audio_path", "")      # 保持传递
    }

    logger.info(f"Planner Agent 完成计划制定，共 {len(tasks_data)} 个任务。")
    return plan_output_for_langgraph