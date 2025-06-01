# 文件路径: src/graph/builder.py
# -*- coding: utf-8 -*-
"""
带记忆的 LangGraph 引擎构建器与运行器：
- `build_graph()`: 从 langgraph.json 配置文件动态构建 StateGraph。
- `run_langgraph()`: 集成了分布式锁、Redis状态持久化（支持分片）、Pub/Sub消息通知、
  以及详细的异常处理机制，是整个研究流程的核心驱动函数。
"""

import os
import json
import logging
import time
import uuid  # 确保导入 uuid
from typing import Dict, Any, Optional, TypedDict  # 确保导入 TypedDict

from langgraph.graph import StateGraph, START, END  # 从 langgraph.graph 导入

from src.utils.logging import init_logger
from src.utils.cache import (
    get_state_sharded, set_state_sharded, delete_state_sharded,
    get_state, set_state, delete_state
)
from src.utils.lock import acquire_lock, release_lock
from src.config.settings import REDIS_HOST, REDIS_PORT, REDIS_DB

import redis

# 初始化日志
init_logger("INFO")  # 确保日志已配置
logger = logging.getLogger(__name__)

# Pub/Sub 客户端 (用于发布“全流程 START/COMPLETE/ERROR” 以及各节点状态)
_pubsub = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)


# 定义 LangGraph 状态模式 (StateSchema)
class StateSchema(TypedDict, total=False):
    """
    LangGraph 流程中传递的状态字典结构。
    `total=False` 表示并非所有键都必须存在。
    """
    topic: str  # 研究主题
    tasks: list[str]  # Planner 生成的任务列表
    research_results: dict  # Researcher 收集的研究结果
    code_results: dict  # Coder 执行代码的结果
    report_paths: dict  # Reporter 生成的报告路径 (多格式)
    audio_path: str  # Voice Agent 生成的音频路径
    error: Optional[str]  # 流程中发生的错误信息
    _session_id: Optional[str]  # 内部使用的会话ID，确保Agent能访问
    # --- CLI模式新增字段，也可能通过API传递 ---
    output_dir: Optional[str]  # 输出目录
    output_options: Optional[list[str]]  # 输出格式选项


def build_graph() -> StateGraph:
    """
    读取项目根目录下的 langgraph.json 并注册节点至 StateGraph。
    不包含持久化或插件逻辑，仅负责图结构定义。
    """
    logger.info("开始构建 LangGraph 实例...")
    try:
        # 获取项目根目录，兼容不同执行路径
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    except NameError:  # 如果在某些非标准 Python 环境中 __file__ 未定义
        base_path = os.getcwd()

    lg_json_path = os.path.join(base_path, "langgraph.json")
    logger.debug(f"期望的 langgraph.json 路径: {lg_json_path}")

    if not os.path.exists(lg_json_path):
        logger.error(f"langgraph.json 文件未找到，路径: {lg_json_path}")
        raise FileNotFoundError(f"核心配置文件 langgraph.json 未在路径 {lg_json_path} 找到。")

    with open(lg_json_path, "r", encoding="utf-8") as f:
        graph_def = json.load(f)
    logger.debug(f"已加载 langgraph.json 内容: {json.dumps(graph_def, indent=2, ensure_ascii=False)}")

    graph = StateGraph(StateSchema)  # 使用定义好的 StateSchema

    # 动态注册节点
    nodes_config = graph_def.get("nodes", {})
    if not nodes_config:
        logger.warning("langgraph.json 中未定义任何节点 (nodes)。")

    for node_name, node_info in nodes_config.items():
        module_path_str = node_info.get("module", "")
        func_name_str = node_info.get("func", "")

        if not module_path_str or not func_name_str:
            logger.error(f"节点 '{node_name}' 的 module 或 func 未在 langgraph.json 中定义。")
            raise ValueError(f"节点 '{node_name}' 配置不完整。")

        # 确保模块路径以 "src." 开头，以便正确导入
        if not module_path_str.startswith("src."):
            full_module_path = f"src.{module_path_str}"
        else:
            full_module_path = module_path_str

        try:
            module_components = full_module_path.split(".")
            # __import__ 的 fromlist 参数需要是模块的直接父包或最后一级组件
            imported_module = __import__(full_module_path, fromlist=[module_components[-1]])
            node_function = getattr(imported_module, func_name_str)

            graph.add_node(node_name, node_function)
            logger.info(f"已成功注册节点 '{node_name}' -> {full_module_path}.{func_name_str}")
        except (ImportError, AttributeError) as e:
            logger.error(f"导入或获取节点函数 {full_module_path}.{func_name_str} (节点名: '{node_name}') 失败: {e}",
                         exc_info=True)
            raise

    # 注册边
    edges_config = graph_def.get("edges", [])
    if not edges_config:
        logger.warning("langgraph.json 中未定义任何边 (edges)。")

    for edge in edges_config:
        from_node = edge.get("from")
        to_node = edge.get("to")
        if not from_node or not to_node:
            logger.error(f"边定义不完整: {edge}")
            raise ValueError("边定义中缺少 'from' 或 'to' 节点。")
        graph.add_edge(from_node, to_node)
        logger.info(f"已成功连接边: '{from_node}' -> '{to_node}'")

    # 设置入口点和可能的固定结束点 (如果 langgraph.json 中未定义)
    # 假设 'planner' 是入口，'voice' (或最后一个处理报告的 agent) 是出口并连接到 END
    # 这些应与 langgraph.json 中的定义一致或作为补充
    entry_point = graph_def.get("entry_point", "planner")  # 从配置读入口，默认 planner
    graph.set_entry_point(entry_point)
    logger.info(f"已设置图入口点为: '{entry_point}'")

    # 示例：如果 voice agent 是流程末端，则连接到 END
    # 实际项目中，应根据 langgraph.json 的 "end_point_to_END" (自定义字段) 或具体逻辑
    if "voice" in nodes_config:  # 假设 voice 是终点之一
        graph.add_edge("voice", END)
        logger.info("已添加从 'voice' 节点到 END 的边。")
    else:  # 如果没有 voice 节点，可能需要一个明确的报告节点连接到 END
        # 查找 langgraph.json 中是否有明确指示哪个节点连接到 END
        final_node_to_end = graph_def.get("final_node_to_END")
        if final_node_to_end and final_node_to_end in nodes_config:
            graph.add_edge(final_node_to_end, END)
            logger.info(f"已添加从 '{final_node_to_end}' 节点到 END 的边 (根据配置)。")
        elif "reporter" in nodes_config:  # 备选：如果 reporter 存在且未指定最终节点
            graph.add_edge("reporter", END)  # 假设 reporter 是一个常见的终点
            logger.info("警告: 未明确指定最终节点连接到 END，默认将 'reporter' 连接到 END。")

    logger.info("LangGraph 实例构建完成。")
    return graph


