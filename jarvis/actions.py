"""Allow-listed operating-system actions. No model-generated code is executed."""

from __future__ import annotations

import ctypes
import subprocess
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from .memory import MemoryStore
from .models import ActionResult, Intent


HELP_TEXT = (
    "I can open configured apps and websites, search the web, report the time, date, "
    "battery and system status, change volume, save and list notes, create reminders, "
    "find files, inspect one webcam frame, and answer questions locally."
)


class SystemActions:
    def __init__(self, config: dict[str, Any], memory: MemoryStore) -> None:
        self.config = config
        self.memory = memory

    def execute(self, intent: Intent) -> ActionResult:
        handlers = {
            "help": self._help,
            "greet": self._greet,
            "time": self._time,
            "date": self._date,
            "system_status": self._system_status,
            "volume": self._volume,
            "open": self._open,
            "web_search": self._web_search,
            "find_file": self._find_file,
            "note": self._note,
            "list_notes": self._list_notes,
            "reminder": self._reminder,
            "last_question": self._last_question,
            "internet_status": self._internet_status,
            "tool_capabilities": self._tool_capabilities,
            "voice": self._voice,
        }
        handler = handlers.get(intent.name)
        if handler is None:
            return ActionResult(f"Unsupported action: {intent.name}", False)
        try:
            return handler(**intent.arguments)
        except Exception as exc:
            return ActionResult(f"I could not complete that action: {exc}", False)

    @staticmethod
    def _help() -> ActionResult:
        return ActionResult(HELP_TEXT)

    def _greet(self) -> ActionResult:
        return ActionResult(f"Hello. {self.config['assistant']['name']} is ready.")

    @staticmethod
    def _time() -> ActionResult:
        return ActionResult(f"It is {datetime.now().strftime('%I:%M %p')}.")

    @staticmethod
    def _date() -> ActionResult:
        return ActionResult(f"Today is {datetime.now().strftime('%A, %B %d, %Y')}.")

    @staticmethod
    def _system_status() -> ActionResult:
        import psutil

        cpu = psutil.cpu_percent(interval=0.2)
        memory = psutil.virtual_memory()
        parts = [f"CPU usage is {cpu:.0f} percent", f"memory usage is {memory.percent:.0f} percent"]
        battery = psutil.sensors_battery()
        if battery is not None:
            charging = " and charging" if battery.power_plugged else ""
            parts.append(f"battery is {battery.percent:.0f} percent{charging}")
        return ActionResult(", ".join(parts) + ".")

    @staticmethod
    def _volume(direction: str) -> ActionResult:
        key_codes = {"mute": 0xAD, "down": 0xAE, "up": 0xAF}
        code = key_codes[direction]
        user32 = ctypes.windll.user32
        presses = 1 if direction == "mute" else 2
        for _ in range(presses):
            user32.keybd_event(code, 0, 0, 0)
            user32.keybd_event(code, 0, 2, 0)
        return ActionResult("Volume toggled." if direction == "mute" else f"Volume {direction}.")

    def _open(self, target: str) -> ActionResult:
        if target in self.config.get("websites", {}):
            webbrowser.open(self.config["websites"][target])
            return ActionResult(f"Opening {target}.")
        executable = self.config.get("apps", {}).get(target)
        if executable:
            subprocess.Popen([executable], close_fds=True)
            return ActionResult(f"Opening {target}.")
        allowed = sorted(set(self.config.get("apps", {})) | set(self.config.get("websites", {})))
        return ActionResult(f"{target} is not allow-listed. Available targets: {', '.join(allowed)}.", False)

    @staticmethod
    def _web_search(query: str) -> ActionResult:
        webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
        return ActionResult(f"Searching the web for {query}.")

    def _find_file(self, query: str) -> ActionResult:
        needle = query.casefold()
        matches: list[str] = []
        for root_text in self.config.get("search_roots", []):
            root = Path(root_text)
            if not root.is_dir():
                continue
            try:
                for path in root.rglob("*"):
                    if needle in path.name.casefold():
                        matches.append(str(path))
                        if len(matches) == 5:
                            break
            except (OSError, PermissionError):
                continue
            if len(matches) == 5:
                break
        if not matches:
            return ActionResult(f"I could not find a file matching {query}.", False)
        return ActionResult("I found: " + "; ".join(matches))

    def _note(self, content: str) -> ActionResult:
        note_id = self.memory.add_note(content)
        return ActionResult(f"Saved note {note_id}.")

    def _list_notes(self) -> ActionResult:
        notes = self.memory.list_notes()
        if not notes:
            return ActionResult("You have no saved notes.")
        return ActionResult("Your recent notes are: " + "; ".join(f"{number}: {text}" for number, text in notes))

    def _reminder(self, content: str, delay_seconds: int) -> ActionResult:
        due_at = time.time() + delay_seconds
        self.memory.add_reminder(content, due_at)
        due_text = datetime.fromtimestamp(due_at).strftime("%I:%M %p")
        return ActionResult(f"Reminder set for {due_text}: {content}.")

    def _last_question(self) -> ActionResult:
        previous = self.memory.last_user_message()
        if previous is None:
            return ActionResult("You have not asked a previous question in this local history.")
        return ActionResult(f"Your previous request was: {previous}")

    @staticmethod
    def _internet_status() -> ActionResult:
        return ActionResult(
            "My language model runs locally. I do not browse autonomously, but my "
            "allow-listed tools can open websites and web searches when your laptop "
            "has internet access."
        )

    @staticmethod
    def _tool_capabilities() -> ActionResult:
        return ActionResult(
            "Yes. I use safe local tools for configured applications, websites, "
            "volume, system status, notes, reminders, file search, and the webcam. "
            "I cannot execute arbitrary model-generated commands."
        )

    def _voice(self, mode: str, target: str | None = None) -> ActionResult:
        import pyttsx3

        engine = pyttsx3.init(driverName="sapi5")
        try:
            voices = list(engine.getProperty("voices"))
            current = self.config["tts"].get("voice") or engine.getProperty("voice")
        finally:
            engine.stop()
        if not voices:
            return ActionResult("Windows did not report any installed speech voices.", False)

        names = [str(getattr(voice, "name", voice.id)) for voice in voices]
        if mode == "list":
            choices = "; ".join(
                f"{index + 1}, {name}" for index, name in enumerate(names)
            )
            return ActionResult(
                f"Available voices are: {choices}. Say set voice to a number or name."
            )
        if mode == "help":
            return ActionResult(
                "Say list voices, change your voice, or set voice to a voice number "
                "or name. The selection lasts until Jarvis is restarted unless you "
                "also put its name in config.json."
            )

        selected = None
        if mode == "cycle":
            current_index = next(
                (index for index, voice in enumerate(voices) if voice.id == current), -1
            )
            selected = voices[(current_index + 1) % len(voices)]
        elif target:
            number_words = {
                "one": 1,
                "two": 2,
                "three": 3,
                "four": 4,
                "five": 5,
                "six": 6,
            }
            normalized = target.strip().casefold()
            index = number_words.get(normalized)
            if index is None and normalized.isdigit():
                index = int(normalized)
            if index is not None and 1 <= index <= len(voices):
                selected = voices[index - 1]
            else:
                selected = next(
                    (
                        voice
                        for voice, name in zip(voices, names)
                        if normalized in name.casefold()
                        or normalized in voice.id.casefold()
                    ),
                    None,
                )
        if selected is None:
            return ActionResult(
                "I could not find that voice. Say list voices to hear the installed choices.",
                False,
            )
        self.config["tts"]["voice"] = selected.id
        name = str(getattr(selected, "name", selected.id))
        return ActionResult(f"Voice changed to {name}.")
