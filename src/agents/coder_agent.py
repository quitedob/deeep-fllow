# 文件路径: src/agents/coder_agent.py
# -*- coding: utf-8 -*-
"""
Coder Agent：从 plan["tasks"] 中寻找“技术细节”任务里的 code 片段并执行，
将输出结果写入 plan["tasks"]["code_result"]。
如果“技术细节”任务未生成 code，则跳过执行。
"""
import tempfile
import subprocess
import os
from typing import Dict, Any # Ensure Any is imported
import logging

logger = logging.getLogger(__name__)

def run_coder(plan: Dict[str, Any]) -> Dict[str, Any]: # Input 'plan_with_results', output 'plan_with_code'
    """
    输入：
      - plan: 来自 Researcher 的输出 (一个字典，包含 "topic" 和 "tasks" list)
              plan = {"topic": "...", "tasks": [{"name": ..., "prompt": ..., "results": [...], "code": "...", ...}, ...]}
    输出：
      - plan_with_code: 修改后的 plan 字典，在 "技术细节" 任务中填充 "code_result" 字段。
                         结构与输入 'plan' 相同，但特定 task 的 'code_result' 被填充。
    """
    logger.info(f"Coder Agent 开始运行，处理主题: '{plan.get('topic', '未知主题')}'")

    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list):
        logger.error(f"输入 'plan' 中的 'tasks' 不是列表: {tasks}")
        return plan # Return plan unmodified

    code_executed_for_task = False
    for task in tasks:
        if not isinstance(task, dict):
            logger.warning(f"任务列表中发现非字典类型项目: {task}，跳过。")
            continue

        # 确保每个任务都有 'code_result' 键，即使是空的
        if "code_result" not in task:
            task["code_result"] = {"stdout": "", "stderr": "未执行代码", "returncode": None}

        if task.get("name") == "技术细节":
            code_to_execute = task.get("code", "").strip()

            if not code_to_execute:
                logger.info(f"任务 '{task.get('name')}' 未提供代码，跳过执行。")
                task["code_result"] = {"stdout": "", "stderr": "未提供代码", "returncode": None}
                continue # Continue to check other tasks, though typically there's one "技术细节"

            logger.info(f"在任务 '{task.get('name')}' 中找到代码，准备执行:
{code_to_execute[:200]}...")

            # 将 code 写入临时文件并执行
            tmp_path = "" # Initialize tmp_path
            try:
                with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
                    tmp.write(code_to_execute)
                    tmp_path = tmp.name

                # Ensure file is closed before subprocess tries to read it, especially on Windows.
                # The 'with' statement handles closing.

                proc = subprocess.run(
                    ["python", tmp_path], # Using default system python
                    capture_output=True,
                    text=True, # Decodes stdout/stderr as UTF-8 by default (Python 3.7+)
                    timeout=60 # 60秒超时
                )
                task["code_result"] = {
                    "stdout": proc.stdout,
                    "stderr": proc.stderr,
                    "returncode": proc.returncode
                }
                logger.info(f"代码执行完成。返回码: {proc.returncode}")
                logger.debug(f"Stdout:
{proc.stdout}")
                if proc.stderr:
                    logger.warning(f"Stderr:
{proc.stderr}")
                code_executed_for_task = True # Mark that code was found and attempted

            except subprocess.TimeoutExpired:
                logger.error(f"代码执行超时 (超过60秒)。")
                task["code_result"] = {
                    "stdout": "",
                    "stderr": "代码执行超时 (60秒)",
                    "returncode": -100 # Custom code for timeout
                }
                code_executed_for_task = True
            except Exception as e:
                logger.error(f"代码执行过程中发生错误: {e}", exc_info=True)
                task["code_result"] = {
                    "stdout": "",
                    "stderr": f"代码执行错误: {str(e)}",
                    "returncode": -1
                }
                code_executed_for_task = True
            finally:
                # 删除临时文件
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                        logger.debug(f"临时代码文件 '{tmp_path}' 已删除。")
                    except OSError as e_remove:
                        logger.error(f"删除临时代码文件 '{tmp_path}' 失败: {e_remove}", exc_info=True)

            # As per user's original code: "break # 只执行第一个“技术细节”任务"
            # If multiple "技术细节" tasks could exist and all should run, remove this break.
            # For now, keeping behavior of only running first one found.
            if code_executed_for_task: # If code was found and execution attempted for "技术细节"
                 break

    if not code_executed_for_task:
        logger.info("未在任何任务中找到名为 '技术细节' 且包含可执行代码的任务。")

    # The 'plan' dictionary itself has been modified in place.
    logger.info("Coder Agent 完成运行。")
    return plan # Return the modified plan dictionary
