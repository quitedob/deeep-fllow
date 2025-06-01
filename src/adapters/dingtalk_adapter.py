# src/adapters/dingtalk_adapter.py
# -*- coding: utf-8 -*-
"""
使用 dingtalkchatbot 库发送钉钉告警，封装发送函数。
"""
# This assumes dingtalkchatbot is or will be in requirements.txt
try:
    from dingtalkchatbot.chatbot import DingtalkChatbot
except ImportError:
    DingtalkChatbot = None # Allow module to load if library not installed, but functions will fail gracefully.

import logging # For logging
from src.config.settings import DINGTALK_WEBHOOK, DINGTALK_SECRET # Ensure this path is correct
from typing import List, Optional # For type hinting

logger = logging.getLogger(__name__)

# 初始化钉钉机器人
# Initialize bot to None. It will be created when first needed if DingtalkChatbot is available.
bot: Optional[DingtalkChatbot] = None
_bot_initialized = False

def _get_dingtalk_bot() -> Optional[DingtalkChatbot]:
    global bot, _bot_initialized
    if not _bot_initialized:
        _bot_initialized = True # Set true at the start of initialization attempt
        if DingtalkChatbot is None:
            logger.error("DingtalkChatbot library is not installed. Please install it to use DingTalk adapter.")
            # bot remains None
        elif DINGTALK_WEBHOOK:
            try:
                if DINGTALK_SECRET:
                    bot = DingtalkChatbot(DINGTALK_WEBHOOK, secret=DINGTALK_SECRET)
                else:
                    bot = DingtalkChatbot(DINGTALK_WEBHOOK)
                logger.info("DingtalkChatbot initialized.")
            except Exception as e:
                logger.error(f"Failed to initialize DingtalkChatbot: {e}", exc_info=True)
                bot = None # Ensure bot is None if initialization fails
        else:
            logger.warning("DINGTALK_WEBHOOK not configured. DingtalkChatbot will not be initialized.")
            # bot remains None
    return bot

def send_dingbot_text(content: str, at_mobiles: Optional[List[str]] = None, is_at_all: bool = False):
    """
    通过 DingtalkChatbot 发送文本消息
    - content: 消息文本
    - at_mobiles: 列表，若需@特定用户，传入手机号列表
    - is_at_all: 是否@所有人
    """
    current_bot = _get_dingtalk_bot()
    if not current_bot:
        logger.warning(f"[DINGTALK ADAPTER SKIPPED] DingtalkChatbot not available or not configured. Message: {content}")
        # Fallback to console print if bot is not available
        print(f"[DINGTALK ADAPTER FALLBACK (bot not configured/failed)][ALERT] {content}")
        return

    try:
        # Ensure at_mobiles is a list, even if None is passed.
        at_mobiles_list = at_mobiles if at_mobiles is not None else []
        current_bot.send_text(msg=content, at_mobiles=at_mobiles_list, is_at_all=is_at_all)
        logger.info(f"[DINGTALK ADAPTER] 消息发送成功: {content}")
    except Exception as e:
        logger.error(f"[DINGTALK ADAPTER] 消息发送失败: {e}", exc_info=True)