def build_graph_with_memory() -> StateGraph:
    """带记忆模式下的 Graph 构建：当前直接调用 build_graph()。"""
    # 未来可在此处添加特定于记忆的图构建逻辑，如检查点、不同状态模式等
    logger.info("调用 build_graph() 构建带记忆的图实例。")
    return build_graph()


def _get_state_persister(use_sharded: bool):
    """根据 use_sharded 标志选择合适的 Redis 状态存取函数组。"""
    if use_sharded:
        return get_state_sharded, set_state_sharded, delete_state_sharded
    else:
        return get_state, set_state, delete_state


def run_langgraph(initial_state: Dict[str, Any],
                  session_id: Optional[str] = None,
                  use_sharded: bool = True) -> Dict[str, Any]:
    """
    带记忆的 LangGraph 流程主执行函数。
    集成了分布式锁、Redis状态持久化、Pub/Sub事件通知和异常处理。

    参数:
      initial_state: 包含流程初始数据的字典，必须有 "topic"。
                     也可能包含 "output_dir", "output_options" 等。
      session_id: 可选的会话ID。若不提供，则自动生成。
      use_sharded: 是否使用分片方式在 Redis 中存储会话状态，默认为 True。

    返回:
      包含最终状态的字典。若执行失败，则包含 "error" 字段。
    """
    get_state_func, set_state_func, _ = _get_state_persister(use_sharded)
    current_state: StateSchema = {}  # 初始化为 TypedDict 兼容的空字典

    # --- 步骤 1: 会话管理 (加载或新建) ---
    if session_id:
        logger.info(f"[Session={session_id}] 尝试加载现有会话状态 (use_sharded={use_sharded})。")
        loaded_s = get_state_func(session_id)
        current_state = loaded_s if loaded_s is not None else {}
        if current_state:
            logger.info(f"[Session={session_id}] 已成功加载状态。")
        else:
            logger.info(f"[Session={session_id}] 未找到现有状态，将创建新会话。")
    else:
        session_id = str(uuid.uuid4())
        logger.info(f"[Session={session_id}] 无提供 session_id，已生成新会话ID。")
        current_state = {}  # 新会话，空状态开始

    # 合并初始输入到当前状态，并确保 _session_id 正确设置
    current_state.update(initial_state)
    current_state["_session_id"] = session_id  # 确保 _session_id 传递给 Agent

    # --- 步骤 2: 获取分布式锁 ---
    logger.debug(f"[Session={session_id}] 尝试获取分布式锁...")
    lock_id = acquire_lock(session_id, timeout=600, wait=10)  # timeout 10分钟，等待10秒
    if not lock_id:
        error_msg = "会话正在执行，请稍后重试"
        logger.warning(f"[Session={session_id}] 获取锁失败 => {error_msg}")
        # 即使获取锁失败，也应返回包含 _session_id 的标准错误结构
        return {"_session_id": session_id, "error": error_msg}

    logger.info(f"[Session={session_id}] 已成功获取分布式锁，Lock ID: {lock_id}")

    # 定义 Pub/Sub 通道
    pubsub_channel = f"channel:session:{session_id}"

    try:
        # --- 步骤 3: 校验必要输入 (如 'topic') ---
        if "topic" not in current_state or not current_state.get("topic"):
            # 此处 topic 必须存在，否则流程无法开始
            logger.error(f"[Session={session_id}] 初始状态中缺少 'topic'。")
            raise ValueError("初始状态中必须包含 'topic' 字段才能启动流程。")

        # --- 步骤 4: 发布 "ALL START" 事件到 Pub/Sub ---
        start_event_payload = {
            "session_id": session_id, "node": "ALL", "status": "START",
            "timestamp": int(time.time() * 1000),
            "topic": current_state.get("topic")  # 附带主题信息
        }
        _pubsub.publish(pubsub_channel, json.dumps(start_event_payload))
        logger.info(f"[Session={session_id}] 已发布 'ALL START' 事件到频道 {pubsub_channel}。")

        # --- 步骤 5: 构建图实例并执行 ---
        logger.debug(f"[Session={session_id}] 开始构建 LangGraph (带记忆模式)...")
        graph = build_graph_with_memory()  # 获取图实例
        runnable = graph.compile()  # 编译图为可执行对象
        logger.info(f"[Session={session_id}] LangGraph 构建并编译完成，准备执行 invoke。")
        logger.debug(f"[Session={session_id}] 传递给 invoke 的状态: {current_state}")

        final_state: StateSchema = runnable.invoke(current_state)  # 执行图
        logger.info(f"[Session={session_id}] LangGraph 流程执行完毕。")
        logger.debug(f"[Session={session_id}] 从 invoke 返回的最终状态: {final_state}")

        # --- 步骤 5.1: 发布 "ALL COMPLETE" 事件 ---
        complete_event_payload = {
            "session_id": session_id, "node": "ALL", "status": "COMPLETE",
            "timestamp": int(time.time() * 1000),
            "report_paths": final_state.get("report_paths"),  # 附带报告路径
            "audio_path": final_state.get("audio_path")  # 附带音频路径
        }
        _pubsub.publish(pubsub_channel, json.dumps(complete_event_payload))
        logger.info(f"[Session={session_id}] 已发布 'ALL COMPLETE' 事件。")

        # --- 步骤 6: 持久化最终状态到 Redis ---
        set_state_func(session_id, final_state)  # 使用选择的存取函数
        logger.info(f"[Session={session_id}] 最终状态已持久化到 Redis (use_sharded={use_sharded})。")

        # --- 步骤 7: 准备并返回结果 ---
        # 确保返回的字典中包含 _session_id，即使 final_state 中可能没有（理论上应该有）
        response = dict(final_state)
        if "_session_id" not in response:
            response["_session_id"] = session_id
        return response

    except Exception as ex:
        error_message = str(ex)
        logger.error(f"[Session={session_id}] LangGraph 流程执行中发生异常: {error_message}", exc_info=True)

        # 发布 "ALL ERROR" 事件
        error_event_payload = {
            "session_id": session_id, "node": "ALL", "status": "ERROR",
            "error": error_message, "timestamp": int(time.time() * 1000)
        }
        _pubsub.publish(pubsub_channel, json.dumps(error_event_payload))
        logger.info(f"[Session={session_id}] 已发布 'ALL ERROR' 事件。")

        # 将错误信息保存到当前状态并持久化
        current_state_with_error = current_state.copy()  # 基于捕获异常时的 current_state
        current_state_with_error["error"] = error_message
        set_state_func(session_id, current_state_with_error)  # 持久化带错误信息的状态
        logger.info(f"[Session={session_id}] 带错误信息的状态已持久化。")

        return {"_session_id": session_id, "error": error_message}

    finally:
        # --- 步骤 8: 释放锁 ---
        if lock_id:  # 只有成功获取了锁才需要释放
            released = release_lock(session_id, lock_id)
            if released:
                logger.info(f"[Session={session_id}] 分布式锁已成功释放。")
            else:
                # 这可能意味着锁已超时被自动释放，或者尝试释放了不属于自己的锁（罕见）
                logger.warning(f"[Session={session_id}] 锁释放失败或锁已超时。")


def get_existing_state(session_id: str, use_sharded: bool = True) -> Optional[Dict[str, Any]]:
    """从 Redis 获取指定会话的已存状态。"""
    get_state_func, _, _ = _get_state_persister(use_sharded)
    logger.debug(f"查询会话 {session_id} 的现有状态 (use_sharded={use_sharded})。")
    return get_state_func(session_id)


def reset_session(session_id: str, use_sharded: bool = True) -> None:
    """删除 Redis 中指定会话的所有状态数据。"""
    _, _, delete_state_func = _get_state_persister(use_sharded)
    delete_state_func(session_id)
    logger.info(f"会话 {session_id} (use_sharded={use_sharded}) 的状态数据已重置。")