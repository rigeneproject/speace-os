"""SpeechOutputOrgan — cyber-physical voice emitter for SPEACE (T107).

Tries pyttsx3 for TTS. Falls back to console print.
Safety: no auto-speak, mute switch, volume limit, emission log,
and a hard timeout on runAndWait() so a hung audio driver cannot
deadlock the dialogue path.
"""

import logging
import pathlib
import threading
import time
from typing import Any, Dict, Optional


class SpeechOutputOrgan:
    """Emits SPEACE responses as speech or text."""

    # Hard cap on a single pyttsx3 utterance. The SAPI5 backend has been
    # observed to block runAndWait() indefinitely on systems without a
    # working audio device or with COM apartment issues. This cap keeps
    # /api/dialogue/speak responsive even in those cases.
    _PYTTSX3_SPEAK_TIMEOUT_S: float = 5.0

    def __init__(
        self,
        enabled: bool = True,
        muted: bool = False,
        volume: float = 0.5,
        rate: int = 150,
        log_path: str = "data/dialogue/speech_log.jsonl",
    ) -> None:
        self.enabled = enabled
        self.muted = muted
        self.volume = max(0.0, min(1.0, volume))
        self.rate = rate
        self.log_path = pathlib.Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine: Optional[Any] = None
        self._init_engine()

    def _init_engine(self) -> None:
        if not self.enabled:
            return
        try:
            import pyttsx3  # type: ignore[import-untyped]
            self._engine = pyttsx3.init()
            self._engine.setProperty("volume", self.volume)
            self._engine.setProperty("rate", self.rate)
            # Prefer Italian voice if available
            for voice in self._engine.getProperty("voices"):
                if "it-IT" in voice.id or "Italian" in voice.name:
                    self._engine.setProperty("voice", voice.id)
                    break
        except Exception as exc:
            # Avoid keeping a half-initialized engine that would deadlock
            # runAndWait() on first use.
            logging.getLogger(__name__).debug(
                "pyttsx3 init failed, TTS disabled: %s", exc
            )
            self._engine = None

    def speak(self, text: str, source: str = "dialogue_manager") -> Dict[str, Any]:
        if not self.enabled or self.muted:
            return self._log("muted", text, source)

        if self._engine:
            # Guard against runAndWait() hanging on a wedged SAPI5 backend.
            completed = threading.Event()
            error: Dict[str, BaseException] = {}

            def _run() -> None:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except BaseException as exc:  # noqa: BLE001
                    error["exc"] = exc
                finally:
                    completed.set()

            worker = threading.Thread(
                target=_run, name="speech-runAndWait", daemon=True
            )
            worker.start()
            completed.wait(timeout=self._PYTTSX3_SPEAK_TIMEOUT_S)
            if not completed.is_set():
                logging.getLogger(__name__).warning(
                    "pyttsx3 runAndWait() exceeded %ss — aborting utterance",
                    self._PYTTSX3_SPEAK_TIMEOUT_S,
                )
                # The daemon thread will eventually finish when the process
                # exits. We deliberately do not call stop() on the engine
                # here, as that itself can hang on a broken COM state; the
                # next utterance will re-attempt.
                return self._log(
                    "timeout",
                    text,
                    source,
                    detail=f"exceeded {self._PYTTSX3_SPEAK_TIMEOUT_S}s",
                )
            if "exc" in error:
                return self._log(
                    "error", text, source, detail=str(error["exc"])
                )
            return self._log("spoken", text, source)
        else:
            # Fallback: console (non-blocking, safe)
            print(f"[SPEACE speech] {text}")
            return self._log("printed", text, source)

    def _log(self, mode: str, text: str, source: str, detail: Optional[str] = None) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "timestamp": time.time(),
            "mode": mode,
            "text": text,
            "source": source,
            "volume": self.volume,
        }
        if detail:
            record["detail"] = detail
        try:
            import json
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
        return record

    def set_mute(self, muted: bool) -> None:
        self.muted = muted

    def set_volume(self, volume: float) -> None:
        self.volume = max(0.0, min(1.0, volume))
        if self._engine:
            try:
                self._engine.setProperty("volume", self.volume)
            except Exception:
                pass
