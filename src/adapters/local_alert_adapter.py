# src/adapters/local_alert_adapter.py
# -*- coding: utf-8 -*- # Added for consistency
"""
本地告警适配器：支持 SMTP 邮件发送或控制台日志告警
"""
import smtplib
import logging # Use logging
from email.mime.text import MIMEText
# email.mime.multipart is not strictly needed if only sending plain text via MIMEText
# but if HTML + plain text were ever desired, MIMEMultipart would be used.
# For now, keeping it simple as per user's direct MIMEText usage.
# from email.mime.multipart import MIMEMultipart
from typing import List # For send_email

# Assuming settings are imported correctly from src.config
# The user's snippet for this file uses SMTP_USERNAME, which was harmonized to SMTP_USER
# in the consolidated settings.py. I will use SMTP_USER here for consistency.
from src.config.settings import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
# ALERT_EMAIL_LIST is not used by this version's notify, as it hardcodes recipients.

logger = logging.getLogger(__name__) # Use logger

class LocalAlertAdapter:
    """
    本地告警适配器：当 ALERT_PROVIDER='local' 时使用
    """

    @staticmethod
    def send_email(subject: str, content: str, to_addrs: List[str]):
        """
        使用 SMTP 发送告警邮件；若未配置 SMTP_USER, 则只打印日志
        """
        # Check SMTP_USER (harmonized from SMTP_USERNAME) and SMTP_PASSWORD
        if SMTP_USER and SMTP_PASSWORD and SMTP_SERVER and to_addrs: # Added SMTP_SERVER check
            # Using MIMEText directly for plain text email as per user's logic
            msg = MIMEText(content, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = SMTP_USER # Use SMTP_USER
            msg["To"] = ", ".join(to_addrs)

            try:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
                    # Optional: server.set_debuglevel(1)
                    server.ehlo()
                    if server.has_extn('STARTTLS'):
                        server.starttls()
                        server.ehlo()
                    server.login(SMTP_USER, SMTP_PASSWORD) # Use SMTP_USER
                    server.sendmail(SMTP_USER, to_addrs, msg.as_string()) # Use SMTP_USER
                logger.info(f"[LocalAlertAdapter] Email alert sent. Subject: {subject} To: {to_addrs}")
            except Exception as e:
                logger.error(f"[LocalAlertAdapter] Failed to send email alert. Subject: {subject}. Error: {e}", exc_info=True)
        else:
            logger.warning(f"[LocalAlertAdapter][ALERT][{subject}] SMTP not fully configured or no recipients. Content: {content}")

    @staticmethod
    def notify(subject: str, content: str):
        """
        统一调用入口，默认收件人从环境变量中读取 (User's text implies this, but code hardcodes)
        User's code hardcodes to_addrs = ["admin@example.com"]
        """
        # TODO: 若未来需求变更，可增加动态收件人配置 (User's comment)
        to = ["admin@example.com"] # Hardcoded as per user's snippet for this file
        logger.info(f"LocalAlertAdapter attempting to notify. Subject: {subject}. Defaulting to: {to}")
        LocalAlertAdapter.send_email(subject, content, to)
