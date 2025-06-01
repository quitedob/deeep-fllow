# 文件路径: src/graph/builder.py
# -*- coding: utf-8 -*-
"""
使用 StateGraph 构建有状态的节点执行图，替代旧版 Engine，并保留 build_graph_with_memory 对外接口。
"""

import os
import json
import logging
from typing import Dict, Any

from langgraph.graph import StateGraph, START, END  # 使用新版 API
from typing_extensions import TypedDict

from src.utils.logging import init_logger

# 初始化日志
init_logger("INFO")
logger = logging.getLogger(__name__)


# 1. 定义整个图的状态结构（TypedDict）
class StateSchema(TypedDict, total=False):
    """
    定义整个工作流所需状态字段。
    'total=False' 表示这些键可以不都存在，节点会动态返回更新的字段。
    """
    topic: str               # 用户输入的主题
    tasks: list[str]         # planner 生成的子任务列表
    research_results: dict   # researcher 返回的检索结果
    code_results: dict       # coder 返回的代码执行结果
    report_paths: dict       # reporter 生成的报告各格式路径
    audio_path: str          # voice 生成的音频文件路径


def build_graph() -> StateGraph:
    """
    构建一个基于 StateGraph 的节点执行图。
    从项目根目录加载 langgraph.json，动态注册所有节点并连接边。
    返回一个已注册好节点与边的 StateGraph 实例。
    """

    # 1) 定位项目根目录下的 langgraph.json
    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    lg_path = os.path.join(base_path, "langgraph.json")

    if not os.path.exists(lg_path):
        logger.error(f"未找到 langgraph.json，预期路径: {lg_path}")
        raise FileNotFoundError(f"langgraph.json 未找到，预期路径: {lg_path}")

    # 2) 读取配置文件
    with open(lg_path, "r", encoding="utf-8") as f:
        graph_def = json.load(f)

    # 3) 实例化 StateGraph，同时指定状态模型
    graph = StateGraph(StateSchema)

    # 4) 动态注册所有节点
    for node_name, node_info in graph_def.get("nodes", {}).items():
        module_path = node_info.get("module", "")
        func_name = node_info.get("func", "")

        # 如果 module_path 没有以 "src." 开头，就加上前缀，方便定位
        if not module_path.startswith("src."):
            module_path = f"src.{module_path}"

        # 动态导入模块，并获取函数对象
        components = module_path.split(".")
        try:
            mod = __import__(module_path, fromlist=[components[-1]])
            func = getattr(mod, func_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"无法导入节点函数：{module_path}.{func_name}，错误: {e}", exc_info=True)
            raise

        # 将节点函数注册到 StateGraph
        # 注意：节点函数应该接收并返回部分 StateSchema 定义字段
        graph.add_node(node_name, func)
        logger.info(f"已成功注册节点 '{node_name}' -> {module_path}.{func_name}")

    # 5) 注册有向边（依赖关系）
    for edge in graph_def.get("edges", []):
        src = edge.get("from")
        dst = edge.get("to")
        graph.add_edge(src, dst)
        logger.info(f"已成功连接边 '{src}' -> '{dst}'")

    # 6) 设置入口点和结束点
    graph.set_entry_point("planner")
    graph.add_edge("voice", END)

    logger.info("StateGraph 构建完成。")
    return graph


def build_graph_with_memory() -> StateGraph:
    """
    构建一个带“记忆”能力的 StateGraph 引擎。
    当前逻辑与 build_graph 相同，但保留该接口以便后续接入持久化或内存插件。
    """
    # 目前直接返回与 build_graph 相同的实例，后续可在此处注入记忆模块
    graph = build_graph()
    logger.info("已启用带记忆功能的 StateGraph（当前与标准图等效）。")
    return graph


def run_langgraph(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 StateGraph 执行整个流程，返回最终状态 (state)。
    initial_state 中必须包含 'topic' 字段，其它字段可留空。
    """

    # 1) 构建带记忆或不带记忆的 StateGraph（一般使用 build_graph_with_memory）
    graph = build_graph_with_memory()

    # 2) 检查 'topic'
    topic = initial_state.get("topic")
    if not topic:
        logger.error("调用 run_langgraph 时，initial_state 必须包含 'topic'")
        raise ValueError("run_langgraph 需要一个包含 'topic' 的 initial_state 参数。")

    logger.info(f"使用主题 '{topic}' 启动 StateGraph 流程…")

    # 3) 编译并执行有状态图
    runnable = graph.compile()
    final_state: Dict[str, Any] = runnable.invoke(initial_state)

    logger.info("StateGraph 流程执行完毕。")
    return final_state


# 如果需要单独测试 builder，可运行以下代码（可选）
if __name__ == "__main__":
    try:
        logger.info("正在测试 StateGraph 构建…")
        test_graph = build_graph_with_memory()
        logger.info("StateGraph 构建成功，您可以通过 run_langgraph 方法验证整个流程。")
    except Exception as e:
        logger.error(f"测试 StateGraph 构建时发生错误: {e}", exc_info=True)
