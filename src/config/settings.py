# src/config/settings.py
# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from enum import Enum # Keep Enum for now, it doesn't harm.

# 仅在开发或测试阶段加载 .env；生产环境可由 Kubernetes ConfigMap、Docker Env 或 CI/CD 填充
load_dotenv()

# -------------------- Redis 配置 --------------------
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# -------------------- API 鉴权配置 --------------------
# This was from Phase 1 and is essential for API security.
API_KEYS_STR = os.getenv("API_KEYS", "")
API_KEYS = [key.strip() for key in API_KEYS_STR.split(',') if key.strip()]
if not API_KEYS:
    raise ValueError("请在环境变量中设置 API_KEYS（以逗号分隔多个 Key）")

# -------------------- 阈值配置 --------------------
QUEUE_ALERT_THRESHOLD = int(os.getenv("QUEUE_ALERT_THRESHOLD", 1000))
FAILURE_RATE_THRESHOLD = float(os.getenv("FAILURE_RATE_THRESHOLD", 0.1))

# -------------------- 告警渠道选择 --------------------
ALERT_PROVIDER = os.getenv("ALERT_PROVIDER", "local") # local 或 cloud

# -------------------- SMTP 邮件告警配置 --------------------
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "") # Harmonized name
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
ALERT_EMAIL_LIST_STR = os.getenv("ALERT_EMAIL_LIST", "")
ALERT_EMAIL_LIST = [email.strip() for email in ALERT_EMAIL_LIST_STR.split(',') if email.strip()]

# -------------------- 钉钉机器人告警配置 --------------------
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "")

# -------------------- FastAPI 配置 --------------------
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", 8000))

# -------------------- APScheduler 定时任务配置 --------------------
JOB_INTERVAL_SECONDS = int(os.getenv("JOB_INTERVAL_SECONDS", 60))

# -------------------- Prometheus 指标埋点（可选） --------------------
PROMETHEUS_METRICS_ENABLED = os.getenv("PROMETHEUS_METRICS_ENABLED", "false").lower() == "true"

# -------------------- All Nodes for Metrics (from user's Phase 1 detailed plan, needed for /api/metrics) ---
ALL_NODES_STR = os.getenv("ALL_NODES", "planner,researcher,coder,reporter,voice") # As per user's P1 plan
ALL_NODES = [node.strip() for node in ALL_NODES_STR.split(',') if node.strip()]

# TTSEngine from user's very first detailed plan (Phase 1, Task 1 for settings.py)
# This is useful if voice_agent is used.
# The "国内服务器" settings list did not explicitly include it, but it's a harmless addition if unused.
class TTSEngine(Enum):
    GTTS    = "GTTS"
    AZURE   = "AZURE"
    GOOGLE  = "GOOGLE"
DEFAULT_TTS_ENGINE = TTSEngine(os.getenv("TTS_ENGINE", "GTTS"))
