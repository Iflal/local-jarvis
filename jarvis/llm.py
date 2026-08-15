"""Minimal Ollama client using only the Python standard library."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.base_url = config["base_url"].rstrip("/")

    def is_available(self) -> bool:
        try:
            with urlopen(self.base_url + "/api/tags", timeout=3) as response:
                return response.status == 200
        except (OSError, URLError):
            return False

    def chat(
        self,
        messages: list[dict[str, Any]],
        images: list[str] | None = None,
    ) -> str:
        request_messages = [dict(message) for message in messages]
        if images:
            request_messages[-1]["images"] = images
        payload = {
            "model": self.config["model"],
            "messages": request_messages,
            "stream": False,
            "think": bool(self.config.get("think", False)),
            "options": {
                "num_ctx": int(self.config.get("context_length", 4096)),
                "temperature": float(self.config.get("temperature", 0.2)),
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + "/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=float(self.config.get("timeout_seconds", 120))) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise OllamaError(f"Ollama returned HTTP {exc.code}: {details}") from exc
        except (OSError, URLError) as exc:
            raise OllamaError("Cannot reach Ollama. Start Ollama and pull the configured model.") from exc
        content = result.get("message", {}).get("content", "").strip()
        if not content:
            raise OllamaError("Ollama returned an empty response.")
        return content

