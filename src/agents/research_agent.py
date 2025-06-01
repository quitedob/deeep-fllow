# 文件路径: src/agents/research_agent.py
# -*- coding: utf-8 -*-
"""
Researcher Agent：对 Planner 输出的每个子任务 prompt 进行多源检索，
并将结果写入 plan["tasks"][i]["results"]。
"""
from typing import Dict, List, Any # Ensure Any is imported
from src.tools.fused_search import fused_search
import logging

logger = logging.getLogger(__name__)

def run_researcher(plan: Dict[str, Any]) -> Dict[str, Any]: # Input is 'plan', output is 'plan_with_results'
    """
    输入：
      - plan: 来自 Planner 的输出 (一个字典，包含 "topic" 和 "tasks" list)
              plan = {"topic": "...", "tasks": [{"name": ..., "prompt": ..., "results": [], ...}, ...]}
    输出：
      - plan_with_results: 修改后的 plan 字典，在每个 task 中填充 "results" 字段。
                           结构与输入 'plan' 相同，但 'results' 列表被填充。
                           This will be the value for 'plan_with_results' in the graph state.
    """
    logger.info(f"Researcher Agent 开始运行，处理主题: '{plan.get('topic', '未知主题')}'")

    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list):
        logger.error(f"输入 'plan' 中的 'tasks' 不是列表: {tasks}")
        # Potentially return plan unmodified or raise an error
        return plan

    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            logger.warning(f"任务列表中的项目 {i} 不是字典: {task}，跳过此任务。")
            continue

        prompt = task.get("prompt", "")
        task_name = task.get("name", f"任务 {i+1}")

        if not prompt:
            logger.warning(f"任务 '{task_name}' 的 prompt 为空，跳过检索。")
            task["results"] = [] #确保 'results' 字段存在
            continue

        logger.info(f"正在为任务 '{task_name}' 执行融合搜索，Prompt: '{prompt[:50]}...'")
        try:
            # 调用 fused_search，获取检索结果
            # fused_search 应该返回 List[Dict[str, Any]]
            search_results = fused_search(prompt, top_k=5)
            task["results"] = search_results # 修改传入的 plan 字典中的 task
            logger.info(f"任务 '{task_name}' 完成检索，获得 {len(search_results)} 条结果。")
        except Exception as e:
            logger.error(f"任务 '{task_name}' 在执行融合搜索时发生错误: {e}", exc_info=True)
            task["results"] = [] # 出错时确保 results 字段存在且为空

    # langgraph.json 中此节点的输出是 "plan_with_results".
    # 这个名字意味着我们应该返回整个 plan 对象，现在它已经被修改过了。
    # The 'plan' dictionary itself has been modified in place.
    logger.info("Researcher Agent 完成所有任务的检索。")
    return plan # Return the modified plan dictionary
