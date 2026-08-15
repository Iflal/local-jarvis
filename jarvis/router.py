"""Fast deterministic intent routing for common assistant commands."""

from __future__ import annotations

import re

from .models import Intent


class IntentRouter:
    _REMINDER = re.compile(
        r"^remind me in\s+(\d+)\s+(second|seconds|minute|minutes|hour|hours)\s+(?:to\s+)?(.+)$",
        re.IGNORECASE,
    )

    def route(self, text: str) -> Intent | None:
        # Whisper commonly adds sentence punctuation. Intent matching should
        # not send an otherwise exact command to the LLM because of a `?`.
        clean = " ".join(text.strip().split()).strip(" .!?,")
        lower = clean.lower()

        if lower in {"help", "what can you do", "show commands"}:
            return Intent("help")
        if lower in {"hello", "hi", "hey", "good morning", "good evening"}:
            return Intent("greet")
        if lower in {"what time is it", "tell me the time", "time"} or (
            "time" in lower
            and any(marker in lower for marker in ("what", "tell", "current", "your time", "time is it"))
            and not any(marker in lower for marker in ("movie", "meeting", "appointment", "timer"))
        ):
            return Intent("time")
        if lower in {
            "what is the date",
            "tell me the date",
            "date",
            "today's date",
            "what day is it",
            "what about today",
            "how about today",
            "so how about today",
        } or self._asks_current_weekday(lower):
            return Intent("date")
        if lower in {"system status", "computer status", "battery status", "status"}:
            return Intent("system_status")
        if lower in {"volume up", "increase volume", "turn it up"}:
            return Intent("volume", {"direction": "up"})
        if lower in {"volume down", "decrease volume", "turn it down"}:
            return Intent("volume", {"direction": "down"})
        if lower in {"mute", "mute volume", "unmute", "unmute volume"}:
            return Intent("volume", {"direction": "mute"})
        if lower in {"what do you see", "look around", "use the camera", "describe the camera"}:
            return Intent("vision")
        if lower in {"list notes", "show notes", "what did i ask you to remember"}:
            return Intent("list_notes")
        if (
            ("question" in lower and any(word in lower for word in ("before", "previous", "last")))
            or lower in {"what did i just ask", "what did i ask you"}
        ):
            return Intent("last_question")
        if "internet" in lower and any(
            marker in lower for marker in ("access", "online", "connect", "use the internet")
        ):
            return Intent("internet_status")
        if "tool" in lower and any(
            marker in lower for marker in ("call", "calling", "have", "support")
        ):
            return Intent("tool_capabilities")

        if lower in {"list voices", "show voices", "what voices do you have", "available voices"}:
            return Intent("voice", {"mode": "list"})
        if any(
            phrase in lower
            for phrase in ("how can i change your voice", "set up your voice", "voice setup")
        ) or ("change your voice" in lower and any(word in lower for word in ("can't", "cannot"))):
            return Intent("voice", {"mode": "help"})
        if lower in {"change your voice", "switch your voice", "use another voice"}:
            return Intent("voice", {"mode": "cycle"})
        voice_match = re.match(
            r"^(?:set|change|switch|use)\s+(?:your\s+)?voice\s+(?:to\s+)?(.+)$",
            clean,
            re.IGNORECASE,
        )
        if voice_match:
            return Intent("voice", {"mode": "set", "target": voice_match.group(1).strip()})

        reminder = self._REMINDER.match(clean)
        if reminder:
            count = int(reminder.group(1))
            unit = reminder.group(2).lower()
            multiplier = 1 if unit.startswith("second") else 60 if unit.startswith("minute") else 3600
            return Intent(
                "reminder",
                {"delay_seconds": count * multiplier, "content": reminder.group(3).strip()},
            )

        for prefix in ("remember that ", "remember ", "take a note ", "note that "):
            if lower.startswith(prefix):
                content = clean[len(prefix) :].strip()
                if content:
                    return Intent("note", {"content": content})

        # Natural speech often wraps a simple action in a polite question or
        # repeats "open". Resolve common browser requests before the generic
        # application matcher.
        if re.search(r"\bopen\b", lower) and re.search(r"\bgoogle\b", lower):
            return Intent("open", {"target": "google"})
        if re.search(r"\bopen\b", lower) and re.search(r"\bbrowser\b", lower):
            return Intent("open", {"target": "browser"})

        match = re.match(
            r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?(?:open|launch|start)\s+(.+)$",
            clean,
            re.IGNORECASE,
        )
        if match:
            target = re.sub(r"^the\s+", "", match.group(1).strip(), flags=re.IGNORECASE)
            return Intent("open", {"target": target.lower()})

        match = re.match(r"^(?:search(?: the)? web for|google)\s+(.+)$", clean, re.IGNORECASE)
        if match:
            return Intent("web_search", {"query": match.group(1).strip()})

        match = re.match(r"^(?:find|locate)\s+(?:file\s+)?(.+)$", clean, re.IGNORECASE)
        if match:
            return Intent("find_file", {"query": match.group(1).strip()})

        return None

    @staticmethod
    def _asks_current_weekday(text: str) -> bool:
        weekdays = {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        mentioned = weekdays.intersection(text.split())
        return (
            ("today" in text and ("day" in text or bool(mentioned)))
            or (len(mentioned) >= 2 and " or " in text)
        )
