# 文件路径: src/llms/deepseek.py
# -*- coding: utf-8 -*-
import httpx
from typing import List, Dict
from src.config.settings import (
    DEFAULT_CHAT_MODEL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    REQUEST_TIMEOUT,
    USE_STREAM
)
from .base import BaseLLM


class DeepSeekLLM(BaseLLM):
    """DeepSeek 模型接口实现，支持异步、temperature 和详细的错误处理"""

    def __init__(self, model: str = None, api_key: str = None):
        """
        初始化DeepSeekLLM实例。
        简化注释：初始化
        """
        self.model = model or DEFAULT_CHAT_MODEL
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = DEEPSEEK_BASE_URL.rstrip("/")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        # 修复：确保AsyncClient在使用后能被关闭，通过在需要时创建或在应用关闭时调用close方法
        self._async_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

    async def chat(self, messages: List[Dict[str, str]], temperature: float = 1.0) -> str:
        """
        异步调用 DeepSeek API 进行聊天对话。
        简化注释：异步聊天
        """
        if not self.api_key:
            error_msg = "DeepSeek API Key 未配置。请在 .env 文件中设置 DEEPSEEK_API_KEY。"
            print(f"--- [LLM Error] {error_msg} ---")
            return f"抱歉，调用模型时出错: {error_msg}"

        url = f"{self.base_url}/chat/completions"
        data = {
            "model": self.model,
            "messages": messages,
            "stream": USE_STREAM,
            "temperature": temperature,
        }

        try:
            response = await self._async_client.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            result = response.json()
            # 假设返回结构为 {'choices':[{'message':{'content': '...'}}], ...}
            content = result["choices"][0]["message"]["content"]
            return content
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            error_text = e.response.text
            # 修复：提供更具体、用户友好的中文错误信息
            error_map = {
                400: f"格式错误 (400): 请求体格式不正确。详情: {error_text}",
                401: f"认证失败 (401): API Key 错误或无效。请检查您的 DEEPSEEK_API_KEY。",
                402: f"余额不足 (402): 您的账户余额不足以完成本次请求。",
                422: f"参数错误 (422): 请求参数不正确。详情: {error_text}",
                429: f"请求速率超限 (429): 已达到TPM或RPM上限，请稍后重试。",
                500: f"服务器故障 (500): DeepSeek 服务器内部故障，请稍后重试。",
                503: f"服务器繁忙 (503): DeepSeek 服务器负载过高，请稍后重试。"
            }
            error_message = error_map.get(status_code, f"API 请求失败 ({status_code}): {error_text}")
            print(f"--- [LLM Error] {error_message} ---")
            return f"抱歉，调用模型时出错: {error_message}"
        except httpx.RequestError as e:
            print(f"--- [LLM Error] 网络请求失败: {e} ---")
            return f"抱歉，无法连接到模型服务: {e}"
        except (KeyError, IndexError) as e:
            print(f"--- [LLM Error] 解析模型响应失败: {e} ---")
            return "抱歉，解析模型响应时发生错误。"
        except Exception as e:
            print(f"--- [LLM Error] 发生未知网络或解析错误: {e} ---")
            return "抱歉，系统发生未知错误。"

    async def close(self):
        """
        关闭 httpx 异步客户端。
        简化注释：关闭客户端
        """
        if hasattr(self, '_async_client') and not self._async_client.is_closed:
            await self._async_client.aclose()