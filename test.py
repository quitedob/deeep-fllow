# 文件路径：D:\python_code\AgentWork\test.py

"""
简要介绍：
本脚本演示如何从同目录下的 .env 文件读取 DeepSeek API Key，
调用 DeepSeek（基于 OpenAI SDK）进行一次性问答（非流式），
并计时测试请求耗时（单位：秒）。
"""

import os
import time                          # 用于计时
from dotenv import load_dotenv       # 用于加载 .env 文件
from openai import OpenAI           # 使用 OpenAI SDK，通过 base_url 指向 DeepSeek API

def main():
    # 1. 加载同目录下的 .env 文件（其中应包含 DEEPSEEK_API_KEY=<你的 API Key>）
    load_dotenv()

    # 2. 从环境变量中读取 API Key
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("错误：未检测到 DEEPSEEK_API_KEY，请在 .env 文件中设置。")
        return

    # 3. 初始化 OpenAI 客户端，但将 base_url 指向 DeepSeek API
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )

    # 4. 构建对话消息列表
    messages = [
        {"role": "system", "content": "你是一个乐于助人的智能助手。"},
        {"role": "user", "content": "请简要介绍 DeepSeek API 的非流式（non-streaming）调用方式。"}
    ]

    try:
        # 5. 记录开始时间
        start_time = time.time()

        # 6. 发送一次性请求（stream=False 表示非流式）
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False
        )

        # 7. 记录结束时间
        end_time = time.time()

    except Exception as e:
        print(f"请求 DeepSeek API 时发生错误：{e}")
        return

    # 8. 计算请求耗时（单位：秒）
    elapsed = end_time - start_time
    # 保留两位小数
    elapsed_str = f"{elapsed:.2f}"

    # 9. 从响应中提取完整回答内容
    try:
        answer = response.choices[0].message.content
    except (KeyError, IndexError):
        print("未能从响应中获取有效内容，请检查返回结果格式。")
        return

    # 10. 打印完整回答及耗时信息
    print("=== DeepSeek 回答开始 ===")
    print(answer)
    print("=== DeepSeek 回答结束 ===")
    print(f"请求耗时：{elapsed_str} 秒")

if __name__ == "__main__":
    main()
