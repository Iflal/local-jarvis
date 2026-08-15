"""Assistant orchestration across routing, local actions, memory, and Ollama."""

from __future__ import annotations

import re
from typing import Any

from .actions import SystemActions
from .llm import OllamaClient, OllamaError
from .memory import MemoryStore
from .router import IntentRouter
from .vision import capture_frame


SYSTEM_PROMPT = """You are Jarvis, a concise, calm, privacy-first assistant running locally on a Windows laptop.
Answer directly and keep spoken responses brief unless detail is requested.
The host application provides safe tools for configured apps, websites, volume, system status, notes, reminders, file search, webcam inspection, and installed Windows voices. You do not execute arbitrary shell code.
Never claim an application, file, or system setting was changed unless a tool result says so.
Do not invent current information or pretend to have internet access.
"""


class JarvisAssistant:
    def __init__(
        self,
        config: dict[str, Any],
        memory: MemoryStore,
        llm: OllamaClient,
        router: IntentRouter | None = None,
        actions: SystemActions | None = None,
    ) -> None:
        self.config = config
        self.memory = memory
        self.llm = llm
        self.router = router or IntentRouter()
        self.actions = actions or SystemActions(config, memory)
        self.name = config["assistant"]["name"]

    def strip_wake_word(self, text: str, required: bool) -> str | None:
        clean = text.strip()
        match = re.match(rf"^(?:hey\s+)?{re.escape(self.name)}[,.]?\s*(.*)$", clean, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None if required else clean

    def process(self, text: str) -> str:
        clean = text.strip()
        if not clean:
            return "I did not hear anything."
        intent = self.router.route(clean)
        if intent is not None:
            if intent.name == "vision":
                response = self._vision_response()
            else:
                response = self.actions.execute(intent).message
        else:
            response = self._chat(clean)
        self.memory.add_message("user", clean)
        self.memory.add_message("assistant", response)
        return response

    def _chat(self, text: str) -> str:
        history = self.memory.recent_messages(int(self.config["assistant"].get("history_messages", 8)))
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": text})
        try:
            return self.llm.chat(messages)
        except OllamaError as exc:
            return str(exc)

    def _vision_response(self) -> str:
        try:
            image = capture_frame(self.config["vision"])
            return self.llm.chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": "Briefly describe what is visible in this webcam image. Avoid identifying a person's identity.",
                    },
                ],
                images=[image],
            )
        except (OllamaError, RuntimeError) as exc:
            return f"I could not inspect the camera: {exc}"

    def due_reminders(self) -> list[str]:
        return [f"Reminder: {content}." for content in self.memory.pop_due_reminders()]
