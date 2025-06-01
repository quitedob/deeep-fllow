# 文件路径: src/tools/ppt_generator.py
# -*- coding: utf-8 -*-
"""
PPT 生成独立模块（供 OutputGenerator 调用）。
如果有更复杂需求，可在此扩展。
"""
from python_pptx import Presentation
from python_pptx.util import Inches, Pt # For setting dimensions and font sizes if needed
from typing import Dict, Any # Ensure Dict and Any are imported
import logging

logger = logging.getLogger(__name__)

def generate_ppt_from_json(ppt_json: Dict[str, Any], output_path: str) -> str:
    """
    参考 OutputGenerator 中的 PPT 生成逻辑，
    该函数独立出来方便后续扩展或直接调用。

    ppt_json 结构示例：
    {
      "title": "报告标题",
      "subtitle": "副标题（可选）", // 新增副标题字段
      "slides": [
        {"heading": "第一张幻灯片标题", "content": "要点1\n要点2\n..."},
        ...
      ]
    }
    """
    logger.info(f"开始从 JSON 生成 PPTX 至路径: {output_path}")
    try:
        prs = Presentation()

        # 幻灯片版式参考 (可以根据实际 .pptx 模板调整索引):
        # 0: 标题幻灯片 (Title Slide)
        # 1: 标题和内容 (Title and Content)
        # 2: 节标题 (Section Header)
        # 3: 两栏内容 (Two Content)
        # 4: 比较 (Comparison)
        # 5: 仅标题 (Title Only)
        # 6: 空白 (Blank)
        # 7: 内容与说明 (Content with Caption)
        # 8: 图片与说明 (Picture with Caption)

        # 封面幻灯片 (使用版式 0)
        title_slide_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_slide_layout)

        title_shape = slide.shapes.title
        # 副标题通常是第一个占位符 (index 1)
        subtitle_shape = slide.placeholders.get(1)

        title_shape.text = ppt_json.get("title", "演示文稿")
        if subtitle_shape:
            subtitle_shape.text = ppt_json.get("subtitle", "") # 使用 ppt_json 中的副标题

        # 内容幻灯片 (使用版式 1: 标题和内容)
        content_slide_layout = prs.slide_layouts[1]
        for slide_info in ppt_json.get("slides", []):
            slide = prs.slides.add_slide(content_slide_layout)

            title_shape = slide.shapes.title
            # 内容区通常是第一个非标题占位符 (index 1 for layout 1)
            body_shape = slide.placeholders[1]

            title_shape.text = slide_info.get("heading", "内容页")

            tf = body_shape.text_frame
            tf.clear()  # 清除可能存在的默认文本

            content_text = slide_info.get("content", "")
            # 按行分割内容并添加到段落, 支持 `\n` 作为换行
            for line in content_text.split('\n'):
                p = tf.add_paragraph()
                p.text = line.strip()
                # p.font.size = Pt(18) # 可选：设置字体大小

        prs.save(output_path)
        logger.info(f"PPTX 文件已成功生成: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"从 JSON 生成 PPTX 文件失败 ({output_path}): {e}", exc_info=True)
        raise # Re-raise the exception to be handled by the caller
