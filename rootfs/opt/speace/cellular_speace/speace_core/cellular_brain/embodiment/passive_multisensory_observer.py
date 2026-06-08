"""PassiveMultisensoryObserver — T151 Passive Multisensory Observation Layer.

Provides purely observational access to camera, microphone and screen.
All sensors are:
- opt-in   (disabled by default)
- read-only (no actuation)
- non-recording by default (no persistent storage unless explicitly requested)
- bounded   (single snapshot on demand, no continuous streams)
"""

from __future__ import annotations

import base64
import io
import time
import uuid
from typing import Any, Dict, List, Optional

try:
    from PIL import Image

    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False

try:
    import cv2

    _HAS_CV2 = True
except Exception:  # pragma: no cover
    _HAS_CV2 = False

try:
    import sounddevice as sd
    import numpy as np

    _HAS_SOUNDDEVICE = True
except Exception:  # pragma: no cover
    _HAS_SOUNDDEVICE = False

try:
    import mss

    _HAS_MSS = True
except Exception:  # pragma: no cover
    _HAS_MSS = False


class PassiveMultisensoryObserver:
    """Opt-in, read-only, non-recording multisensory observer.

    Usage:
        observer = PassiveMultisensoryObserver()
        observer.enable_camera()          # explicit opt-in
        snapshot = observer.camera_snapshot()   # returns base64 JPEG or None
    """

    def __init__(self) -> None:
        self._camera_enabled = False
        self._microphone_enabled = False
        self._screen_enabled = False

        self._camera_cap: Optional[Any] = None

    # ------------------------------------------------------------------ #
    # Opt-in toggles
    # ------------------------------------------------------------------ #

    def enable_camera(self) -> None:
        self._camera_enabled = True

    def disable_camera(self) -> None:
        self._camera_enabled = False
        if self._camera_cap is not None:
            self._camera_cap.release()
            self._camera_cap = None

    def enable_microphone(self) -> None:
        self._microphone_enabled = True

    def disable_microphone(self) -> None:
        self._microphone_enabled = False

    def enable_screen(self) -> None:
        self._screen_enabled = True

    def disable_screen(self) -> None:
        self._screen_enabled = False

    def status(self) -> Dict[str, Any]:
        return {
            "camera_enabled": self._camera_enabled,
            "microphone_enabled": self._microphone_enabled,
            "screen_enabled": self._screen_enabled,
            "camera_available": _HAS_CV2,
            "microphone_available": _HAS_SOUNDDEVICE,
            "screen_available": _HAS_MSS,
        }

    # ------------------------------------------------------------------ #
    # Camera — single frame, no recording
    # ------------------------------------------------------------------ #

    def camera_snapshot(self, jpeg_quality: int = 50) -> Optional[Dict[str, Any]]:
        """Capture a single JPEG frame from the default camera.

        Returns a dict with base64-encoded image or None if unavailable.
        No video file is written to disk.
        """
        if not self._camera_enabled:
            return None
        if not _HAS_CV2:
            return {"available": False, "error": "opencv_not_installed"}

        if self._camera_cap is None:
            self._camera_cap = cv2.VideoCapture(0)
            if not self._camera_cap.isOpened():
                self._camera_cap = None
                return {"available": False, "error": "camera_cannot_open"}

        ret, frame = self._camera_cap.read()
        if not ret or frame is None:
            return {"available": False, "error": "camera_read_failed"}

        # Encode as JPEG, bounded quality to avoid large payloads
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), max(10, min(95, jpeg_quality))]
        success, encoded = cv2.imencode(".jpg", frame, encode_params)
        if not success:
            return {"available": False, "error": "jpeg_encode_failed"}

        b64 = base64.b64encode(encoded.tobytes()).decode("ascii")
        return {
            "available": True,
            "format": "jpeg",
            "width": frame.shape[1],
            "height": frame.shape[0],
            "base64_length": len(b64),
            "data": b64,
            "timestamp": time.time(),
        }

    # ------------------------------------------------------------------ #
    # Microphone — short audio snippet, no recording
    # ------------------------------------------------------------------ #

    def microphone_snapshot(
        self,
        duration_s: float = 0.5,
        sample_rate: int = 16000,
    ) -> Optional[Dict[str, Any]]:
        """Record a short audio snippet (default 0.5 s) from the default mic.

        Returns a dict with base64 PCM or None if unavailable.
        No audio file is written to disk.
        """
        if not self._microphone_enabled:
            return None
        if not _HAS_SOUNDDEVICE:
            return {"available": False, "error": "sounddevice_not_installed"}

        duration_s = max(0.1, min(2.0, duration_s))
        frames = int(duration_s * sample_rate)

        try:
            audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="float32")
            sd.wait()
            # Convert to 16-bit PCM for compactness
            pcm = (audio * 32767).astype("int16")
            b64 = base64.b64encode(pcm.tobytes()).decode("ascii")
            return {
                "available": True,
                "format": "pcm_s16le_mono",
                "sample_rate": sample_rate,
                "duration_s": round(duration_s, 3),
                "base64_length": len(b64),
                "data": b64,
                "timestamp": time.time(),
            }
        except Exception as exc:
            return {"available": False, "error": f"microphone_capture_failed: {exc}"}

    # ------------------------------------------------------------------ #
    # Screen — single screenshot, no recording
    # ------------------------------------------------------------------ #

    def screen_snapshot(self, jpeg_quality: int = 50) -> Optional[Dict[str, Any]]:
        """Capture a single screenshot of the primary monitor.

        Returns a dict with base64 JPEG or None if unavailable.
        No video file is written to disk.
        """
        if not self._screen_enabled:
            return None
        if not _HAS_MSS:
            return {"available": False, "error": "mss_not_installed"}
        if not _HAS_PIL:
            return {"available": False, "error": "pillow_not_installed"}

        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary monitor
                screenshot = sct.grab(monitor)
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=max(10, min(95, jpeg_quality)))
                b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
                return {
                    "available": True,
                    "format": "jpeg",
                    "width": img.width,
                    "height": img.height,
                    "base64_length": len(b64),
                    "data": b64,
                    "timestamp": time.time(),
                }
        except Exception as exc:
            return {"available": False, "error": f"screen_capture_failed: {exc}"}

    # ------------------------------------------------------------------ #
    # Composite snapshot
    # ------------------------------------------------------------------ #

    def multisensory_snapshot(self) -> Dict[str, Any]:
        """Return a snapshot from every enabled sensor."""
        return {
            "run_id": f"sense_{uuid.uuid4().hex[:8]}",
            "timestamp": time.time(),
            "camera": self.camera_snapshot() if self._camera_enabled else {"enabled": False},
            "microphone": self.microphone_snapshot() if self._microphone_enabled else {"enabled": False},
            "screen": self.screen_snapshot() if self._screen_enabled else {"enabled": False},
        }
