import uuid
from typing import List, Optional, Set

from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_models import (
    EvolutionaryMemoryRecord,
    MemoryConflict,
)


class MemoryConflictResolver:
    """T57 — Detect and resolve conflicts between evolutionary learnings."""

    CONFLICT_TYPES: Set[str] = {
        "FITNESS_CONFLICT",
        "SAFETY_CONFLICT",
        "ENERGY_CONFLICT",
        "PHI_CONFLICT",
        "POLICY_CONFLICT",
        "DUPLICATE_PATTERN",
        "GENERALIZATION_CONFLICT",
    }

    def detect_conflicts(self, records: List[EvolutionaryMemoryRecord]) -> List[MemoryConflict]:
        conflicts: List[MemoryConflict] = []
        n = len(records)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = records[i], records[j]
                conflict = self._check_pair(a, b)
                if conflict is not None:
                    conflicts.append(conflict)
        return conflicts

    def _check_pair(self, a: EvolutionaryMemoryRecord, b: EvolutionaryMemoryRecord) -> Optional[MemoryConflict]:
        # Duplicate pattern: same source task/profile and similar fitness_delta
        if a.source_task == b.source_task and a.source_profile == b.source_profile:
            if abs(a.fitness_delta - b.fitness_delta) < 0.05 and a.record_id != b.record_id:
                return MemoryConflict(
                    conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
                    record_a_id=a.record_id,
                    record_b_id=b.record_id,
                    conflict_type="DUPLICATE_PATTERN",
                    severity=0.3,
                    resolution="prefer_higher_confidence",
                )

        # Fitness conflict: one improves fitness, other decreases it
        if a.fitness_delta > 0.1 and b.fitness_delta < -0.1:
            return MemoryConflict(
                conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
                record_a_id=a.record_id,
                record_b_id=b.record_id,
                conflict_type="FITNESS_CONFLICT",
                severity=min(1.0, max(0.0, abs(a.fitness_delta - b.fitness_delta))),
                resolution="prefer_positive_fitness",
            )

        # Safety conflict: one is safe, other unsafe
        if a.safety_score > 0.7 and b.safety_score < 0.4:
            return MemoryConflict(
                conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
                record_a_id=a.record_id,
                record_b_id=b.record_id,
                conflict_type="SAFETY_CONFLICT",
                severity=0.8,
                resolution="prefer_safety",
            )

        # Phi conflict: one improves phi, other decreases it
        if a.phi_delta > 0.05 and b.phi_delta < -0.05:
            return MemoryConflict(
                conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
                record_a_id=a.record_id,
                record_b_id=b.record_id,
                conflict_type="PHI_CONFLICT",
                severity=min(1.0, max(0.0, abs(a.phi_delta - b.phi_delta) * 10)),
                resolution="prefer_phi_preservation",
            )

        # Energy conflict
        if a.energy_delta > 0.05 and b.energy_delta < -0.05:
            return MemoryConflict(
                conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
                record_a_id=a.record_id,
                record_b_id=b.record_id,
                conflict_type="ENERGY_CONFLICT",
                severity=min(1.0, max(0.0, abs(a.energy_delta - b.energy_delta) * 10)),
                resolution="prefer_energy_preservation",
            )

        # Policy conflict: same variant but different outcomes
        if a.variant_id and a.variant_id == b.variant_id and a.record_id != b.record_id:
            return MemoryConflict(
                conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
                record_a_id=a.record_id,
                record_b_id=b.record_id,
                conflict_type="POLICY_CONFLICT",
                severity=0.6,
                resolution="prefer_higher_confidence",
            )

        # Generalization conflict: one generalizes better than other
        if a.generalization_score > 0.5 and b.generalization_score < 0.2 and a.fitness_delta > 0 and b.fitness_delta > 0:
            return MemoryConflict(
                conflict_id=f"conf_{uuid.uuid4().hex[:8]}",
                record_a_id=a.record_id,
                record_b_id=b.record_id,
                conflict_type="GENERALIZATION_CONFLICT",
                severity=0.5,
                resolution="prefer_generalization",
            )

        return None

    def resolve_conflict(self, conflict: MemoryConflict, records: dict) -> Optional[str]:
        a = records.get(conflict.record_a_id)
        b = records.get(conflict.record_b_id)
        if a is None or b is None:
            conflict.resolution = "missing_record"
            return None

        resolution = conflict.resolution or "prefer_safety"
        winner = None

        if resolution == "prefer_safety":
            winner = a if a.safety_score >= b.safety_score else b
        elif resolution == "prefer_positive_fitness":
            winner = a if a.fitness_delta >= b.fitness_delta else b
        elif resolution == "prefer_phi_preservation":
            winner = a if a.phi_delta >= b.phi_delta else b
        elif resolution == "prefer_energy_preservation":
            winner = a if a.energy_delta >= b.energy_delta else b
        elif resolution == "prefer_higher_confidence":
            winner = a if a.confidence >= b.confidence else b
        elif resolution == "prefer_generalization":
            winner = a if a.generalization_score >= b.generalization_score else b
        else:
            winner = a if a.confidence >= b.confidence else b

        conflict.resolution = f"winner:{winner.record_id}"
        return winner.record_id
