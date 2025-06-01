# 文件路径: src/agents/reporter_agent.py
# -*- coding: utf-8 -*-
"""
Reporter Agent：将 plan 中所有任务的检索结果与代码执行结果
整理为 Markdown，并调用 OutputGenerator 生成 TXT/PDF/PPT。
"""
import os
import asyncio
import json
import aiofiles # 修复：导入 aiofiles
from typing import Dict, Any, List
from src.tools.output_generator import OutputGenerator
import logging

logger = logging.getLogger(__name__)

async def run_reporter(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入：
      - plan: 包含 tasks，每个 task 中可能有 "results" 列表与 "code_result"
              以及 "output_dir" 和 "output_options"
    输出：
      - plan: 添加 "report_paths" 字段
    """
    topic = plan.get("topic", "未知主题")
    tasks: List[Dict[str, Any]] = plan.get("tasks", [])
    # 修复：确保与 main.py 和 planner.py 的默认值和键名一致
    output_options = plan.get("output_options", ["md", "txt", "pdf", "ppt"]) # audio 由 voice agent 处理
    output_dir = plan.get("output_dir", "outputs")

    logger.info(f"Reporter Agent：开始为主题「{topic}」生成报告。输出选项: {output_options}")

    # 1. 拼接 Markdown 文本
    md_lines = []
    md_lines.append(f"# 研究报告：{topic}\n\n")
    for i, task in enumerate(tasks, 1):
        name = task.get("name", f"子任务 {i}")
        md_lines.append(f"## {i}. {name}\n\n")

        results = task.get("results", [])
        if results:
            md_lines.append("### 检索结果：\n")
            for idx, r in enumerate(results, 1):
                title = r.get("title", "无标题")
                url = r.get("url", "#")
                source = r.get("source", "未知来源")
                score = r.get("score", 0.0)
                content_snippet = r.get("content", "无内容").replace("\n", " ").strip()
                content_display = (content_snippet[:150] + '...') if len(content_snippet) > 150 else content_snippet
                md_lines.append(f"{idx}. **{title}**\n")
                md_lines.append(f"   - **来源**: {source}\n")
                md_lines.append(f"   - **链接**: [{url}]({url})\n")
                md_lines.append(f"   - **相关性分数**: {score:.2f}\n")
                md_lines.append(f"   - **摘要**: {content_display}\n\n")
        else:
            md_lines.append("本任务无检索结果。\n\n")

        code_to_execute = task.get("code", "").strip()
        code_res = task.get("code_result", {})
        if code_to_execute:
            md_lines.append("### 代码执行详情：\n")
            md_lines.append("```python\n")
            md_lines.append(code_to_execute + "\n")
            md_lines.append("```\n\n")
            if code_res:
                stdout = code_res.get("stdout", "")
                stderr = code_res.get("stderr", "")
                returncode = code_res.get("returncode", None)
                if stdout:
                    md_lines.append("#### 输出：\n```text\n")
                    md_lines.append(stdout.strip() + "\n```\n\n")
                if stderr:
                    md_lines.append("#### 错误：\n```text\n")
                    md_lines.append(stderr.strip() + "\n```\n\n")
                md_lines.append(f"- **代码返回值**：`{returncode}`\n\n")
            else:
                md_lines.append("此任务中的代码未执行或无结果。\n\n")
        elif "code_result" in task and not code_to_execute:
             md_lines.append("此任务未提供可执行代码。\n\n")

    markdown_content = "".join(md_lines)
    logger.debug(f"生成的Markdown内容:\n{markdown_content[:500]}...")

    # 2. 确保输出目录存在
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"创建输出目录 '{output_dir}' 失败: {e}")
        plan["report_paths"] = {"error": f"创建输出目录失败: {e}"}
        return plan

    # 3. 调用 OutputGenerator 逐个生成文件
    og_config = {"output_dir": output_dir}
    og = OutputGenerator(og_config)
    generated_paths: Dict[str, str] = {}

    # 修复：在 to_markdown 中使用 aiofiles
    try:
        if "md" in output_options:
            md_path = await og.to_markdown(markdown_content)
            generated_paths["md"] = md_path
            logger.info(f"Markdown报告已生成：{md_path}")
    except Exception as e:
        logger.error(f"生成Markdown文件失败: {e}")
        generated_paths["md"] = f"错误: {e}"

    try:
        if "txt" in output_options:
            txt_path = await og.to_text(markdown_content)
            generated_paths["txt"] = txt_path
            logger.info(f"纯文本报告已生成：{txt_path}")
    except Exception as e:
        logger.error(f"生成TXT文件失败: {e}")
        generated_paths["txt"] = f"错误: {e}"

    try:
        if "pdf" in output_options:
            pdf_path = await og.to_pdf(markdown_content)
            generated_paths["pdf"] = pdf_path
            logger.info(f"PDF报告已生成：{pdf_path}")
    except Exception as e:
        logger.error(f"生成PDF文件失败: {e}")
        generated_paths["pdf"] = f"错误: {e}"

    try:
        if "ppt" in output_options:
            ppt_json_slides = []
            for task in tasks:
                heading = task.get("name", "子任务")
                slide_content_lines = []
                task_results = task.get("results", [])
                if task_results:
                    slide_content_lines.append("主要发现：")
                    for r_idx, r in enumerate(task_results[:3],1):
                        slide_content_lines.append(f"  {r_idx}. {r.get('title', '无标题')}")
                if task.get("code_result", {}).get('stdout'):
                    slide_content_lines.append("\n代码执行概要：请参阅详细报告。")
                elif task.get("code","").strip():
                     slide_content_lines.append("\n代码片段：请参阅详细报告。")

                if not slide_content_lines:
                    slide_content_lines.append("此任务无关键信息摘要。")

                ppt_json_slides.append({"heading": heading, "content": "\n".join(slide_content_lines)})

            ppt_data_for_generator = {"title": f"研究报告：{topic}", "slides": ppt_json_slides}
            logger.debug(f"传递给PPT生成器的JSON: {json.dumps(ppt_data_for_generator, indent=2, ensure_ascii=False)}")

            ppt_path = await og.to_ppt(ppt_data_for_generator)
            generated_paths["ppt"] = ppt_path
            logger.info(f"PPT报告已生成：{ppt_path}")
    except Exception as e:
        logger.error(f"生成PPT文件失败: {e}", exc_info=True)
        generated_paths["ppt"] = f"错误: {e}"

    # 4. 将路径写回 plan
    plan["report_paths"] = generated_paths
    logger.info(f"Reporter Agent：报告生成完成，路径已更新：{generated_paths}")

    return plan