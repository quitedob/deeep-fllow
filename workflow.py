# 文件路径: workflow.py
# -*- coding: utf-8 -*-
# 定义和运行智能体工作流
import json
from typing import Optional, List

# 新增：导入 HumanMessage 用于初始化消息列表
from langchain.schema import HumanMessage
from src.config.configuration import Configuration
from src.graph.builder import graph
from src.tools.output_generator import OutputGenerator  # 导入OutputGenerator


async def run_agent_workflow_async(
        user_input: str,
        max_iterations: int,
        image_path: Optional[str] = None,
        output_options: Optional[List[str]] = None,
        auto_approve: bool = False,  # 新增：接收自动批准标志
):
    """
    异步运行智能体工作流并打印每一步的结果。
    简化注释：异步运行并按需生成报告
    """
    # 1. 创建运行时配置字典，后续会覆盖默认配置
    run_config = {
        "configurable": {
            "max_plan_iterations": max_iterations
            # 可以在这里传递更多运行时参数给 Configuration.from_runnable_config
        }
    }

    # 2. 从配置和运行时参数中创建唯一的Configuration实例
    config_obj = Configuration.from_runnable_config(run_config)

    # 3. 准备图的初始状态，将config对象完整注入
    initial_state = {
        "user_input": user_input,
        "image_path": image_path,
        # 修复：将用户输入作为第一条HumanMessage放入消息列表，以避免后续节点因列表为空而出错
        "messages": [HumanMessage(content=user_input)] if user_input else [],
        "completed_steps": [],
        "research_summary": "",
        "enable_background_investigation": True,
        "output_options": output_options if output_options is not None else ["text"],
        "output_dir": config_obj.output_dir,  # 从统一配置中获取
        "config": config_obj,  # 传递完整的配置对象
        "auto_accepted_plan": auto_approve,  # 新增：设置自动批准状态
        # 初始化报告路径字段
        "txt_path": "未生成",
        "md_path": "未生成",
        "pdf_path": "未生成",
        "ppt_path": "未生成",
        "podcast_path": "未生成",
    }

    # 修复：正确捕获和处理最终状态
    all_events = []
    async for event in graph.astream(initial_state, config=run_config):
        for node_name, node_output in event.items():  # 变量名修改以更清晰
            print(f"--- [节点: {node_name}] ---")
            if isinstance(node_output, dict):
                # 过滤掉一些过长的字段，如消息历史和完整配置
                filtered_value = {k: v for k, v in node_output.items() if
                                  k not in ["messages", "config", "user_input", "research_summary", "final_report",
                                            "md_content"]}
                if filtered_value:  # 只打印非空过滤结果
                    print(filtered_value)
                else:  # 如果过滤后为空，打印原始（部分）输出提示
                    print(f"节点 '{node_name}' 的输出内容较多或为核心数据，不在此处完全显示。")
            else:
                print(node_output)
            print("\n" + "=" * 30 + "\n")
        all_events.append(event)

    final_graph_output = {}  # 初始化最终的图输出
    if all_events:
        last_event = all_events[-1]  # 获取流中的最后一个事件
        # 假设最后一个事件的 value 就是图的最终状态字典
        if last_event and isinstance(last_event, dict):
            final_graph_output = next(iter(last_event.values()), {})

    # 工作流结束后，根据 final_state 中的内容生成报告文件
    if final_graph_output and isinstance(final_graph_output, dict):
        # 实例化 OutputGenerator
        output_gen = OutputGenerator(config=config_obj)
        generated_files = {}

        final_report_content = final_graph_output.get("final_report", "")
        md_content = final_graph_output.get("md_content", final_report_content)
        ppt_json_data = final_graph_output.get("ppt_json_data")  # 修复：直接获取，可能是str或dict
        podcast_data = final_graph_output.get("podcast_data")  # 新增：获取播客数据

        # 检查是否有内容可供生成
        if not md_content and not ppt_json_data and not podcast_data:
            print("--- [报告生成] 未找到可用于生成报告的内容。 ---")
        else:
            requested_outputs = final_graph_output.get("output_options", [])

            if "text" in requested_outputs and md_content:
                generated_files["txt_path"] = await output_gen.to_text(md_content)
            if "md" in requested_outputs and md_content:
                generated_files["md_path"] = await output_gen.to_markdown(md_content)
            if "pdf" in requested_outputs and md_content:
                generated_files["pdf_path"] = await output_gen.to_pdf(md_content)

            # 修复：确保 ppt_json_data 是字符串
            if "ppt" in requested_outputs and ppt_json_data:
                ppt_json_str = json.dumps(ppt_json_data) if isinstance(ppt_json_data, dict) else str(ppt_json_data)
                generated_files["ppt_path"] = await output_gen.to_ppt(ppt_json_str)

            # 新增：处理播客生成
            if "podcast" in requested_outputs and podcast_data:
                if isinstance(podcast_data, dict):
                    generated_files["podcast_path"] = await output_gen.to_podcast_audio(podcast_data)
                else:
                    print(f"--- [报告生成] 播客数据格式不正确，无法生成音频。 ---")

        print("--- [最终报告文件] ---")
        for format_key, path in generated_files.items():
            if path and "未生成" not in path and "错误" not in str(path):
                print(f"{format_key.replace('_path', '').upper()} 文件: {path}")
            elif "错误" in str(path):
                print(f"生成 {format_key.replace('_path', '').upper()} 文件失败: {path}")
        print("\n" + "=" * 30 + "\n")

    else:
        print("--- [工作流] 未能获取最终状态。 ---")