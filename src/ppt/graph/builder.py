# 文件路径: src/graph/builder.py
# -*- coding: utf-8 -*-
"""
将 langgraph.json 中的节点与实现函数进行注册，提供给 LangGraph 运行时。
"""
import os
import json
import logging
from typing import Dict, Any # 引入类型提示

from langgraph import Engine

from src.utils.logging import init_logger

# 初始化日志，方便调试
init_logger("INFO")
logger = logging.getLogger(__name__)

def build_graph():
    """
    读取项目根目录下的 langgraph.json，注册所有节点到 LangGraph Engine。
    返回 Engine 实例，可用于启动流程。
    """
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    lg_path = os.path.join(base_path, "langgraph.json")

    if not os.path.exists(lg_path):
        logger.error(f"未找到 langgraph.json，预期路径: {lg_path}")
        raise FileNotFoundError(f"未找到 langgraph.json，预期路径: {lg_path}")

    with open(lg_path, "r", encoding="utf-8") as f:
        graph_def = json.load(f)

    engine = Engine()
    for node_name, node_info in graph_def["nodes"].items():
        module_path = node_info["module"]
        func_name = node_info["func"]
        try:
            # 动态导入模块并获取函数
            if not module_path.startswith("src."):
                module_path = f"src.{module_path}"

            components = module_path.split(".")
            mod = __import__(module_path, fromlist=[components[-1]])
            func = getattr(mod, func_name)

            # 注册节点
            engine.add_node(
                name=node_name,
                func=func,
                inputs=node_info.get("inputs", []),
                outputs=node_info.get("outputs", [])
            )
            logger.info(f"已成功注册节点 '{node_name}' -> {module_path}.{func_name}")
        except (ImportError, AttributeError) as e:
            logger.error(f"注册节点 '{node_name}' ({module_path}.{func_name}) 失败: {e}", exc_info=True)
            raise

    # 注册依赖边
    for edge in graph_def["edges"]:
        engine.add_edge(edge["from"], edge["to"])
        logger.info(f"已成功连接边 '{edge['from']}' -> '{edge['to']}'")

    logger.info("LangGraph 引擎构建完成。")
    return engine

def run_langgraph(initial_state: Dict[str, Any]):
    """
    启动 Engine，并执行以 'planner' 为起点的整个流程。
    接收一个包含初始状态的字典。
    """
    engine = build_graph()

    topic = initial_state.get("topic")
    if not topic:
        logger.error("调用 run_langgraph 时，initial_state 中必须包含 'topic'。")
        raise ValueError("run_langgraph 需要一个包含 'topic' 的 initial_state 参数。")

    logger.info(f"使用主题 '{topic}' 和初始状态启动 LangGraph 流程...")

    # 修复：为了让 Planner 能接收到完整的初始状态（包括 output_dir 等），
    # 我们需要将整个 initial_state 包装在一个字典中，其键与 langgraph.json 中 planner 的输入匹配。
    # 我们假设 planner 的输入在 langgraph.json 中被定义为 "initial_state"。
    # 请确保 langgraph.json 中 planner 节点的 "inputs" 字段为 ["initial_state"]。
    inputs_for_engine = {"initial_state": initial_state}

    # 执行图，将包含完整状态的字典作为输入
    result_plan = engine.run(start="planner", inputs=inputs_for_engine)
    logger.info("LangGraph 流程执行完毕。")
    return result_plan