# 文件路径：src/adapters/dingtalk_adapter.py
# -*- coding: utf-8 -*-
"""
钉钉告警适配器：封装 dingtalkchatbot 库调用，支持文本消息发送与 @ 特定成员或 @ 所有人。
若 DingtalkChatbot 库未安装或 DINGTALK_WEBHOOK 未配置，则回退到控制台打印警告。
"""

import logging
from typing import List, Optional

try:
    from dingtalkchatbot.chatbot import DingtalkChatbot
except ImportError:
    DingtalkChatbot = None  # 若库未安装，则放弃初始化

from src.config.settings import DINGTALK_WEBHOOK, DINGTALK_SECRET

logger = logging.getLogger(__name__)

# 全局钉钉机器人对象，首次调用时初始化
_bot: Optional[DingtalkChatbot] = None
_initialized = False

def _get_dingtalk_bot() -> Optional[DingtalkChatbot]:
    """
    内部函数：初始化并返回 DingtalkChatbot 实例
    - 若 DingtalkChatbot 库未安装或 DINGTALK_WEBHOOK 为空，则返回 None
    - 加签模式：自动计算 timestamp + 签名参数
    """
    global _bot, _initialized
    if not _initialized:
        _initialized = True
        if DingtalkChatbot is None:
            logger.error("钉钉告警库 dingtalkchatbot 未安装，无法发送钉钉消息。")
            return None

        if not DINGTALK_WEBHOOK:
            logger.warning("未配置 DINGTALK_WEBHOOK，钉钉告警功能不可用。")
            return None

        try:
            if DINGTALK_SECRET:
                # 加签模式
                _bot = DingtalkChatbot(DINGTALK_WEBHOOK, secret=DINGTALK_SECRET)
            else:
                # 无加签
                _bot = DingtalkChatbot(DINGTALK_WEBHOOK)
            logger.info("钉钉告警机器人已初始化。")
        except Exception as e:
            logger.error(f"钉钉机器人初始化失败：{e}", exc_info=True)
            _bot = None

    return _bot

def send_dingbot_text(content: str, at_mobiles: Optional[List[str]] = None, is_at_all: bool = False):
    """
    发送钉钉文本告警消息
    参数：
      content: 消息正文
      at_mobiles: 需@的手机号列表（可选）
      is_at_all: 是否@所有人
    若机器人未初始化，则在控制台打印警告并退出。
    """
    bot = _get_dingtalk_bot()
    if not bot:
        logger.warning(f"[DingTalk 告警跳过] 钉钉机器人不可用。消息内容: {content}")
        print(f"[DingTalk 告警回退] {content}")
        return

    try:
        mobile_list = at_mobiles if at_mobiles is not None else []
        bot.send_text(msg=content, at_mobiles=mobile_list, is_at_all=is_at_all)
        logger.info(f"[DingTalk 告警] 消息发送成功: {content}")
    except Exception as e:
        logger.error(f"[DingTalk 告警] 消息发送失败: {e}", exc_info=True)
        print(f"[DingTalk 告警失败回退] {content}")