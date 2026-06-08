"""CircadianValidator — validate circadian transitions and sleep quality (T112).

Tracks phase-transition correctness, consolidation outcomes, narrative
compression, and drive rebalancing across sleep/wake cycles.
"""

import json
import pathlib
import time
from typing import Any, Dict, List, Optional


class CircadianValidator:
    """Validates circadian rhythm integrity and sleep efficacy."""

    EXPECTED_PHASE_ORDER = ("awake", "pre_sleep", "sleep", "consolidation", "post_sleep")

    def __init__(self, narrative_engine: Any = None) -> None:
        self.narrative_engine = narrative_engine
        self._transition_log: List[Dict[str, Any]] = []
        self._consolidation_log: List[Dict[str, Any]] = []
        self._last_phase: Optional[str] = None
        self._sleep_cycles_completed: int = 0

    # ------------------------------------------------------------------ #
    # Event hooks
    # ------------------------------------------------------------------ #

    def record_phase_transition(self, old_phase: str, new_phase: str) -> None:
        now = time.time()
        self._transition_log.append({
            "timestamp": now,
            "from": old_phase,
            "to": new_phase,
        })
        if new_phase == "awake" and old_phase == "post_sleep":
            self._sleep_cycles_completed += 1
        self._last_phase = new_phase

    def record_consolidation(self, result: Dict[str, Any]) -> None:
        self._consolidation_log.append({
            "timestamp": time.time(),
            "result": result,
        })

    # ------------------------------------------------------------------ #
    # Validation rules
    # ------------------------------------------------------------------ #

    def validate(self, orchestrator: Any) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Phase-order correctness
        phase_order_valid = self._validate_phase_order()
        if not phase_order_valid:
            errors.append("circadian_phase_order_violation")

        # 2. Consolidation presence after sleep
        consolidation_ok = self._validate_consolidation_presence()
        if not consolidation_ok:
            warnings.append("missing_consolidation_after_sleep")

        # 3. Narrative compression proxy
        narrative_compression = self._compute_narrative_compression(orchestrator)

        # 4. Drive rebalancing proxy
        drive_balance = self._compute_drive_balance(orchestrator)

        # 5. Sleep efficiency
        sleep_efficiency = self._compute_sleep_efficiency()

        report = {
            "timestamp": time.time(),
            "phase_order_valid": phase_order_valid,
            "consolidation_present": consolidation_ok,
            "narrative_compression_ratio": narrative_compression,
            "drive_balance_score": drive_balance,
            "sleep_efficiency": sleep_efficiency,
            "sleep_cycles_completed": self._sleep_cycles_completed,
            "errors": errors,
            "warnings": warnings,
            "is_valid": len(errors) == 0,
        }

        if self.narrative_engine is not None:
            try:
                self.narrative_engine.record(
                    event_type="circadian_validation",
                    description=f"T112: valid={report['is_valid']}, cycles={self._sleep_cycles_completed}, efficiency={sleep_efficiency:.2f}",
                    importance=5,
                    metadata=report,
                )
            except Exception:
                pass

        return report

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _validate_phase_order(self) -> bool:
        if not self._transition_log:
            return True
        order = {p: i for i, p in enumerate(self.EXPECTED_PHASE_ORDER)}
        for i in range(len(self._transition_log)):
            prev = self._transition_log[i]["from"]
            curr = self._transition_log[i]["to"]
            if prev not in order or curr not in order:
                continue
            prev_idx = order[prev]
            curr_idx = order[curr]
            # Valid transitions: next phase in sequence, or post_sleep -> awake wrap-around
            expected_next = (prev_idx + 1) % len(self.EXPECTED_PHASE_ORDER)
            if curr_idx != expected_next:
                return False
        return True

    def _validate_consolidation_presence(self) -> bool:
        # Expect at least one consolidation entry after each completed sleep cycle
        return len(self._consolidation_log) >= self._sleep_cycles_completed

    def _compute_narrative_compression(self, orchestrator: Any) -> float:
        """Proxy: ratio of compressed vs raw narrative events."""
        narrative = getattr(orchestrator, "_narrative_engine", None)
        if narrative is None:
            return 0.0
        events = getattr(narrative, "_events", [])
        if not events:
            return 0.0
        compressed = sum(1 for e in events if getattr(e, "compressed", False))
        return compressed / len(events)

    def _compute_drive_balance(self, orchestrator: Any) -> float:
        """Proxy: std-dev of drive energies (lower = more balanced)."""
        drives = getattr(orchestrator, "_drives", None)
        if drives is None:
            return 0.0
        values = [getattr(d, "energy", 0.5) for d in drives]
        if not values:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return max(0.0, 1.0 - (variance ** 0.5))

    def _compute_sleep_efficiency(self) -> float:
        if self._sleep_cycles_completed == 0:
            return 0.0
        # Simple proxy: ratio of consolidations per cycle vs expected 1.0
        ratio = len(self._consolidation_log) / self._sleep_cycles_completed
        return min(1.0, ratio)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self, path: str = "data/runtime/circadian_validation.jsonl") -> None:
        p = pathlib.Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": time.time(),
                "cycles": self._sleep_cycles_completed,
                "transitions": self._transition_log,
                "consolidations": self._consolidation_log,
            }, ensure_ascii=False) + "\n")
