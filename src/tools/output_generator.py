# -*- coding: utf-8 -*-
# 专用于生成各种格式报告文件的工具类

import os
import json
import re
import asyncio
from datetime import datetime
from pathlib import Path

# 引入新依赖库
import aiofiles
import markdown2
from bs4 import BeautifulSoup
import pdfkit
from gtts import gTTS  # 新增：导入gTTS

from src.config.configuration import Configuration
from src.tools.ppt_generator import generate_ppt_from_json


class OutputGenerator:
    """
    一个负责根据内容生成不同格式文件的类。
    包含了异步文件写入、精准文本提取等优化。
    简化注释：报告文件生成器
    """

    def __init__(self, config: Configuration):
        """
        初始化生成器，并从配置中读取输出目录。
        """
        self.config = config
        self.output_dir = Path(config.output_dir).resolve()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    async def to_text(self, markdown_content: str) -> str:
        """
        将Markdown内容转换为纯文本并异步写入文件。
        简化注释：生成TXT文件
        """
        path = self.output_dir / f"report_{self.timestamp}.txt"
        try:
            html = markdown2.markdown(markdown_content)
            soup = BeautifulSoup(html, "lxml")
            plain_text = soup.get_text(separator="\n", strip=True)

            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(plain_text)

            print(f"--- [输出生成器] 已生成纯文本文件: {path} ---")
            return str(path)
        except Exception as e:
            error_msg = f"生成TXT时出错: {e}"
            print(f"--- [输出生成器] {error_msg} ---")
            return error_msg

    async def to_markdown(self, markdown_content: str) -> str:
        """
        将Markdown内容异步写入文件。
        简化注释：生成MD文件
        """
        path = self.output_dir / f"report_{self.timestamp}.md"
        try:
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(markdown_content)
            print(f"--- [输出生成器] 已生成 Markdown 文件: {path} ---")
            return str(path)
        except Exception as e:
            error_msg = f"生成MD时出错: {e}"
            print(f"--- [输出生成器] {error_msg} ---")
            return error_msg

    async def to_pdf(self, markdown_content: str) -> str:
        """
        将Markdown内容转换为PDF并异步写入文件。
        简化注释：生成PDF文件
        """
        path = self.output_dir / f"report_{self.timestamp}.pdf"
        loop = asyncio.get_running_loop()
        try:
            options = {
                'encoding': "UTF-8",
                'custom-header': [('Content-Encoding', 'utf-8')],
                'no-outline': None
            }
            html_content = markdown2.markdown(markdown_content)
            await loop.run_in_executor(
                None,
                lambda: pdfkit.from_string(html_content, str(path), options=options)
            )
            print(f"--- [输出生成器] 已生成 PDF 文件: {path} ---")
            return str(path)
        except Exception as e:
            error_msg = f"生成PDF时出错: {e} (请确保已安装wkhtmltopdf并将其添加到系统PATH)"
            print(f"--- [输出生成器] {error_msg} ---")
            return error_msg

    async def to_ppt(self, ppt_json_str: str) -> str:
        """
        解析PPT的JSON字符串，并调用工具生成PPT文件。
        简化注释：生成PPT文件
        """
        path = self.output_dir / f"report_{self.timestamp}.pptx"
        loop = asyncio.get_running_loop()
        try:
            def process_and_generate():
                json_match = re.search(r"\{[\s\S]*\}", ppt_json_str)
                if not json_match:
                    raise ValueError("未在输入中找到有效的JSON对象")

                cleaned_json_str = json_match.group(0)
                ppt_data = json.loads(cleaned_json_str)
                return generate_ppt_from_json(ppt_data, str(path))

            status = await loop.run_in_executor(None, process_and_generate)
            print(f"--- [输出生成器] {status} ---")
            return str(path)
        except Exception as e:
            error_msg = f"生成PPT时出错: {e}"
            print(f"--- [输出生成器] {error_msg} ---")
            return error_msg

    # 新增：生成播客音频文件的方法
    async def to_podcast_audio(self, podcast_data: dict) -> str:
        """
        根据播客脚本数据生成MP3音频文件。
        简化注释：生成MP3播客文件
        """
        path = self.output_dir / f"podcast_{self.timestamp}.mp3"
        loop = asyncio.get_running_loop()
        try:
            # 1. 拼接完整的播客脚本
            script_text = podcast_data.get('intro', '')
            segments = podcast_data.get('segments', [])
            if segments:
                script_text += "\n" + "\n".join(segments)
            script_text += "\n" + podcast_data.get('outro', '')

            if not script_text.strip():
                raise ValueError("从数据中提取的脚本内容为空。")

            # 2. 定义一个同步的保存函数，以便在线程池中运行
            def save_audio():
                # 语言可以根据需要动态设置，这里默认为中文
                tts = gTTS(text=script_text, lang='zh-cn')
                tts.save(str(path))

            # 3. 在线程池中执行同步的 gTTS 保存操作
            await loop.run_in_executor(None, save_audio)

            print(f"--- [输出生成器] 已生成播客音频文件: {path} ---")
            return str(path)
        except Exception as e:
            error_msg = f"生成播客音频时出错: {e}"
            print(f"--- [输出生成器] {error_msg} ---")
            return error_msg