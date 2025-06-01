# 文件路径: src/agents/planner.py
# -*- coding: utf-8 -*-
"""
Planner Agent：将用户输入的主题拆解为若干子任务，并生成初始计划 State。
"""
from typing import Dict, Any, List # Ensure List is imported
import logging

logger = logging.getLogger(__name__)

def run_planner(topic: str) -> Dict[str, Any]: # Corresponds to 'plan' output in langgraph.json for this node
    """
    输入：
      - topic: 用户输入的研究主题
    输出 (一个字典，将作为 langgraph 中名为 'plan' 的状态字段):
      - plan: 包含拆分后的子任务列表，例如：
        {
          "topic": "...",
          "tasks": [
            {"name": "定义与背景", "prompt": "...", "results": [], "code": "", "code_result": {}},
            {"name": "相关工作", "prompt": "...", "results": [], "code": "", "code_result": {}},
            # ... 其他任务
          ]
        }
    """
    logger.info(f"Planner Agent 开始运行，主题: '{topic}'")

    # 简单模板拆分，生产环境可根据更复杂模型
    # 注意：这个 'plan_data' 字典的结构需要与 langgraph.json 中定义的 'plan' 输出相匹配
    # 并且也应该与 src/graph/types.py 中 State dataclass 的 'tasks' 字段结构兼容
    # (State 包含 topic 和 List[Task], Task 有 name, prompt, results, code, code_result)

    tasks_data: List[Dict[str, Any]] = [
        {
            "name": "定义与背景",
            "prompt": f"请简要介绍『{topic}』的背景与定义。",
            "results": [], # 初始为空
            "code": "",    # 初始为空
            "code_result": {} # 初始为空
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
            "code": "", # Coder Agent 可能会填充这个
            "code_result": {}
        },
        {
            "name": "实验与结果",
            "prompt": f"设计一个实验方案来验证『{topic}』的有效性，包含数据、方法与指标。",
            "results": [],
            "code": "", # Coder Agent 可能会填充这个 (如果实验涉及代码)
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

    # langgraph.json 中此节点的输出是 "plan"
    # 这个 "plan" 应该是一个字典，其内容会被 langgraph 引擎用来更新图的状态。
    # 如果 State dataclass 直接作为图状态，那么这里返回的字典的键应该对应 State 的字段。
    # 根据 langgraph.json, planner's output is "plan".
    # The next node "researcher" takes "plan" as input.
    # This means the 'plan' variable passed to researcher *is* this dictionary.
    # The researcher then modifies this dictionary (e.g., plan['tasks'][0]['results'] = ...)
    # So, the structure returned here IS the 'plan' that gets passed around and modified.

    plan_output_for_langgraph = {
        "topic": topic,
        "tasks": tasks_data
        # No need for output_options, output_dir etc. here, those are part of the overall State
        # but not directly produced by planner as a distinct output called "plan".
        # The 'plan' output of this node becomes the 'plan' input for the next.
    }

    logger.info(f"Planner Agent 完成计划制定，共 {len(tasks_data)} 个任务。")
    # This dictionary is what langgraph will provide as 'plan' to the next node.
    return plan_output_for_langgraph
