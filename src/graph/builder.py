# 文件路径: src/graph/builder.py
# -*- coding: utf-8 -*-
"""
将 langgraph.json 中的节点与实现函数进行注册，提供给 LangGraph 运行时。
"""
import os
import json
import logging

from langgraph import Engine  # 需要 pip install langgraph-cli[inmem]

from src.utils.logging import init_logger

# 初始化日志，方便调试
init_logger("INFO")
logger = logging.getLogger(__name__)

def build_graph():
    """
    读取项目根目录下的 langgraph.json，注册所有节点到 LangGraph Engine。
    返回 Engine 实例，可用于启动流程。
    """
    # 修改路径获取方式，确保在各种执行环境下都能正确找到 langgraph.json
    # __file__ 是当前文件 (builder.py) 的路径
    # os.path.dirname(__file__) 是 src/graph/
    # os.path.dirname(os.path.dirname(__file__)) 是 src/
    # os.path.dirname(os.path.dirname(os.path.dirname(__file__))) 是项目根目录
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
            # Ensure the module path is correctly resolved if agents are in src.agents
            if not module_path.startswith("src."):
                 module_path = f"src.{module_path}" # Assuming agents are relative to src

            components = module_path.split(".")
            # The actual module to import is the full path, e.g., src.agents.planner
            # fromlist expects the last component if we want to get specific attributes from it
            mod = __import__(module_path, fromlist=[components[-1]])
            func = getattr(mod, func_name)

            # 注册节点
            engine.add_node(
                name=node_name,
                func=func, # Pass the actual function object
                inputs=node_info.get("inputs", []),
                outputs=node_info.get("outputs", [])
            )
            logger.info(f"已成功注册节点 '{node_name}' -> {module_path}.{func_name}")
        except (ImportError, AttributeError) as e:
            logger.error(f"注册节点 '{node_name}' ({module_path}.{func_name}) 失败: {e}", exc_info=True)
            # Optionally, re-raise to halt execution if a node can't be registered
            raise  # Re-raise the exception to make it clear registration failed

    # 注册依赖边
    for edge in graph_def["edges"]:
        engine.add_edge(edge["from"], edge["to"])
        logger.info(f"已成功连接边 '{edge['from']}' -> '{edge['to']}'")

    logger.info("LangGraph 引擎构建完成。")
    return engine

# 修改：确保 run_langgraph 在没有 topic 的情况下也能被调用（如果适用）或有默认行为
# 但根据 langgraph.json 的 'planner' 节点，'topic' 是必需的输入
def run_langgraph(topic: str = None): # Added default None for topic
    """
    启动 Engine，并执行以 'planner' 为起点的整个流程。
    """
    engine = build_graph() # build_graph now raises error if json not found or node registration fails

    if topic is None:
        logger.warning("调用 run_langgraph 时未提供 'topic'。Planner 节点可能需要它。")
        # Depending on desired behavior, either raise error or proceed if planner can handle None
        # For now, let's assume planner requires a topic
        raise ValueError("run_langgraph 需要一个 'topic' 参数来启动 'planner' 节点。")

    logger.info(f"使用主题 '{topic}' 启动 LangGraph 流程...")
    # 启动流程：传入初始变量 topic
    # The 'inputs' should be a dictionary mapping input names to values
    result = engine.run(start="planner", inputs={"topic": topic})
    logger.info("LangGraph 流程执行完毕。")
    return result

# Example of how to test this builder (optional, can be removed)
if __name__ == '__main__':
    try:
        logger.info("尝试构建 LangGraph 引擎...")
        # This test assumes dummy agent files exist as per langgraph.json
        # To run this test, you'd need to create those dummy files first.
        # For example, src/agents/planner.py with a run_planner function.
        # test_engine = build_graph()
        # if test_engine:
        #     logger.info("LangGraph 引擎成功构建。")
        #     # Example run (requires dummy agents that match langgraph.json inputs/outputs)
        #     # test_result = run_langgraph(topic="测试主题")
        #     # logger.info(f"LangGraph 测试运行结果: {test_result}")
        # else:
        #     logger.error("LangGraph 引擎构建失败。")
        logger.info("请注意: 直接运行此文件仅用于构建测试。实际运行需通过 main.py 或类似入口。")
        logger.info("确保 langgraph.json 中引用的所有模块和函数都已实现。")
    except Exception as e:
        logger.error(f"执行 builder.py 测试时发生错误: {e}", exc_info=True)
