# -*- coding: utf-8 -*-
"""
DeepFlow 项目的入口脚本
"""

import argparse
import asyncio
import sys
from typing import List, Optional
from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator
from src.config.questions import BUILT_IN_QUESTIONS_ZH_CN
from workflow import run_agent_workflow_async


def ask(
        question: str,
        max_iterations: int,
        image_path: Optional[str],
        output_options: Optional[List[str]]
):
    """
    使用给定问题、输出选项和可选图片运行智能体工作流
    简化注释：运行工作流
    """
    if not question and not image_path:
        print("错误：至少需要提供一个问题或一张图片。")
        return

    asyncio.run(
        run_agent_workflow_async(
            user_input=question,
            max_iterations=max_iterations,
            image_path=image_path,
            output_options=output_options,
        )
    )


def main(
        max_iterations: int,
        image_path_from_args: Optional[str],
        output_options_from_args: Optional[List[str]]
):
    """
    带有内置问题的交互模式
    简化注释：交互模式主函数
    """
    questions = BUILT_IN_QUESTIONS_ZH_CN
    ask_own_option = "[自定义问题]"

    try:
        initial_question = inquirer.select(
            message="您想了解什么?",
            choices=[ask_own_option] + questions,
            default=ask_own_option
        ).execute()

        if initial_question == ask_own_option:
            initial_question = inquirer.text(
                message="请输入您的问题:",
                validate=EmptyInputValidator("输入不能为空！")
            ).execute()

        # 优先使用命令行传入的图片路径，否则再询问用户
        image_path = image_path_from_args
        if not image_path:
            image_path = inquirer.text(
                message="请输入图片文件路径 (可选，直接按回车跳过):"
            ).execute()

        # 如果命令行未指定，则在交互模式下询问输出格式
        output_options = output_options_from_args
        if not output_options:
            output_options = inquirer.checkbox(
                message="请选择报告输出格式 (按空格键选中/取消，回车确认):",
                choices=[
                    {"name": "纯文本 (TXT)", "value": "text", "enabled": True},
                    {"name": "Markdown (MD)", "value": "md", "enabled": False},
                    {"name": "PDF", "value": "pdf", "enabled": False},
                    {"name": "演示文稿 (PPT)", "value": "ppt", "enabled": False},
                    {"name": "播客音频 (TTS)", "value": "tts", "enabled": False}, # 新增TTS选项
                ],
                validate=EmptyInputValidator("至少选择一种输出格式！"),
                long_instruction="使用空格键来选中或取消选中一个选项。"
            ).execute()

        ask(
            question=initial_question,
            max_iterations=max_iterations,
            image_path=image_path.strip() if image_path else None,
            output_options=output_options,
        )
    except KeyboardInterrupt:
        print("\n操作已取消，退出程序。")
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="运行 DeepFlow 智能体工作流。",
        usage="python main.py [query...] [--image IMAGE] [--output FORMATS...] [--interactive] [--max_iterations N]",
        epilog="示例:\n"
               "  交互模式: python main.py --interactive\n"
               "  非交互模式: python main.py \"什么是小型语言模型?\"\n"
               "  指定输出格式: python main.py \"什么是小型语言模型?\" --output text pdf ppt tts\n"
               "  带图片查询: python main.py \"详细描述这张图片\" --image ./path/to/image.jpg",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("query", nargs="*", help="要处理的查询（在非交互模式下使用）。")
    parser.add_argument("--image", type=str, help="要分析的图片文件路径。")
    # 修复：在choices中添加 'tts'
    parser.add_argument("--output", nargs="+", choices=["text", "md", "pdf", "ppt", "tts"], help="指定一个或多个输出文件格式。")
    parser.add_argument("--interactive", action="store_true", help="以交互模式运行，忽略 [query] 参数。")
    parser.add_argument("--max_iterations", type=int, default=10, help="工作流最大迭代次数。")

    try:
        args = parser.parse_args()
    except SystemExit:
        # argparse 默认会处理 --help 并退出，这里捕获其他解析错误
        print("\n参数解析失败，请检查您的命令。使用 --help 查看帮助。")
        sys.exit(1)

    if args.interactive:
        # 在交互模式下，将命令行参数传递给 main 函数
        main(
            max_iterations=args.max_iterations,
            image_path_from_args=args.image,
            output_options_from_args=args.output
        )
    else:
        # 非交互模式逻辑
        user_query = " ".join(args.query) if args.query else ""
        if not user_query and not args.image:
            print("错误：在非交互模式下，必须通过命令行提供查询或图片路径。")
            parser.print_help()
            sys.exit(1)

        ask(
            question=user_query,
            max_iterations=args.max_iterations,
            image_path=args.image,
            # 修复：确保即使命令行指定了output，也能正常传递
            output_options=args.output if args.output else ["text"]
        )