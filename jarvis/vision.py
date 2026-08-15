"""Capture one webcam frame in memory for a multimodal Ollama model."""

from __future__ import annotations

import base64
from typing import Any


def capture_frame(config: dict[str, Any]) -> str:
    import cv2

    camera = cv2.VideoCapture(int(config.get("camera_index", 0)), cv2.CAP_DSHOW)
    try:
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, int(config.get("width", 640)))
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, int(config.get("height", 480)))
        frame = None
        for _ in range(5):
            ok, candidate = camera.read()
            if ok:
                frame = candidate
        if frame is None:
            raise RuntimeError("the webcam did not return a frame")
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise RuntimeError("the webcam frame could not be encoded")
        return base64.b64encode(encoded.tobytes()).decode("ascii")
    finally:
        camera.release()

