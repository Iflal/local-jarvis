"""Offline microphone recording and Faster-Whisper transcription."""

from __future__ import annotations

from collections import deque
from typing import Any


class SpeechRecognizer:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._model = None

    def _load_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.config["model"],
                device=self.config.get("device", "cpu"),
                compute_type=self.config.get("compute_type", "int8"),
            )
        return self._model

    def listen(self) -> str:
        import numpy as np
        import sounddevice as sd

        sample_rate = int(self.config.get("sample_rate", 16000))
        block_seconds = 0.1
        block_size = int(sample_rate * block_seconds)
        threshold = float(self.config.get("silence_threshold", 0.015))
        start_blocks = int(float(self.config.get("start_timeout_seconds", 6)) / block_seconds)
        max_blocks = int(float(self.config.get("max_record_seconds", 15)) / block_seconds)
        silence_blocks = int(float(self.config.get("silence_seconds", 0.9)) / block_seconds)
        pre_roll: deque[Any] = deque(maxlen=3)
        captured: list[Any] = []
        started = False
        quiet_count = 0

        with sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32", blocksize=block_size) as stream:
            for block_number in range(max_blocks):
                block, overflowed = stream.read(block_size)
                if overflowed:
                    continue
                mono = block[:, 0].copy()
                level = float(np.sqrt(np.mean(np.square(mono))))
                if not started:
                    pre_roll.append(mono)
                    if level >= threshold:
                        started = True
                        captured.extend(pre_roll)
                    elif block_number >= start_blocks:
                        return ""
                else:
                    captured.append(mono)
                    quiet_count = quiet_count + 1 if level < threshold else 0
                    if quiet_count >= silence_blocks:
                        break

        if not captured:
            return ""
        audio = np.concatenate(captured).astype(np.float32)
        segments, _ = self._load_model().transcribe(
            audio,
            beam_size=int(self.config.get("beam_size", 3)),
            language="en" if self.config["model"].endswith(".en") else None,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=self.config.get("initial_prompt") or None,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
