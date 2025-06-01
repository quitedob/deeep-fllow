# src/adapters/cloud_alert_adapter.py
# -*- coding: utf-8 -*- # Added coding for consistency
"""
云端告警适配器：当 ALERT_PROVIDER='cloud' 时使用
本示例仅提供代码结构，需根据具体云平台实现
"""
import os
import requests
import logging # Added logging
import json # Added for json.dumps if not using requests' json param directly

logger = logging.getLogger(__name__) # Added logger

class CloudAlertAdapter:
    """
    云端告警适配器：示例结构，实际实现需接入钉钉/Slack/Webhook 等
    """

    @staticmethod
    def notify(subject: str, content: str):
        """
        调用云端告警 API，将告警信息推送至配置的渠道
        例如：钉钉自定义机器人、Slack Webhook、云监控告警接口等
        """
        # This adapter assumes it's called only when ALERT_PROVIDER is 'cloud'.
        # The decision to call this adapter should be made by the calling code.

        # CLOUD_ALERT_WEBHOOK should be defined in src.config.settings if this adapter is used.
        # For this example, we directly use os.getenv as per the user's snippet for this file.
        cloud_alert_webhook_env = os.getenv("CLOUD_ALERT_WEBHOOK", "")

        if not cloud_alert_webhook_env:
            logger.warning(f"[CLOUD-ALERT-FALLBACK][{subject}] CLOUD_ALERT_WEBHOOK not set. Content: {content}")
            return

        # Assuming a DingTalk-like webhook payload for the example
        payload = {
            "msgtype": "text",
            "text": {"content": f"{subject}\n{content}"}
        }
        headers = {"Content-Type": "application/json;charset=utf-8"} # Added for clarity

        response = None # Initialize for use in error logging if requests.post fails early
        try:
            response = requests.post(cloud_alert_webhook_env, data=json.dumps(payload), headers=headers, timeout=5)
            response.raise_for_status() # Check for HTTP errors (4xx or 5xx)

            # Further response checking might be needed depending on the actual cloud service
            # For a simple webhook, a 2xx status is often success.
            # If it's a more complex API (e.g. cloud monitoring), parse response.json().
            logger.info(f"[CLOUD-ALERT][{subject}] Successfully sent to {cloud_alert_webhook_env}.") # Removed content from log for brevity
        except requests.exceptions.RequestException as e:
            logger.error(f"[CLOUD-ALERT][{subject}] Request failed for {cloud_alert_webhook_env}: {e}", exc_info=True)
        except Exception as e: # Catch-all for other unexpected errors (e.g. if response.json() was used and failed)
            logger.error(f"[CLOUD-ALERT][{subject}] Unknown error for {cloud_alert_webhook_env}: {e}", exc_info=True)
