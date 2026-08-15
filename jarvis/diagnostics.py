"""Environment diagnostics used by the --check command."""

from __future__ import annotations

import importlib.util
from typing import Any

from .llm import OllamaClient


def run_checks(config: dict[str, Any]) -> tuple[bool, list[str]]:
    checks: list[tuple[str, bool, str]] = []
    packages = {
        "numpy": "numpy",
        "sounddevice": "sounddevice",
        "faster-whisper": "faster_whisper",
        "pyttsx3": "pyttsx3",
        "psutil": "psutil",
        "OpenCV": "cv2",
    }
    for label, module in packages.items():
        present = importlib.util.find_spec(module) is not None
        checks.append((label, present, "installed" if present else "missing"))
    ollama = OllamaClient(config["ollama"])
    available = ollama.is_available()
    checks.append(("Ollama", available, "reachable" if available else "not reachable"))
    lines = [f"[{'OK' if passed else 'FAIL'}] {label}: {detail}" for label, passed, detail in checks]
    return all(passed for _, passed, _ in checks), lines

