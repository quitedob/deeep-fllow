# 文件路径：src/utils/logger.py
# -*- coding: utf-8 -*-
"""
日志工具模块：统一配置日志输出到控制台和文件
使用方法：在其他模块中引入 logger，并调用 logger.info(), logger.error() 等
"""

import logging
import os
from pathlib import Path
from src.config.settings import API_HOST, API_PORT

# 日志目录
LOG_DIR = Path("logs")
# 如果 logs 目录不存在，则创建
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志文件路径：在 logs 目录下，以当前服务名称命名
LOG_FILE = LOG_DIR / "deerflow.log"

# 全局日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        # 将日志写入文件
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        # 也输出到控制台
        logging.StreamHandler()
    ]
)

# 获取名为 "deerflow" 的 Logger
logger = logging.getLogger("deerflow")

# 示例：在模块初始化时，打印当前服务启动信息
logger.info(f"DeerFlow Monitoring Service 日志初始化完成，监听地址: {API_HOST}:{API_PORT}")