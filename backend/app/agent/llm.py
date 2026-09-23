"""OpenAI 兼容大模型客户端（DeepSeek / OpenAI 等），基于官方 openai SDK。"""

import logging
import os

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError
from openai.types.chat import ChatCompletionMessage

from app.core.config import settings

logger = logging.getLogger("meeting-room-agent.llm")

PROVIDER_PRESETS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}


class LLMError(RuntimeError):
    pass


def resolve_provider() -> dict | None:
    """解析当前可用的大模型配置，返回 None 表示使用本地知识库引擎。"""
    if settings.AGENT_PROVIDER == "local":
        return None

    api_key = settings.LLM_API_KEY.strip()
    preset = "openai"
    if not api_key:
        if os.getenv("DEEPSEEK_API_KEY"):
            api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
            preset = "deepseek"
        elif os.getenv("OPENAI_API_KEY"):
            api_key = os.getenv("OPENAI_API_KEY", "").strip()
            preset = "openai"

    if not api_key:
        return None

    defaults = PROVIDER_PRESETS[preset]
    base_url = (settings.LLM_BASE_URL or defaults["base_url"]).rstrip("/")
    model = settings.LLM_MODEL or defaults["model"]
    return {"name": preset, "base_url": base_url, "model": model, "api_key": api_key}


def _client(provider: dict) -> OpenAI:
    """按当前配置建客户端：base_url 指向兼容端点，其余行为与官方 SDK 一致。"""
    return OpenAI(
        api_key=provider["api_key"],
        base_url=provider["base_url"],
        timeout=settings.LLM_TIMEOUT,
    )


def _to_message_dict(message: ChatCompletionMessage) -> dict:
    """把 SDK 的返回转成可回灌进 messages 的纯字典。

    只保留兼容端点认识的字段，SDK 补出的 refusal / annotations 等 null 字段不往外带。
    """
    result: dict = {"content": message.content or ""}
    if message.tool_calls:
        result["tool_calls"] = [call.model_dump() for call in message.tool_calls]
    return result


def _error_detail(error: APIStatusError) -> str:
    """尽量取出接口返回的原文，便于排查；取不到就退回异常自身的描述。"""
    try:
        return str(error.response.text)[:300]
    except Exception:  # noqa: BLE001 - 兜底分支不该盖掉原始错误
        return str(error)[:300]


def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """调用 /chat/completions，返回模型的 message（可能带 tool_calls）。"""
    provider = resolve_provider()
    if provider is None:
        raise LLMError("未配置大模型，已使用本地知识库引擎")

    payload: dict = {
        "model": provider["model"],
        "messages": messages,
        "temperature": 0.3,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    try:
        with _client(provider) as client:
            completion = client.chat.completions.create(**payload)
    except APITimeoutError as error:
        raise LLMError(f"大模型调用超时：{error}") from error
    except APIConnectionError as error:
        raise LLMError(f"无法连接大模型服务：{error}") from error
    except APIStatusError as error:
        raise LLMError(f"大模型接口返回 {error.status_code}：{_error_detail(error)}") from error
    except OpenAIError as error:
        raise LLMError(f"大模型调用失败：{error}") from error

    choices = completion.choices or []
    if not choices:
        raise LLMError("大模型返回内容为空")
    return _to_message_dict(choices[0].message)
