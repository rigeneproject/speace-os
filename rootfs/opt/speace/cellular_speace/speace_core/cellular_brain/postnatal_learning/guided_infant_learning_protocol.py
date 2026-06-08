"""GuidedInfantLearningProtocol — T156.

A human-guided infant learning session where simple events are shown/described
and SPEACE associates them with sounds, images, text, cause-effect, and memory.

Protocol steps:
1. Human shows/describes a simple event.
2. SPEACE observes via PassiveMultisensoryObserver (opt-in).
3. SPEACE receives textual description.
4. SPEACE binds sensory symbol + text label in SymbolicGroundingEngine.
5. SPEACE records an episodic memory trace.
6. SPEACE generates a narrative event.
7. In future sessions, SPEACE can recall the association.

Constraints:
- opt-in sensors only
- no person recognition
- no persistent raw recording without consent
- only lightweight features/metadata
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


class GuidedInfantLearningProtocol:
    """Human-guided infant learning session protocol."""

    def __init__(
        self,
        observer: Any,
        grounding_engine: Any,
        narrative_engine: Any,
        episodic_memory: Any,
        data_root: str = "data/postnatal_learning/infant_protocol",
    ) -> None:
        self._observer = observer
        self._grounding = grounding_engine
        self._narrative = narrative_engine
        self._memory = episodic_memory
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._session_log = self._data_root / "sessions.jsonl"
        self._associations: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    # Session API
    # ------------------------------------------------------------------ #

    def present_event(
        self,
        event_label: str,
        description: str,
        expected_sound: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Human presents a simple event; SPEACE learns the association.

        Args:
            event_label: short symbolic label, e.g. "red_ball_rolling".
            description: human description of the event.
            expected_sound: optional sound label associated.

        Returns:
            Session record with associations.
        """
        session_id = f"infant_{uuid.uuid4().hex[:8]}"

        # 1. Sensory observation (if sensors are opt-in enabled)
        sensory = self._capture_sensory()

        # 2. Ground symbolic label with assembly
        assembly_id = f"asm_{event_label}_{uuid.uuid4().hex[:6]}"
        self._ground_assembly(assembly_id, event_label)

        # 3. Record episodic trace
        self._record_episodic(session_id, event_label, description, sensory, expected_sound)

        # 4. Narrative event
        self._record_narrative(session_id, event_label, description, sensory)

        record = {
            "session_id": session_id,
            "timestamp": time.time(),
            "event_label": event_label,
            "description": description,
            "expected_sound": expected_sound,
            "sensory_snapshot": sensory,
        }
        self._associations[event_label] = record
        self._persist(record)
        return record

    def recall_event(self, event_label: str) -> Optional[Dict[str, Any]]:
        """Recall a previously learned event by label."""
        return self._associations.get(event_label)

    def recall_by_description(self, description_fragment: str) -> List[Dict[str, Any]]:
        """Recall events whose description contains a fragment."""
        results = []
        for record in self._associations.values():
            if description_fragment.lower() in record.get("description", "").lower():
                results.append(record)
        return results

    def list_learned_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return all learned event associations."""
        items = list(self._associations.values())
        items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return items[:limit]

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _capture_sensory(self) -> Dict[str, Any]:
        if not any(
            [
                getattr(self._observer, "_camera_enabled", False),
                getattr(self._observer, "_microphone_enabled", False),
                getattr(self._observer, "_screen_enabled", False),
            ]
        ):
            return {"enabled": False}
        try:
            snap = self._observer.multisensory_snapshot()
            return {
                "enabled": True,
                "run_id": snap.get("run_id"),
                "timestamp": snap.get("timestamp"),
                "camera_available": snap.get("camera", {}).get("available", False),
                "microphone_available": snap.get("microphone", {}).get("available", False),
                "screen_available": snap.get("screen", {}).get("available", False),
            }
        except Exception:
            return {"enabled": True, "error": "capture_failed"}

    def _ground_assembly(self, assembly_id: str, label: str) -> None:
        if self._grounding is not None:
            try:
                self._grounding.ground_assembly(assembly_id, label)
            except Exception:
                pass

    def _record_episodic(
        self,
        session_id: str,
        label: str,
        description: str,
        sensory: Dict[str, Any],
        expected_sound: Optional[str],
    ) -> None:
        if self._memory is None:
            return
        try:
            from speace_core.cellular_brain.memory.morphology_events import (
                MorphologyEvent,
                MorphologyEventType,
            )

            event = MorphologyEvent(
                event_id=session_id,
                event_type=MorphologyEventType.EPISODE_EVENT_RECORDED,
                timestamp=time.time(),
                source_id="guided_infant_learning_protocol",
                target_id=label,
                metadata={
                    "description": description,
                    "sensory": sensory,
                    "expected_sound": expected_sound,
                },
            )
            self._memory.record_event(event)
        except Exception:
            pass

    def _record_narrative(
        self,
        session_id: str,
        label: str,
        description: str,
        sensory: Dict[str, Any],
    ) -> None:
        if self._narrative is None:
            return
        try:
            self._narrative.record(
                event_type="infant_learning_event",
                description=f"Learned: {label} — {description}",
                importance=7,
                metadata={
                    "session_id": session_id,
                    "sensory_enabled": sensory.get("enabled", False),
                },
            )
        except Exception:
            pass

    def _persist(self, record: Dict[str, Any]) -> None:
        try:
            with self._session_log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass
