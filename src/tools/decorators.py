# 文件路径: src/tools/decorators.py
# -*- coding: utf-8 -*-
# 用于工具和节点的装饰器

import functools
import logging
import asyncio

# 修复：确保日志记录器在模块级别定义
logger = logging.getLogger(__name__)


def log_io(func):
    """
    一个装饰器，用于记录函数的输入和输出，同时支持同步和异步函数。
    简化注释：记录函数IO
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger.debug(f"--- 调用 [异步] {func.__name__} ---")
            logger.debug(f"参数: {args}, {kwargs}")
            result = await func(*args, **kwargs)
            logger.debug(f"返回: {str(result)[:500]}...") # 避免打印过长的结果
            logger.debug(f"--- 结束 {func.__name__} ---")
            return result
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger.debug(f"--- 调用 [同步] {func.__name__} ---")
            logger.debug(f"参数: {args}, {kwargs}")
            result = func(*args, **kwargs)
            logger.debug(f"返回: {str(result)[:500]}...") # 避免打印过长的结果
            logger.debug(f"--- 结束 {func.__name__} ---")
            return result
        return sync_wrapper


def create_logged_tool(tool_class):
    """
    一个高阶函数，用于创建带有日志记录的工具类实例。
    简化注释：创建带日志的工具
    """
    class LoggedTool(tool_class):
        @log_io
        def _run(self, *args, **kwargs):
            return super()._run(*args, **kwargs)

        @log_io
        async def _arun(self, *args, **kwargs):
            return await super()._arun(*args, **kwargs)

    return LoggedTool