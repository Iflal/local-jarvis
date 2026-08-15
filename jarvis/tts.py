"""Offline text-to-speech using the Windows SAPI engine through pyttsx3."""

from __future__ import annotations

from typing import Any


class Speaker:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.enabled = bool(config.get("enabled", True))

    def say(self, text: str) -> None:
        if not self.enabled or not text:
            return
        engine = None
        try:
            # Recreate the SAPI driver for every utterance. Reusing a pyttsx3
            # engine on Windows can leave its event loop in a completed/busy
            # state, causing every response after the first to be silent.
            import pyttsx3

            engine = pyttsx3.init(driverName="sapi5")
            engine.setProperty("rate", int(self.config.get("rate", 185)))
            engine.setProperty("volume", float(self.config.get("volume", 1.0)))
            configured_voice = str(self.config.get("voice", "")).strip()
            if configured_voice:
                voices = list(engine.getProperty("voices"))
                selected = next(
                    (
                        voice
                        for voice in voices
                        if configured_voice.casefold() in voice.id.casefold()
                        or configured_voice.casefold()
                        in str(getattr(voice, "name", "")).casefold()
                    ),
                    None,
                )
                if selected is not None:
                    engine.setProperty("voice", selected.id)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            self.enabled = False
            print(f"[TTS disabled: {exc}]")
        finally:
            if engine is not None:
                engine.stop()
