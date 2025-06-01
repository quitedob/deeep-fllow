# 文件路径: src/config/loader.py
# -*- coding: utf-8 -*-
"""
YAML 配置文件加载器，支持环境变量替换。
"""
import logging
import os
import yaml
from typing import Dict, Any

# 缓存已加载和处理过的配置，避免重复IO和解析
# 简化注释：配置缓存
_config_cache: Dict[str, Dict[str, Any]] = {}


def replace_env_vars(value: Any) -> Any:
    """
    如果值是字符串且以 '$' 开头，则替换为环境变量。
    简化注释：替换环境变量
    """
    if isinstance(value, str) and value.startswith("$"):
        env_var_name = value[1:]  # 获取环境变量名 (去掉 '$')
        # os.getenv 的第二个参数是默认值，如果环境变量不存在，则返回原始值 (如 "$VAR")
        return os.getenv(env_var_name, value)
    return value


def process_dict(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    递归遍历字典，对所有字符串值应用环境变量替换。
    简化注释：递归处理字典
    """
    if not isinstance(config, dict):
        return config

    processed = {}
    for key, value in config.items():
        if isinstance(value, dict):
            # 如果值是字典，则递归处理
            processed[key] = process_dict(value)
        elif isinstance(value, list):
            # 如果值是列表，则遍历列表中的每个元素
            processed[key] = [process_dict(item) if isinstance(item, dict) else replace_env_vars(item) for item in
                              value]
        else:
            # 对其他类型的值（主要是字符串）进行环境变量替换
            processed[key] = replace_env_vars(value)
    return processed


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    加载并处理 YAML 配置文件。
    - 修复：在 open() 函数中增加了 encoding='utf-8'，以解决在 Windows 环境下的 'gbk' 解码错误。
    - 增加了对文件不存在的检查和缓存功能。
    简化注释：加载YAML配置
    """
    # 如果文件路径已在缓存中，直接返回缓存结果
    if file_path in _config_cache:
        return _config_cache[file_path]

    # 如果文件不存在，记录警告并返回空字典
    if not os.path.exists(file_path):
        logging.warning(f"配置文件未找到: {file_path}，将返回空配置。")
        return {}

    # --- 核心修复点 ---
    # 使用 'utf-8' 编码打开文件，防止在不同操作系统上出现解码错误
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}  # 如果文件为空，yaml.safe_load返回None，我们将其置为{}
    except Exception as e:
        logging.error(f"读取或解析YAML文件失败: {file_path}, 错误: {e}", exc_info=True)
        return {}  # 发生错误时返回空字典

    # 处理环境变量替换
    processed_config = process_dict(config)

    # 将处理后的配置存入缓存
    _config_cache[file_path] = processed_config

    return processed_config