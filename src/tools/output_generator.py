# 文件路径: src/tools/output_generator.py
# -*- coding: utf-8 -*-
"""
OutputGenerator：将 Markdown 内容导出为 TXT、PDF、PPTX，并返回对应路径。
"""
import os
import aiofiles
import markdown2
import pdfkit # type: ignore
from python_pptx import Presentation
from io import BytesIO # Not strictly used in this version, but good for future memory stream handling
from typing import Dict, Any # Ensure Dict and Any are imported
import logging

logger = logging.getLogger(__name__)

class OutputGenerator:
    def __init__(self, config: Dict[str, Any]):
        """
        config:
          - output_dir: 输出目录（相对或绝对路径）
        """
        self.output_dir = config.get("output_dir", "outputs") # Default to "outputs"
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            logger.info(f"输出目录 '{self.output_dir}' 已确保存在。")
        except OSError as e:
            logger.error(f"创建输出目录 '{self.output_dir}' 失败: {e}", exc_info=True)
            # Depending on desired behavior, either raise or set a default fallback
            raise # Raising error as directory is crucial

    async def to_text(self, md: str) -> str:
        """
        将 Markdown 转为纯文本（去掉标记），并写入 .txt 文件。
        """
        txt_path = os.path.join(self.output_dir, "report.txt")
        logger.info(f"准备将 Markdown 转换为 TXT: {txt_path}")
        try:
            # 当前实现直接写入 Markdown 内容作为 TXT。
            # 若需剥离 Markdown 标记，可使用 markdown2 转 html 后再处理，或使用其他库。
            # html_content = markdown2.markdown(md, extras=["fenced-code-blocks", "tables"])
            # text_content = BeautifulSoup(html_content, "html.parser").get_text() # Example with BeautifulSoup
            async with aiofiles.open(txt_path, "w", encoding="utf-8") as f:
                await f.write(md) # Simplified: writing MD as TXT
            logger.info(f"TXT 文件已成功保存至: {txt_path}")
            return txt_path
        except Exception as e:
            logger.error(f"保存 TXT 文件失败 ({txt_path}): {e}", exc_info=True)
            raise

    async def to_markdown(self, md: str) -> str:
        """
        直接输出 Markdown 文件（.md）。
        """
        md_path = os.path.join(self.output_dir, "report.md")
        logger.info(f"准备保存 Markdown 文件: {md_path}")
        try:
            async with aiofiles.open(md_path, "w", encoding="utf-8") as f:
                await f.write(md)
            logger.info(f"Markdown 文件已成功保存至: {md_path}")
            return md_path
        except Exception as e:
            logger.error(f"保存 Markdown 文件失败 ({md_path}): {e}", exc_info=True)
            raise

    async def to_pdf(self, md: str) -> str:
        """
        将 Markdown 转为 HTML，再调用 pdfkit 生成 PDF。
        依赖：系统需安装 wkhtmltopdf。
        """
        pdf_path = os.path.join(self.output_dir, "report.pdf")
        logger.info(f"准备将 Markdown 转换为 PDF: {pdf_path}")
        try:
            # 将 md 转为 HTML
            html = markdown2.markdown(md, extras=["fenced-code-blocks", "tables", "footnotes", "header-ids", "smarty-pants"])

            # pdfkit 选项
            options = {
                'encoding': "UTF-8",
                'custom-header': [
                    ('Content-Encoding', 'utf-8'),
                ],
                'no-outline': None, # 禁用大纲
                'quiet': '' # 减少控制台输出
            }

            pdfkit.from_string(html, pdf_path, options=options)
            logger.info(f"PDF 文件已成功生成至: {pdf_path}")
            return pdf_path
        except FileNotFoundError as e:
            logger.error(f"生成 PDF 文件失败 ({pdf_path}): wkhtmltopdf 未找到或未正确安装。请确保它在系统 PATH 中。错误: {e}", exc_info=True)
            raise RuntimeError(f"wkhtmltopdf not found. Please install it and ensure it's in your PATH. Original error: {e}")
        except Exception as e:
            logger.error(f"生成 PDF 文件失败 ({pdf_path}): {e}", exc_info=True)
            # Provide more specific error message if it's an OSError related to wkhtmltopdf
            if isinstance(e, OSError) and "No such file or directory" in str(e) and "wkhtmltopdf" in str(e):
                 raise RuntimeError(f"wkhtmltopdf execution failed. Is it installed and in PATH? Original error: {e}")
            raise

    async def to_ppt(self, ppt_json: Dict[str, Any]) -> str:
        """
        将自定义的 ppt_json（包含 title 和 slides 列表）转换为 PPTX。
        ppt_json 结构示例：
        {
          "title": "报告标题",
          "slides": [
            {"heading": "第一张幻灯片标题", "content": "要点1\n要点2\n..."},
            ...
          ]
        }
        """
        ppt_path = os.path.join(self.output_dir, "report.pptx")
        logger.info(f"准备从 JSON 生成 PPTX: {ppt_path}")
        try:
            prs = Presentation()
            # 封面幻灯片 (版式0: 标题幻灯片)
            slide_layout_title = prs.slide_layouts[0]
            slide = prs.slides.add_slide(slide_layout_title)
            title_shape = slide.shapes.title
            subtitle_shape = slide.placeholders.get(1) # 通常 placeholder 1 是副标题

            title_shape.text = ppt_json.get("title", "演示文稿")
            if subtitle_shape:
                # Можно добавить подзаголовок или оставить пустым
                # subtitle_shape.text = ppt_json.get("subtitle", "自动生成")
                subtitle_shape.text = ""


            # 内容幻灯片 (版式1: 标题和内容)
            slide_layout_content = prs.slide_layouts[1]
            for slide_info in ppt_json.get("slides", []):
                slide = prs.slides.add_slide(slide_layout_content)
                title_shape = slide.shapes.title
                body_shape = slide.shapes.placeholders[1] # Placeholder for content

                title_shape.text = slide_info.get("heading", "内容页")

                tf = body_shape.text_frame
                tf.clear() # 清除默认文本

                content_text = slide_info.get("content", "")
                # 按行分割内容并添加到段落
                for line in content_text.split('\n'): # 支持
 作为换行符
                    p = tf.add_paragraph()
                    p.text = line.strip()

            prs.save(ppt_path)
            logger.info(f"PPTX 文件已成功生成至: {ppt_path}")
            return ppt_path
        except Exception as e:
            logger.error(f"生成 PPTX 文件失败 ({ppt_path}): {e}", exc_info=True)
            raise
