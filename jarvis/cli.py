"""Console, push-to-talk, and continuous wake-word operating modes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .assistant import JarvisAssistant
from .config import load_config
from .diagnostics import run_checks
from .llm import OllamaClient
from .memory import MemoryStore
from .speech import SpeechRecognizer
from .tts import Speaker


EXIT_WORDS = {"exit", "quit", "bye", "goodbye", "good bye", "see you", "stop listening"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline-first local Jarvis assistant")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--text", action="store_true", help="type commands in a console")
    mode.add_argument("--continuous", action="store_true", help="listen continuously for 'Jarvis ...'")
    mode.add_argument("--once", metavar="TEXT", help="process one text command and exit")
    parser.add_argument("--config", type=Path, help="optional JSON configuration override")
    parser.add_argument("--no-tts", action="store_true", help="print responses without speaking")
    parser.add_argument("--check", action="store_true", help="check dependencies and Ollama")
    return parser


def _respond(text: str, speaker: Speaker) -> None:
    print(f"Jarvis: {text}")
    speaker.say(text)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except (OSError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        healthy, lines = run_checks(config)
        print("\n".join(lines))
        return 0 if healthy else 1

    if args.no_tts:
        config["tts"]["enabled"] = False
    memory = MemoryStore(config["database"])
    speaker = Speaker(config["tts"])
    assistant = JarvisAssistant(config, memory, OllamaClient(config["ollama"]))
    try:
        if args.once is not None:
            _respond(assistant.process(args.once), speaker)
            return 0
        if args.text:
            return _text_loop(assistant, speaker)
        recognizer = SpeechRecognizer(config["speech"])
        if args.continuous:
            return _continuous_loop(assistant, recognizer, speaker)
        return _push_to_talk_loop(assistant, recognizer, speaker)
    except KeyboardInterrupt:
        print("\nJarvis stopped.")
        return 0
    finally:
        memory.close()


def _text_loop(assistant: JarvisAssistant, speaker: Speaker) -> int:
    print("Local Jarvis text mode. Type 'exit' to quit.")
    while True:
        for reminder in assistant.due_reminders():
            _respond(reminder, speaker)
        try:
            text = input("You: ").strip()
        except EOFError:
            return 0
        if text.lower().strip(" .!?,") in EXIT_WORDS:
            _respond("Goodbye.", speaker)
            return 0
        if text:
            _respond(assistant.process(text), speaker)


def _push_to_talk_loop(
    assistant: JarvisAssistant, recognizer: SpeechRecognizer, speaker: Speaker
) -> int:
    print("Push-to-talk mode. Press Enter, speak, then pause. Type q + Enter to quit.")
    while True:
        for reminder in assistant.due_reminders():
            _respond(reminder, speaker)
        command = input("[Enter to speak] ").strip().lower()
        if command in {"q", "quit", "exit"}:
            return 0
        print("Listening...")
        text = recognizer.listen()
        print(f"You: {text or '[no speech detected]'}")
        if text.lower().strip(" .!?,") in EXIT_WORDS:
            _respond("Goodbye.", speaker)
            return 0
        if text:
            _respond(assistant.process(text), speaker)


def _continuous_loop(
    assistant: JarvisAssistant, recognizer: SpeechRecognizer, speaker: Speaker
) -> int:
    print(f"Continuous mode. Begin commands with '{assistant.name}'. Press Ctrl+C to stop.")
    while True:
        for reminder in assistant.due_reminders():
            _respond(reminder, speaker)
        text = recognizer.listen()
        if not text:
            continue
        print(f"Heard: {text}")
        command = assistant.strip_wake_word(text, required=True)
        if command is None:
            continue
        if command.lower().strip(" .!?,") in EXIT_WORDS:
            _respond("Goodbye.", speaker)
            return 0
        if command:
            _respond(assistant.process(command), speaker)
