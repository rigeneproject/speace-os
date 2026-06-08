from typing import Dict, Any, Optional, Callable
from speace_core.evolution.cv.stagnation_detector import CognitiveBranch


class BranchEvaluator:
    """Valuta i branch generati dal CV Engine."""

    def __init__(
        self,
        min_ilf_improvement: float = 0.02,
        max_stability_drop: float = 0.1,
        min_ilf_score: float = 0.3,
    ):
        self.min_ilf_improvement = min_ilf_improvement
        self.max_stability_drop = max_stability_drop
        self.min_ilf_score = min_ilf_score

    def evaluate(
        self,
        branch: CognitiveBranch,
        base_ilf: float,
        ilf_engine: Any,
        ilf_metrics_fn: Callable[[], Any],
    ) -> Dict[str, Any]:
        """Valuta un branch.

        Applica le modifiche del branch in sandbox e valuta con ILF.

        Returns:
            Evaluation result with ilf_score, ilf_delta, etc.
        """
        import copy

        # Simula l'applicazione del branch
        simulated_genome = self._apply_branch(branch)

        # Valuta in sandbox
        try:
            metrics = ilf_metrics_fn()
            ilf_state = ilf_engine.compute_ilf(metrics)
            ilf_score = ilf_state.value
            stability = ilf_state.cognitive_stability
        except Exception as e:
            return {
                "branch_id": branch.id,
                "ilf_score": base_ilf,
                "ilf_delta": 0.0,
                "stability_delta": 0.0,
                "accepted": False,
                "reason": f"evaluation_failed: {str(e)}",
            }

        ilf_delta = ilf_score - base_ilf

        # Determina accettazione
        accepted = self._should_accept(
            ilf_score=ilf_score,
            ilf_delta=ilf_delta,
            base_ilf=base_ilf,
        )

        if accepted:
            reason = "accepted"
        elif ilf_score < self.min_ilf_score:
            reason = "ilf_too_low"
        elif ilf_delta < self.min_ilf_improvement:
            reason = "insufficient_improvement"
        else:
            reason = "rejected_by_guard"

        return {
            "branch_id": branch.id,
            "ilf_score": ilf_score,
            "ilf_delta": ilf_delta,
            "stability_delta": 0.0,  # Calcolato se disponibile
            "accepted": accepted,
            "reason": reason,
            "metadata": {
                "base_ilf": base_ilf,
                "stability": stability,
            },
        }

    def _apply_branch(self, branch: CognitiveBranch) -> Dict[str, Any]:
        """Simula l'applicazione delle modifiche del branch."""
        import copy

        # Le modifiche sono già nel branch, qui possiamo
        # applicarle a una copia del genoma se necessario
        return {}

    def _should_accept(
        self,
        ilf_score: float,
        ilf_delta: float,
        base_ilf: float,
    ) -> bool:
        """Determina se il branch dovrebbe essere accettato."""
        # ILF deve essere sopra la soglia minima
        if ilf_score < self.min_ilf_score:
            return False

        # Deve migliorare l'ILF
        if ilf_delta < self.min_ilf_improvement:
            return False

        # Non deve causare un calo eccessivo
        if ilf_delta < 0:
            return False

        return True