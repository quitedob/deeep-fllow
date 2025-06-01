# 文件路径: src/tools/python_repl.py
# -*- coding: utf-8 -*-
# 定义 Python 代码执行工具

from langchain_experimental.tools import PythonREPLTool
from langchain_core.tools import tool

# 直接创建一个可以被 LangChain Agent 使用的实例
python_repl_tool = PythonREPLTool()

# 如果需要自定义工具名称或描述，可以进行包装
@tool("python_interpreter")
def python_repl_tool_wrapped(code: str) -> str:
    """
    一个 Python 解释器。用它来执行 Python 代码。
    输入应该是一个有效的 Python 代码字符串。
    如果代码执行有输出，将会被返回，否则返回一个空字符串。
    """
    return python_repl_tool.run(code)