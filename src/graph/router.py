# 文件路径: src/graph/router.py
# -*- coding: utf-8 -*-
# 定义图中的条件路由逻辑

from typing import Literal, List, Dict, Any

from src.config import Configuration
from src.prompts.planner_model import Plan, StepType  # 修复：导入 Plan 模型


def route_after_intent(state: Dict[str, Any]) -> Literal["coordinator", "reporter"]:
    """
    在识别意图和分析图片后，决定是启动研究流程还是直接去报告。
    简化注释：意图识别后的路由
    """
    intent = state.get("intent")
    if intent == "history_review":
        print("--- [路由] 决策：历史回顾，直接转向报告员 ---")
        return "reporter"

    print("--- [路由] 决策：常规研究，转向协调员 ---")
    return "coordinator"


def route_after_coordinator(state: Dict[str, Any]) -> Literal[
    "planner", "research_team", "human_feedback", "background_investigator"]:
    """
    在协调员之后决定下一步。
    简化注释：协调员后的路由
    """
    # 修复：从 coordinator_node 的 Command 中获取路由目标
    # 这个路由函数实际上可能不会被 LangGraph 的 Command 机制调用，但我们保持逻辑正确
    activated_agents: List[str] = state.get("activated_agents", [])
    if not isinstance(activated_agents, list) or not activated_agents:
        print("--- [路由] 错误：协调员未返回有效的 'activated_agents' 列表，需要人工干预 ---")
        return "human_feedback"

    if "background_investigator" in activated_agents:
        print("--- [路由] 决策：需要背景调查，转向背景调查员 ---")
        return "background_investigator"

    if "planner" in activated_agents:
        print("--- [路由] 决策：需要规划，转向规划师 ---")
        return "planner"

    if "research_team" in activated_agents:
        print("--- [路由] 决策：直接研究，转向研究团队 ---")
        return "research_team"

    print(f"--- [路由] 决策：路径不明确 (激活的智能体: {activated_agents})，需要人工干预 ---")
    return "human_feedback"


def route_after_planner(state: Dict[str, Any]) -> Literal["research_team", "human_feedback"]:
    """
    在规划师之后决定下一步。
    简化注释：规划师后的路由
    修复：检查 state 中的 current_plan 对象而不是 plan 列表。
    """
    plan = state.get("current_plan")
    # 检查 plan 是否是 Plan 类的实例，并且其 steps 列表不为空
    if isinstance(plan, Plan) and plan.steps:
        print(f"--- [路由] 已生成计划 ({len(plan.steps)}个步骤)，转向研究团队 ---")
        return "research_team"

    print("--- [路由] 未能从规划师处获得有效计划，需要人工干预 ---")
    return "human_feedback"


# 修复：实现真正的多轮研究判断逻辑
def should_continue_research(state: Dict[str, Any]) -> Literal["planner", "reporter", "researcher", "coder"]:
    """
    在研究团队节点之后，判断是继续研究、重新规划还是生成报告。
    简化注释：判断是否继续研究
    """
    # 逻辑1：检查是否所有步骤都已完成
    current_plan = state.get("current_plan")
    if isinstance(current_plan, Plan):
        # 如果还有未执行的步骤，则根据下一个步骤的类型继续
        next_step = next((step for step in current_plan.steps if not step.execution_res), None)
        if next_step:
            if next_step.step_type == StepType.RESEARCH:
                return "researcher"
            if next_step.step_type == StepType.PROCESSING:
                return "coder"

    # 逻辑2：如果所有步骤都完成了，或者计划无效，则检查迭代次数
    config = state.get("config")
    if not isinstance(config, Configuration):
        config = Configuration.from_runnable_config(state.get("config", {}))

    plan_iterations = state.get("plan_iterations", 1)
    if plan_iterations >= config.max_plan_iterations:
        print(f"--- [路由] 已达到最大规划迭代次数 ({config.max_plan_iterations})，转向报告员 ---")
        return "reporter"

    # 逻辑3：如果未达到最大迭代次数，但需要更多信息，可以返回规划师
    # （这里的逻辑可以根据需要变得更复杂，例如分析当前结果的质量）
    print(f"--- [路由] 研究内容可能不足，返回规划师进行新一轮规划 ---")
    return "planner"