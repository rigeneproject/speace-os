"""MultisensoryGroundingIntegrator — T152.

Pipeline:
    PassiveMultisensoryObserver snapshot
    → minimal feature extraction (metadata only, no raw persistence)
    → symbolic grounding
    → narrative event
    → memory trace
    → dialogue context buffer

Constraints:
- opt-in (observer sensors must be explicitly enabled)
- single snapshots, no continuous streaming
- no person recognition by default
- no persistent raw recording unless consented
- only light metadata/features
"""

from __future__ import annotations

import base64
import io
import json
import logging
import math
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from PIL import Image

    _HAS_PIL = True
except Exception:  # pragma: no cover
    _HAS_PIL = False

try:
    import numpy as np

    _HAS_NUMPY = True
except Exception:  # pragma: no cover
    _HAS_NUMPY = False


class MultisensoryGroundingIntegrator:
    """Integrates multisensory snapshots into SPEACE cognition.

    Usage:
        integrator = MultisensoryGroundingIntegrator(observer, ...)
        result = integrator.process_snapshot()
        # result is a dict of sensory symbols and features
        # dialogue context available via integrator.get_dialogue_context()
    """

    def __init__(
        self,
        observer: Any,
        narrative_engine: Optional[Any] = None,
        memory: Optional[Any] = None,
        grounding_engine: Optional[Any] = None,
        data_root: str = "data/experience/multisensory",
        max_dialogue_buffer: int = 20,
    ) -> None:
        self._observer = observer
        self._narrative_engine = narrative_engine
        self._memory = memory
        self._grounding_engine = grounding_engine

        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._dialogue_buffer: deque[Dict[str, Any]] = deque(maxlen=max_dialogue_buffer)
        self._last_camera_meta: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def process_snapshot(self) -> Optional[Dict[str, Any]]:
        """Trigger a single multisensory snapshot and ground it cognitively."""
        if not any(
            [
                getattr(self._observer, "_camera_enabled", False),
                getattr(self._observer, "_microphone_enabled", False),
                getattr(self._observer, "_screen_enabled", False),
            ]
        ):
            return None

        snap = self._observer.multisensory_snapshot()
        run_id = snap.get("run_id", f"mg_{uuid.uuid4().hex[:8]}")
        result: Dict[str, Any] = {"run_id": run_id, "timestamp": time.time(), "sensors": {}}

        for sensor_key in ("camera", "microphone", "screen"):
            sensor_data = snap.get(sensor_key)
            if not isinstance(sensor_data, dict):
                continue
            if not sensor_data.get("available"):
                continue
            features = self._extract_features(sensor_key, sensor_data)
            symbol = self._ground_symbol(sensor_key, features)
            self._publish_narrative(sensor_key, features, symbol, run_id)
            self._publish_memory(sensor_key, features, symbol, run_id)
            result["sensors"][sensor_key] = {
                "symbol": symbol,
                "features": features,
            }

        if result["sensors"]:
            self._dialogue_buffer.append(result)
            return result
        return None

    def get_dialogue_context(self, limit: int = 5) -> str:
        """Return a human-readable summary of recent sensory observations."""
        lines: List[str] = []
        for obs in list(self._dialogue_buffer)[-limit:]:
            ts = time.strftime("%H:%M:%S", time.localtime(obs.get("timestamp", time.time())))
            for sensor_key, payload in obs.get("sensors", {}).items():
                symbol = payload.get("symbol", sensor_key)
                lines.append(f"[{ts}] {symbol}")
        if not lines:
            return "Nessuna osservazione multisensoriale recente."
        return "\n".join(lines)

    def recent_symbols(self, limit: int = 10) -> List[str]:
        """Return recent symbolic labels."""
        symbols: List[str] = []
        for obs in list(self._dialogue_buffer)[-limit:]:
            for payload in obs.get("sensors", {}).values():
                sym = payload.get("symbol")
                if sym:
                    symbols.append(sym)
        return symbols

    # ------------------------------------------------------------------ #
    # Feature extraction — metadata only, no raw persistence
    # ------------------------------------------------------------------ #

    def _extract_features(
        self, sensor_key: str, sensor_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        features: Dict[str, Any] = {
            "timestamp": sensor_data.get("timestamp"),
            "format": sensor_data.get("format"),
        }

        if sensor_key == "camera":
            features["width"] = sensor_data.get("width")
            features["height"] = sensor_data.get("height")
            features["base64_length"] = sensor_data.get("base64_length")

            # Light mean-color estimate from thumbnail (no face recognition)
            if _HAS_PIL and sensor_data.get("data"):
                try:
                    raw = base64.b64decode(sensor_data["data"])
                    img = Image.open(io.BytesIO(raw))
                    thumb = img.resize((1, 1))
                    pixel = thumb.getpixel((0, 0))
                    features["mean_color_rgb"] = pixel if isinstance(pixel, tuple) else (pixel, pixel, pixel)
                except Exception:
                    logging.getLogger(__name__).warning("Grounding integration step failed for camera extraction", exc_info=True)

            # Simple motion proxy: did mean color shift vs last frame?
            if self._last_camera_meta and features.get("mean_color_rgb"):
                prev = self._last_camera_meta.get("mean_color_rgb")
                if prev and isinstance(prev, (list, tuple)) and len(prev) == 3:
                    curr = features["mean_color_rgb"]
                    delta = sum(abs(c - p) for c, p in zip(curr, prev))
                    features["motion_proxy"] = delta > 30.0
                else:
                    features["motion_proxy"] = False
            else:
                features["motion_proxy"] = False

            self._last_camera_meta = features

        elif sensor_key == "microphone":
            features["sample_rate"] = sensor_data.get("sample_rate")
            features["duration_s"] = sensor_data.get("duration_s")
            features["base64_length"] = sensor_data.get("base64_length")
            # Approximate volume RMS if numpy available
            if _HAS_NUMPY and sensor_data.get("data"):
                try:
                    pcm_bytes = base64.b64decode(sensor_data["data"])
                    pcm = np.frombuffer(pcm_bytes, dtype=np.int16)
                    if len(pcm) > 0:
                        rms = math.sqrt(float(np.mean(pcm.astype(np.float32) ** 2)))
                        # Normalise roughly to 0-1
                        features["volume_rms"] = round(min(1.0, rms / 32768.0), 4)
                except Exception:
                    logging.getLogger(__name__).warning("Grounding integration step failed for microphone extraction", exc_info=True)

        elif sensor_key == "screen":
            features["width"] = sensor_data.get("width")
            features["height"] = sensor_data.get("height")
            features["base64_length"] = sensor_data.get("base64_length")

        return features

    # ------------------------------------------------------------------ #
    # Symbolic grounding
    # ------------------------------------------------------------------ #

    def _ground_symbol(self, sensor_key: str, features: Dict[str, Any]) -> str:
        symbol = f"sensor_{sensor_key}_snapshot"

        if sensor_key == "camera" and features.get("motion_proxy"):
            symbol = "sensor_camera_motion_detected"

        if sensor_key == "microphone":
            vol = features.get("volume_rms")
            if vol is not None and vol > 0.1:
                symbol = "sensor_microphone_sound_detected"
            else:
                symbol = "sensor_microphone_silence"

        # Ground in SymbolicGroundingEngine if available
        if self._grounding_engine is not None:
            try:
                assembly_id = f"asm_{sensor_key}_{uuid.uuid4().hex[:6]}"
                self._grounding_engine.ground_assembly(assembly_id, symbol)
            except Exception:
                logging.getLogger(__name__).warning("Grounding integration step failed for symbol grounding", exc_info=True)

        return symbol

    # ------------------------------------------------------------------ #
    # Narrative event
    # ------------------------------------------------------------------ #

    def _publish_narrative(
        self,
        sensor_key: str,
        features: Dict[str, Any],
        symbol: str,
        run_id: str,
    ) -> None:
        if self._narrative_engine is None:
            return
        try:
            desc = self._build_description(sensor_key, features, symbol)
            self._narrative_engine.record(
                event_type="multisensory_snapshot",
                description=desc,
                importance=3,
                metadata={
                    "run_id": run_id,
                    "sensor": sensor_key,
                    "symbol": symbol,
                    "features": {k: v for k, v in features.items() if k != "mean_color_rgb"},
                },
            )
        except Exception:
            logging.getLogger(__name__).warning("Grounding integration step failed for narrative publish", exc_info=True)

    # ------------------------------------------------------------------ #
    # Memory trace
    # ------------------------------------------------------------------ #

    def _publish_memory(
        self,
        sensor_key: str,
        features: Dict[str, Any],
        symbol: str,
        run_id: str,
    ) -> None:
        if self._memory is None:
            return
        try:
            from speace_core.cellular_brain.memory.morphology_events import (
                MorphologyEvent,
                MorphologyEventType,
            )

            event = MorphologyEvent(
                event_id=f"mg_{run_id}_{sensor_key}",
                event_type=MorphologyEventType.SENSOR_SNAPSHOT,
                timestamp=time.time(),
                source_id="multisensory_grounding_integrator",
                target_id=sensor_key,
                metadata={
                    "symbol": symbol,
                    "features": {k: v for k, v in features.items() if k != "mean_color_rgb"},
                },
            )
            self._memory.record_event(event)
        except Exception:
            logging.getLogger(__name__).warning("Grounding integration step failed for memory publish", exc_info=True)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_description(sensor_key: str, features: Dict[str, Any], symbol: str) -> str:
        if sensor_key == "camera":
            w = features.get("width", "?")
            h = features.get("height", "?")
            motion = "motion" if features.get("motion_proxy") else "static"
            return f"Camera captured {motion} frame ({w}x{h})"
        if sensor_key == "microphone":
            dur = features.get("duration_s", "?")
            vol = features.get("volume_rms")
            if vol is not None:
                return f"Microphone recorded {dur}s snippet (volume {vol:.2f})"
            return f"Microphone recorded {dur}s snippet"
        if sensor_key == "screen":
            w = features.get("width", "?")
            h = features.get("height", "?")
            return f"Screen captured ({w}x{h})"
        return f"{sensor_key} snapshot ({symbol})"
