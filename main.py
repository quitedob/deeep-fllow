# 文件路径: main.py
# -*- coding: utf-8 -*-
"""
项目统一入口，支持 CLI 和 Server 两种模式：
  - CLI 模式：python main.py --query "研究主题" [--output_dir ./my_reports] [--output_options txt pdf]
  - Server 模式：python main.py --serve
"""
import argparse # 命令行参数解析
import asyncio # 异步IO
import logging # 日志
import os # 系统操作
from typing import List, Dict, Any, Optional # 修复：导入 Optional

from src.utils.logging import init_logger # 自定义日志初始化
from src.graph.builder import run_langgraph # LangGraph流程运行函数
# 移除 server app 的直接导入，因为 uvicorn 会自己找
# from src.server.app import app as fastapi_app
from src.config.loader import load_yaml_config # YAML配置加载


logger = logging.getLogger(__name__) # 获取日志记录器

async def run_cli_workflow(topic: str, output_dir_cli: Optional[str], output_options_cli: Optional[List[str]]):
    """
    CLI 模式：直接调用 LangGraph 流程，等待结束后输出结果。
    简化注释：运行CLI模式工作流
    """
    logger.info(f"CLI模式：收到研究主题「{topic}」") # 日志：收到主题

    # 加载 conf.yaml 获取默认输出配置
    # 简化注释：加载配置
    project_root = os.path.dirname(os.path.abspath(__file__)) # 获取项目根目录
    conf_yaml_path = os.path.join(project_root, "conf.yaml") # 构造配置文件路径
    config = load_yaml_config(conf_yaml_path) # 加载YAML配置

    # 优先使用命令行参数，否则使用配置文件或默认值
    # 简化注释：确定输出配置
    final_output_dir = output_dir_cli or config.get("OUTPUT_DIR", "outputs")
    # 修复：从配置文件读取 OUTPUT_OPTIONS
    default_options = config.get("OUTPUT_OPTIONS", ["md", "txt", "pdf", "ppt", "audio"])
    final_output_options = output_options_cli or default_options

    # 准备初始状态
    # 简化注释：准备初始状态
    initial_state: Dict[str, Any] = {
        "topic": topic,
        "tasks": [], # Planner会填充
        "output_dir": final_output_dir, # 输出目录
        "output_options": final_output_options, # 输出格式
        "report_paths": {}, # Reporter会填充
        "audio_path": ""    # Voice Agent会填充
    }
    logger.debug(f"传递给run_langgraph的初始状态: {initial_state}") # 日志：初始状态

    # 异步执行 LangGraph 流程
    # 简化注释：执行LangGraph
    # run_langgraph 本身可能是同步的，所以用 run_in_executor
    loop = asyncio.get_event_loop() # 获取事件循环
    # 修复：传递正确的初始状态字典
    completed_plan = await loop.run_in_executor(None, run_langgraph, initial_state) # 异步执行

    if completed_plan is None:
        logger.error("CLI模式：LangGraph 流程执行失败。") # 日志：流程失败
        return

    # 输出报告和音频路径
    # 简化注释：输出结果路径
    report_paths = completed_plan.get("report_paths", {}) # 获取报告路径
    audio_path = completed_plan.get("audio_path", "") # 获取音频路径

    logger.info("CLI模式：流程执行完毕。结果如下：") # 日志：流程结束
    if report_paths:
        logger.info("  报告文件:") # 日志：报告文件
        for fmt, path in report_paths.items():
            logger.info(f"    - {fmt.upper()}: {path}") # 日志：具体格式路径
    else:
        logger.info("  未生成任何报告文件。") # 日志：无报告

    if audio_path:
        logger.info(f"  音频文件: {audio_path}") # 日志：音频文件
    else:
        logger.info("  未生成音频文件。") # 日志：无音频

def main():
    """
    主函数，解析命令行参数并根据模式执行相应操作。
    简化注释：主函数
    """
    init_logger("INFO") # 初始化日志，级别INFO
    parser = argparse.ArgumentParser(
        description="DeeepFlow LangGraph 项目入口。", # 程序描述
        formatter_class=argparse.RawTextHelpFormatter # 保留换行符的帮助信息格式
    )
    # CLI模式参数
    parser.add_argument(
        "--query", "-q", type=str,
        help="研究主题，用于CLI模式。例如：--query \"人工智能的未来发展\"" # 查询参数
    )
    parser.add_argument(
        "--output_dir", type=str,
        help="指定报告和音频的输出目录 (CLI模式)。默认为 conf.yaml中的OUTPUT_DIR 或 'outputs'。" # 输出目录参数
    )
    parser.add_argument(
        "--output_options", nargs='+',
        choices=["txt", "md", "pdf", "ppt", "audio"],
        help="指定输出文件的格式 (CLI模式)，可多选。例如：--output_options txt pdf audio。默认为 conf.yaml 或全部。" # 输出格式参数
    )
    # Server模式参数
    parser.add_argument(
        "--serve", action="store_true",
        help="启动 FastAPI HTTP 服务。" # 服务模式参数
    )
    parser.add_argument(
        "--host", type=str, default="0.0.0.0",
        help="FastAPI 服务监听的主机地址 (仅当 --serve 时有效)。默认为 0.0.0.0。" # 主机地址参数
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="FastAPI 服务监听的端口号 (仅当 --serve 时有效)。默认为 8000。" # 端口号参数
    )

    args = parser.parse_args() # 解析参数

    if args.serve:
        # Server 模式：启动 FastAPI
        # 简化注释：启动服务器
        try:
            import uvicorn # 动态导入uvicorn
            logger.info(f"服务器模式：启动 FastAPI 服务于 http://{args.host}:{args.port}") # 日志：启动服务
            # 注意：确保 uvicorn.run 的第一个参数是 "module_path:app_instance_name"
            # 此处指向 src.server.app 模块中的 app 实例
            uvicorn.run("src.server.app:app", host=args.host, port=args.port, reload=True) # 运行uvicorn
        except ImportError:
            logger.error("启动服务器失败：uvicorn 未安装。请运行 `pip install uvicorn[standard]`。") # uvicorn未安装错误
        except Exception as e:
            logger.error(f"启动服务器时发生未知错误: {e}", exc_info=True) # 其他启动错误

    elif args.query:
        # CLI 模式：执行 LangGraph
        # 简化注释：运行CLI
        asyncio.run(run_cli_workflow(args.query, args.output_dir, args.output_options)) # 异步运行CLI工作流
    else:
        # 如果没有指定模式，打印帮助信息
        # 简化注释：无参数帮助
        logger.warning("未指定操作模式。请使用 --query 执行CLI研究，或使用 --serve 启动API服务。") # 警告信息
        parser.print_help() # 打印帮助

if __name__ == "__main__":
    main() # 执行主函数