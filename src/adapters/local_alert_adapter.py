# 文件路径：src/adapters/local_alert_adapter.py
# -*- coding: utf-8 -*-
"""
本地告警适配器：当 ALERT_PROVIDER='local' 时调用
—— 通过 SMTP 发送邮件告警；若 SMTP 未配置或收件人列表为空，则在控制台打印 Warning 日志。
"""

import smtplib
import logging
from email.mime.text import MIMEText
from typing import List

# 修复：从 settings 导入 ALERT_EMAIL_LIST
from src.config.settings import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, ALERT_EMAIL_LIST

logger = logging.getLogger(__name__)

class LocalAlertAdapter:
    """
    本地告警实现类：
    - send_email(subject, content, to_addrs): 使用 SMTP 发送纯文本邮件
    - notify(subject, content): 统一调用入口，使用预定义收件人列表发送告警邮件
    """

    @staticmethod
    def send_email(subject: str, content: str, to_addrs: List[str]):
        """
        使用 SMTP 发送告警邮件。
        参数：
          subject: 邮件主题
          content: 邮件正文（纯文本）
          to_addrs: 收件人列表
        若 SMTP_USER/SMTP_PASSWORD/SMTP_SERVER 未配置或 to_addrs 为空，则仅记录 Warning 日志，跳过发送。
        """
        # 检查 SMTP 及收件人是否配置完整
        if SMTP_SERVER and SMTP_PORT and SMTP_USER and SMTP_PASSWORD and to_addrs:
            msg = MIMEText(content, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER
            msg["To"] = ", ".join(to_addrs)

            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                    server.ehlo()
                    # 如果 SMTP 支持 STARTTLS，则启用加密
                    if server.has_extn("STARTTLS"):
                        server.starttls()
                        server.ehlo()
                    server.login(SMTP_USER, SMTP_PASSWORD)
                    server.sendmail(SMTP_USER, to_addrs, msg.as_string())
                logger.info(f"[LocalAlertAdapter] 邮件告警已发送 → 主题: {subject}, 收件人: {to_addrs}")
            except Exception as e:
                logger.error(f"[LocalAlertAdapter] 发送邮件告警失败 → 主题: {subject}, 异常: {e}", exc_info=True)
        else:
            # 修改日志信息，明确指出是配置不完整或收件人列表为空
            if not to_addrs:
                logger.warning(
                    f"[LocalAlertAdapter][告警跳过] 邮件收件人列表 (ALERT_EMAIL_LIST) 为空。主题: {subject}"
                )
            else:
                logger.warning(
                    f"[LocalAlertAdapter][告警跳过] SMTP 邮件配置不完整。主题: {subject}"
                )


    @staticmethod
    def notify(subject: str, content: str):
        """
        统一调用入口：将告警邮件发送给默认收件人列表。
        修复：不再硬编码收件人，而是从 settings 中读取 ALERT_EMAIL_LIST。
        """
        # 从 settings 中读取收件人列表
        to_addrs = ALERT_EMAIL_LIST
        logger.info(f"[LocalAlertAdapter] 准备发送邮件告警 → 主题: {subject}, 目标收件人: {to_addrs}")
        LocalAlertAdapter.send_email(subject, content, to_addrs)