# 文件路径：src/config/settings.py
# -*- coding: utf-8 -*-
"""
项目全局配置文件：从环境变量或 .env 中读取各类配置，
包括 Redis 连接、告警阈值、SMTP、钉钉机器人、FastAPI 服务等。
所有模块通过 import settings 来获取对应配置。
"""

import os
from dotenv import load_dotenv
from enum import Enum

# 仅在开发或测试阶段加载 .env；生产环境可由 Kubernetes ConfigMap、Docker Env 或 CI/CD 填充
load_dotenv()

# -------------------- Redis 配置 --------------------
# Redis 服务主机地址，默认 127.0.0.1；国内服务器可根据实际部署修改
REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
# Redis 服务端口号，默认 6379
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
# Redis 数据库索引，默认 0
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# -------------------- API 鉴权配置 --------------------
# 项目的 API Key 列表，以逗号分隔，必须通过环境变量设置；若为空，则抛出异常
API_KEYS_STR = os.getenv("API_KEYS", "")
API_KEYS = [key.strip() for key in API_KEYS_STR.split(',') if key.strip()]
if not API_KEYS:
    raise ValueError("请在环境变量中设置 API_KEYS（以逗号分隔多个 Key）")

# -------------------- 阈值配置 --------------------
# Redis 队列长度告警阈值（长度），默认 1000
QUEUE_ALERT_THRESHOLD = int(os.getenv("QUEUE_ALERT_THRESHOLD", 1000))
# 节点故障率告警阈值，0.1 即 10%
FAILURE_RATE_THRESHOLD = float(os.getenv("FAILURE_RATE_THRESHOLD", 0.1))

# -------------------- 告警渠道选择 --------------------
# 当 ALERT_PROVIDER='local' 时使用本地邮件+钉钉；当为 'cloud' 时调用云端告警适配器
ALERT_PROVIDER = os.getenv("ALERT_PROVIDER", "local")  # 可选值：local / cloud
# 优化点：新增告警状态配置
# 告警状态（如 "ALERTING"）在 Redis 中的有效期（秒），防止因 worker 停止而永久卡在告警状态
ALERT_STATE_EXPIRY_SECONDS = int(os.getenv("ALERT_STATE_EXPIRY_SECONDS", 86400)) # 默认 24 小时

# -------------------- SMTP 邮件告警配置 --------------------
# SMTP 服务地址（如 qq 邮箱：smtp.qq.com）
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
# SMTP 端口号，587(STARTTLS)/465(SSL)
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
# 发件邮箱账号，如 qq 邮箱地址
SMTP_USER = os.getenv("SMTP_USER", "")
# 发件邮箱授权码（非登录密码）
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
# 收件人列表，以逗号分隔，格式示例 "alice@example.com,bob@example.com"
ALERT_EMAIL_LIST_STR = os.getenv("ALERT_EMAIL_LIST", "")
ALERT_EMAIL_LIST = [email.strip() for email in ALERT_EMAIL_LIST_STR.split(',') if email.strip()]

# -------------------- 钉钉机器人告警配置 --------------------
# 钉钉自定义机器人 Webhook 地址
DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")
# 钉钉机器人加签密钥（若已在钉钉后台开启“加签”安全设置，则必填）
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "")

# -------------------- FastAPI 配置 --------------------
# FastAPI 服务监听主机，默认 0.0.0.0 可对外暴露
API_HOST = os.getenv("API_HOST", "0.0.0.0")
# FastAPI 服务监听端口，默认 8000
API_PORT = int(os.getenv("API_PORT", 8000))

# -------------------- APScheduler 定时任务配置 --------------------
# 定时任务（队列监控、节点故障率监控）循环间隔（秒），默认 60s
JOB_INTERVAL_SECONDS = int(os.getenv("JOB_INTERVAL_SECONDS", 60))

# -------------------- Prometheus 指标埋点（可选） --------------------
# 若设置为 true，则启用指标埋点并暴露 /metrics 接口
PROMETHEUS_METRICS_ENABLED = os.getenv("PROMETHEUS_METRICS_ENABLED", "false").lower() == "true"

# -------------------- 所有节点名称，用于 Prometheus 监控（可选） --------------------
# 在最初阶段，可不使用；如果在指标中需要标签，可在 .env 中设置 ALL_NODES="planner,researcher,coder,reporter,voice"
ALL_NODES_STR = os.getenv("ALL_NODES", "planner,researcher,coder,reporter,voice")
ALL_NODES = [node.strip() for node in ALL_NODES_STR.split(',') if node.strip()]

# -------------------- TTS 引擎配置 --------------------
# 可选 TTS 引擎，用于 Voice Agent 语音合成
class TTSEngine(Enum):
    GTTS = "GTTS"       # 使用 gTTS 库
    AZURE = "AZURE"     # 使用 Azure TTS（可扩展）
    GOOGLE = "GOOGLE"   # 使用 Google TTS（可扩展）

# 从环境变量读取默认 TTS 引擎，若为空则使用 GTTS
DEFAULT_TTS_ENGINE = TTSEngine(os.getenv("TTS_ENGINE", "GTTS"))