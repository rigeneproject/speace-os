from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict


class CoherenceReport(BaseModel):
    coherent: bool
    coherence_score: float
    violations: List[str] = []

    model_config = ConfigDict(arbitrary_types_allowed=True)


class CrossCloneCoherenceChecker:
    """Checks identity coherence across distributed clones."""

    def __init__(self, min_coherence_score: float = 0.7):
        self.min_coherence_score = min_coherence_score

    def check_coherence(
        self,
        clone_states: Dict[str, Dict[str, Any]],
    ) -> CoherenceReport:
        violations = []
        scores = []

        if len(clone_states) < 2:
            return CoherenceReport(
                coherent=True,
                coherence_score=1.0,
                violations=[],
            )

        # Check species_orientation consistency
        orientations = [
            state.get("species_orientation", "")
            for state in clone_states.values()
        ]
        if len(set(orientations)) > 1:
            violations.append("species_orientation_mismatch")
            scores.append(0.0)
        else:
            scores.append(1.0)

        # Check epigenome invariant compliance
        for clone_id, state in clone_states.items():
            epigenome = state.get("epigenome", {})
            if epigenome.get("quarantined", 0) > 0.5:
                violations.append(f"clone_{clone_id}_quarantined")
                scores.append(0.5)

        # Compute overall coherence score
        coherence_score = sum(scores) / len(scores) if scores else 1.0
        coherent = coherence_score >= self.min_coherence_score and not violations

        return CoherenceReport(
            coherent=coherent,
            coherence_score=coherence_score,
            violations=violations,
        )
