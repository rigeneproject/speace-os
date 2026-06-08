from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cyber_physical.cyber_physical_models import (
    CyberPhysicalMode,
    ExternalSignal,
    SensorStream,
)


class SensorStreamManager:
    """T60 — Gestore di stream sensoriali simulati/read-only."""

    def __init__(self):
        self._streams: Dict[str, SensorStream] = {}
        self._signals: Dict[str, List[ExternalSignal]] = {}

    def create_stream(
        self,
        stream_id: str,
        source_id: str,
        signal_type: str,
        mode: str = CyberPhysicalMode.SIMULATED_READ_ONLY.value,
    ) -> SensorStream:
        if mode not in (
            CyberPhysicalMode.SIMULATED_READ_ONLY.value,
            CyberPhysicalMode.SANDBOXED_READ_ONLY.value,
            CyberPhysicalMode.PASSIVE_MONITORING.value,
            CyberPhysicalMode.QUARANTINED.value,
            CyberPhysicalMode.BLOCKED.value,
        ):
            mode = CyberPhysicalMode.BLOCKED.value
        stream = SensorStream(
            stream_id=stream_id,
            source_id=source_id,
            signal_type=signal_type,
            mode=mode,
            active=mode != CyberPhysicalMode.BLOCKED.value,
        )
        self._streams[stream_id] = stream
        self._signals[stream_id] = []
        return stream

    def ingest_signal(self, stream_id: str, signal: ExternalSignal) -> bool:
        stream = self._streams.get(stream_id)
        if stream is None or not stream.active:
            return False
        if stream.mode == CyberPhysicalMode.BLOCKED.value:
            return False
        signal.timestamp = signal.timestamp or datetime.now(timezone.utc).isoformat()
        self._signals[stream_id].append(signal)
        stream.sample_count += 1
        stream.last_timestamp = signal.timestamp
        return True

    def list_streams(self) -> List[SensorStream]:
        return list(self._streams.values())

    def get_stream_snapshot(self, stream_id: str) -> Optional[Dict[str, Any]]:
        stream = self._streams.get(stream_id)
        if stream is None:
            return None
        return {
            "stream": stream.model_dump(),
            "signal_count": len(self._signals.get(stream_id, [])),
        }

    def deactivate_stream(self, stream_id: str) -> bool:
        stream = self._streams.get(stream_id)
        if stream is None:
            return False
        stream.active = False
        return True

    def validate_signal(self, signal: ExternalSignal) -> bool:
        if signal.confidence < 0.0 or signal.confidence > 1.0:
            return False
        if signal.noise_score > 0.8:
            return False
        if signal.safety_relevance > 1.0:
            return False
        return True
