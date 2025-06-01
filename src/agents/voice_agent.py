# 文件路径: src/agents/voice_agent.py
# -*- coding: utf-8 -*-
"""
Voice Agent：将最终报告文本通过 gTTS 转为 MP3，写入指定输出目录。
"""
import os
import asyncio
import aiofiles # 修复：导入 aiofiles
from gtts import gTTS
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


async def run_voice(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入：
      - plan: 包含 "report_paths" 字段，至少要有 plan["report_paths"]["txt"]
              以及 "output_dir"
    输出：
      - plan: 添加 "audio_path" 字段
    """
    report_paths = plan.get("report_paths", {})
    txt_path = report_paths.get("txt", "")
    output_dir = plan.get("output_dir", "outputs")

    plan["audio_path"] = ""

    # 检查是否需要在本次运行中生成音频
    if "audio" not in plan.get("output_options", []):
        logger.info("Voice Agent：根据输出选项，本次运行无需生成音频。")
        return plan

    if not txt_path or not os.path.exists(txt_path):
        logger.warning("Voice Agent：未找到纯文本报告或路径无效，无法生成音频。")
        return plan

    logger.info(f"Voice Agent：开始处理文本报告「{txt_path}」以生成语音。")

    try:
        # 修复：使用 aiofiles 异步读取文件内容
        async with aiofiles.open(txt_path, "r", encoding="utf-8") as f:
            text_content = await f.read()
    except Exception as e:
        logger.error(f"Voice Agent：读取文本文件「{txt_path}」失败：{e}")
        return plan

    if not text_content.strip():
        logger.warning("Voice Agent：文本报告内容为空，跳过语音合成。")
        return plan

    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        logger.error(f"Voice Agent：创建输出目录「{output_dir}」失败：{e}")
        return plan

    topic_slug = "".join(c if c.isalnum() else "_" for c in plan.get("topic", "report"))[:50]
    audio_filename = f"{topic_slug}_audio.mp3"
    audio_path = os.path.join(output_dir, audio_filename)

    try:
        logger.info("Voice Agent：开始使用gTTS合成语音，这可能需要一些时间...")

        loop = asyncio.get_running_loop()

        def generate_audio_sync():
            tts = gTTS(text=text_content, lang="zh-cn", slow=False)
            tts.save(audio_path)

        await loop.run_in_executor(None, generate_audio_sync)

        plan["audio_path"] = audio_path
        logger.info(f"Voice Agent：语音合成完成，音频文件已保存至「{audio_path}」。")
    except Exception as e:
        logger.error(f"Voice Agent：使用gTTS进行语音合成失败：{e}", exc_info=True)

    return plan