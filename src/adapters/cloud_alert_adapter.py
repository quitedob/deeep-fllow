# 文件路径：src/adapters/cloud_alert_adapter.py
# -*- coding: utf-8 -*-
"""
云端告警适配器：当 ALERT_PROVIDER='cloud' 时调用
示例中以钉钉 Webhook 为例，实际项目可对接云监控平台、Slack、企业微信等。
"""

import os
import requests
import logging
import json

logger = logging.getLogger(__name__)

class CloudAlertAdapter:
    """
    云端告警实现类：
    - notify(subject, content)：通过配置的 CLOUD_ALERT_WEBHOOK 发送告警内容
    """

    @staticmethod
    def notify(subject: str, content: str):
        """
        调用云端告警 API，将告警信息推送到配置的渠道（如钉钉、Slack、企业微信等）
        参数：
          subject: 告警主题
          content: 告警正文
        """
        # 从环境变量中读取云端告警 Webhook 地址，需在 .env 中配置 CLOUD_ALERT_WEBHOOK
        webhook = os.getenv("CLOUD_ALERT_WEBHOOK", "")
        if not webhook:
            logger.warning(f"[CloudAlertAdapter][告警跳过] 未配置 CLOUD_ALERT_WEBHOOK → 主题: {subject}")
            return

        # 构造类似钉钉机器人的 JSON Payload；若对接其他平台，需调整格式
        payload = {
            "msgtype": "text",
            "text": {"content": f"{subject}\n{content}"}
        }
        headers = {"Content-Type": "application/json;charset=utf-8"}

        try:
            response = requests.post(webhook, data=json.dumps(payload), headers=headers, timeout=5)
            response.raise_for_status()  # 若状态码非 2xx，将抛出 HTTPError
            logger.info(f"[CloudAlertAdapter] 云端告警发送成功 → 主题: {subject}，Webhook: {webhook}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[CloudAlertAdapter] 云端告警请求失败 → 主题: {subject}, 异常: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[CloudAlertAdapter] 云端告警未知异常 → 主题: {subject}, 异常: {e}", exc_info=True)