import json
from collections.abc import AsyncIterator
from urllib import request

from backend.app.config import get_settings
from backend.app.models import ChatMessage


class OllamaClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
        stream: bool = False,
        json_mode: bool = False,
    ) -> str:
        payload = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
            "stream": stream,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"

        data = _post_json(f"{self.settings.ollama_base_url}/api/chat", payload)
        return data.get("message", {}).get("content", "")

    async def stream_chat(
        self,
        model: str,
        messages: list[ChatMessage],
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
            "stream": True,
            "options": {"temperature": temperature},
        }

        req = request.Request(
            f"{self.settings.ollama_base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=None) as response:
            for raw_line in response:
                if not raw_line.strip():
                    continue
                data = json.loads(raw_line.decode("utf-8"))
                content = data.get("message", {}).get("content")
                if content:
                    yield content


def _post_json(url: str, payload: dict) -> dict:
    req = request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=None) as response:
        return json.loads(response.read().decode("utf-8"))
