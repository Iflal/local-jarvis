from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jarvis.assistant import JarvisAssistant
from jarvis.memory import MemoryStore
from jarvis.models import ActionResult
from jarvis.router import IntentRouter
from jarvis.tts import Speaker


class FakeLLM:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, images=None):
        self.calls.append((messages, images))
        return "local answer"


class FakeActions:
    def __init__(self) -> None:
        self.intents = []

    def execute(self, intent):
        self.intents.append(intent)
        return ActionResult("action complete")


class RouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = IntentRouter()

    def test_open_app(self) -> None:
        intent = self.router.route("Open calculator")
        self.assertEqual(intent.name, "open")
        self.assertEqual(intent.arguments["target"], "calculator")

    def test_reminder_conversion(self) -> None:
        intent = self.router.route("Remind me in 2 minutes to stretch")
        self.assertEqual(intent.name, "reminder")
        self.assertEqual(intent.arguments["delay_seconds"], 120)
        self.assertEqual(intent.arguments["content"], "stretch")

    def test_unknown_goes_to_llm(self) -> None:
        self.assertIsNone(self.router.route("Explain recursion"))

    def test_polite_browser_request(self) -> None:
        intent = self.router.route("Can you open the browser and open Google?")
        self.assertEqual(intent.name, "open")
        self.assertEqual(intent.arguments["target"], "google")

    def test_natural_today_question(self) -> None:
        intent = self.router.route("So how about today?")
        self.assertEqual(intent.name, "date")

    def test_imperfect_spoken_time_question(self) -> None:
        intent = self.router.route("What is your time is it?")
        self.assertEqual(intent.name, "time")

    def test_weekday_choice_uses_system_date(self) -> None:
        intent = self.router.route("Tuesday or Saturday?")
        self.assertEqual(intent.name, "date")

    def test_unrelated_time_question_uses_llm(self) -> None:
        self.assertIsNone(self.router.route("What time is the movie?"))

    def test_previous_question_intent(self) -> None:
        intent = self.router.route("What question did I ask before?")
        self.assertEqual(intent.name, "last_question")

    def test_internet_capability_intent(self) -> None:
        intent = self.router.route("Do you have any internet access?")
        self.assertEqual(intent.name, "internet_status")

    def test_tool_capability_intent(self) -> None:
        intent = self.router.route("Do you have tool calling?")
        self.assertEqual(intent.name, "tool_capabilities")

    def test_voice_management_intents(self) -> None:
        self.assertEqual(self.router.route("List voices").arguments["mode"], "list")
        self.assertEqual(self.router.route("Change your voice").arguments["mode"], "cycle")
        intent = self.router.route("Set your voice to two")
        self.assertEqual(intent.name, "voice")
        self.assertEqual(intent.arguments["target"], "two")


class MemoryTests(unittest.TestCase):
    def test_notes_messages_and_due_reminders(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(str(Path(directory) / "memory.db"))
            memory.add_note("buy milk")
            self.assertEqual(memory.list_notes(), [(1, "buy milk")])
            memory.add_message("user", "hello")
            self.assertEqual(memory.recent_messages(1), [{"role": "user", "content": "hello"}])
            self.assertEqual(memory.last_user_message(), "hello")
            memory.add_reminder("stretch", 10)
            self.assertEqual(memory.pop_due_reminders(now=9), [])
            self.assertEqual(memory.pop_due_reminders(now=10), ["stretch"])
            self.assertEqual(memory.pop_due_reminders(now=11), [])
            memory.close()


class AssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.memory = MemoryStore(str(Path(self.temp.name) / "memory.db"))
        self.config = {
            "assistant": {"name": "Jarvis", "history_messages": 4},
            "vision": {},
        }
        self.llm = FakeLLM()
        self.actions = FakeActions()
        self.assistant = JarvisAssistant(
            self.config, self.memory, self.llm, actions=self.actions
        )

    def tearDown(self) -> None:
        self.memory.close()
        self.temp.cleanup()

    def test_wake_word(self) -> None:
        self.assertEqual(
            self.assistant.strip_wake_word("Hey Jarvis, open calculator", True),
            "open calculator",
        )
        self.assertIsNone(self.assistant.strip_wake_word("open calculator", True))

    def test_direct_action_bypasses_llm(self) -> None:
        self.assertEqual(self.assistant.process("open calculator"), "action complete")
        self.assertEqual(len(self.actions.intents), 1)
        self.assertEqual(self.llm.calls, [])

    def test_conversation_uses_llm(self) -> None:
        self.assertEqual(self.assistant.process("explain recursion"), "local answer")
        self.assertEqual(len(self.llm.calls), 1)


class SpeakerTests(unittest.TestCase):
    def test_new_sapi_engine_is_used_for_each_response(self) -> None:
        engines = []

        class FakeEngine:
            def setProperty(self, name, value):
                pass

            def say(self, text):
                self.text = text

            def runAndWait(self):
                pass

            def stop(self):
                pass

        def init(driverName=None):
            self.assertEqual(driverName, "sapi5")
            engine = FakeEngine()
            engines.append(engine)
            return engine

        fake_pyttsx3 = SimpleNamespace(init=init)
        with patch.dict(sys.modules, {"pyttsx3": fake_pyttsx3}):
            speaker = Speaker({"enabled": True, "rate": 185, "volume": 1.0})
            speaker.say("first")
            speaker.say("second")

        self.assertEqual(len(engines), 2)
        self.assertEqual([engine.text for engine in engines], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
