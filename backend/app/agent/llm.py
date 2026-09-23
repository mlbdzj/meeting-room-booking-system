"""OpenAI 兼容大模型客户端（DeepSeek / OpenAI 等），仅依赖标准库。"""

import json
import logging
import os
import urllib.error
import urllib.request

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


def chat_completion(messages: list[dict], tools: list[dict] | None = None) -> dict:
    provider = resolve_provider()
    if provider is None:
        raise LLMError("未配置大模型，已使用本地知识库引擎")

    payload: dict = {
        "model": provider["model"],
        "messages": messages,
        "temperature": 0.3,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    request = urllib.request.Request(
        f"{provider['base_url']}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {provider['api_key']}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.LLM_TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="ignore")[:300]
        raise LLMError(f"大模型接口返回 {error.code}：{detail}") from error
    except urllib.error.URLError as error:
        raise LLMError(f"无法连接大模型服务：{error.reason}") from error
    except (TimeoutError, json.JSONDecodeError) as error:
        raise LLMError(f"大模型调用失败：{error}") from error

    choices = data.get("choices") or []
    if not choices:
        raise LLMError("大模型返回内容为空")
    return choices[0].get("message", {})
