from typing import Any, Dict, List, Optional, Callable
import copy
import time
from dataclasses import dataclass, field
from enum import Enum


class MutationResult(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REJECTED_ILF_DECREASE = "rejected_ilf_decrease"
    REJECTED_STABILITY_LOSS = "rejected_stability_loss"
    REJECTED_SANDBOX_FAILED = "rejected_sandbox_failed"
    REVERTED = "reverted"


@dataclass
class MutationRecord:
    """Record di una mutazione per audit."""

    timestamp: float
    gene_name: str
    action: str
    old_value: Any
    new_value: Any
    result: MutationResult
    ilf_before: float
    ilf_after: float
    reason: Optional[str] = None


@dataclass
class RollbackPoint:
    """Punto di rollback per recovery."""

    timestamp: float
    generation: int
    state_snapshot: Dict[str, Any]
    ilf_state: Dict[str, float]
    description: str


class SafetyLayer:
    """Livello di sicurezza per l'evoluzione.

    Responsabilità:
    - Rollback: recovery a stati precedenti
    - Sandbox test: valutazione mutazioni prima dell'applicazione
    - Mutation guard: validazione mutazioni
    """

    def __init__(self, max_rollback_points: int = 50):
        self.max_rollback_points = max_rollback_points
        self._rollback_stack: List[RollbackPoint] = []
        self._mutation_log: List[MutationRecord] = []
        self._current_state: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------------ #
    # State Snapshot & Rollback
    # ------------------------------------------------------------------ #

    def capture_state(
        self,
        state: Dict[str, Any],
        ilf_state: Dict[str, float],
        generation: int,
        description: str = "",
    ) -> RollbackPoint:
        """Cattura uno snapshot dello stato per potential rollback."""
        snapshot = copy.deepcopy(state)
        point = RollbackPoint(
            timestamp=time.time(),
            generation=generation,
            state_snapshot=snapshot,
            ilf_state=copy.deepcopy(ilf_state),
            description=description,
        )
        self._rollback_stack.append(point)

        # Limita la dimensione dello stack
        if len(self._rollback_stack) > self.max_rollback_points:
            self._rollback_stack.pop(0)

        self._current_state = snapshot
        return point

    def rollback(self, to_point: Optional[RollbackPoint] = None) -> Optional[Dict[str, Any]]:
        """Ripristina lo stato a un punto precedente.

        Se to_point è None, ripristina all'ultimo punto.
        """
        if not self._rollback_stack:
            return None

        if to_point is None:
            # Pop dell'ultimo punto
            point = self._rollback_stack.pop()
        else:
            # Trova e rimuovi il punto specifico
            if to_point not in self._rollback_stack:
                return None
            self._rollback_stack.remove(to_point)
            point = to_point

        self._current_state = copy.deepcopy(point.state_snapshot)
        return copy.deepcopy(point.state_snapshot)

    def get_latest_rollback(self) -> Optional[RollbackPoint]:
        """Restituisce l'ultimo punto di rollback senza applicarlo."""
        if self._rollback_stack:
            return self._rollback_stack[-1]
        return None

    def get_rollback_history(self) -> List[RollbackPoint]:
        """Restituisce la storia dei rollback points."""
        return list(self._rollback_stack)

    # ------------------------------------------------------------------ #
    # Sandbox Testing
    # ------------------------------------------------------------------ #

    def sandbox_test(
        self,
        mutation_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        current_state: Dict[str, Any],
        ilf_engine: Any,
        ilf_metrics_fn: Callable[[], Any],
    ) -> tuple[bool, Dict[str, Any], Dict[str, float]]:
        """Testa una mutazione in sandbox.

        Args:
            mutation_fn: Funzione che applica la mutazione allo stato
            current_state: Stato corrente
            ilf_engine: ILF engine per valutare
            ilf_metrics_fn: Funzione che restituisce i metrics ILF

        Returns:
            (accepted, mutated_state, ilf_after)
        """
        # Clona lo stato per il test
        test_state = copy.deepcopy(current_state)

        # Applica la mutazione in sandbox
        try:
            mutated_state = mutation_fn(test_state)
        except Exception as e:
            # Mutazione fallita - reject
            return False, current_state, {}

        # Valuta con ILF
        try:
            metrics = ilf_metrics_fn()
            ilf_after = ilf_engine.compute_ilf(metrics)
        except Exception:
            # Valutazione fallita - reject
            return False, current_state, {}

        return True, mutated_state, ilf_after.to_summary()

    # ------------------------------------------------------------------ #
    # Mutation Guard
    # ------------------------------------------------------------------ #

    def validate_mutation(
        self,
        gene_name: str,
        old_value: Any,
        new_value: Any,
        ilf_before: float,
        ilf_after: float,
        stability_before: float,
        stability_after: float,
        min_ilf_threshold: float = 0.3,
        max_ilf_drop: float = 0.1,
        max_stability_drop: float = 0.15,
    ) -> MutationResult:
        """Valida se una mutazione può essere accettata.

        Regole:
        1. ILF non deve diminuire oltre max_ilf_drop
        2. ILF non deve scendere sotto min_ilf_threshold
        3. Stabilità non deve diminuire oltre max_stability_drop
        """
        # Regola 1: ILF drop massimo
        ilf_delta = ilf_after - ilf_before
        if ilf_delta < -max_ilf_drop:
            return MutationResult.REJECTED_ILF_DECREASE

        # Regola 2: ILF minimo assoluto
        if ilf_after < min_ilf_threshold:
            return MutationResult.REJECTED_ILF_DECREASE

        # Regola 3: Stabilità
        stability_delta = stability_after - stability_before
        if stability_delta < -max_stability_drop:
            return MutationResult.REJECTED_STABILITY_LOSS

        return MutationResult.ACCEPTED

    def apply_mutation_with_guard(
        self,
        gene_name: str,
        action: str,
        old_value: Any,
        new_value: Any,
        state: Dict[str, Any],
        ilf_before: float,
        ilf_engine: Any,
        ilf_metrics_fn: Callable[[], Any],
        stability_before: float = 1.0,
    ) -> tuple[MutationResult, Dict[str, Any], Optional[float]]:
        """Applica una mutazione con validazione del guard.

        Returns:
            (result, new_state, ilf_after)
        """
        # Calcola ilf_after stimato
        try:
            metrics = ilf_metrics_fn()
            ilf_state = ilf_engine.compute_ilf(metrics)
            ilf_after = ilf_state.value
            stability_after = ilf_state.cognitive_stability
        except Exception:
            ilf_after = ilf_before  # Non peggiora se non riesce a misurare
            stability_after = stability_before

        # Valida
        result = self.validate_mutation(
            gene_name,
            old_value,
            new_value,
            ilf_before,
            ilf_after,
            stability_before,
            stability_after,
        )

        # Log della mutazione
        record = MutationRecord(
            timestamp=time.time(),
            gene_name=gene_name,
            action=action,
            old_value=old_value,
            new_value=new_value,
            result=result,
            ilf_before=ilf_before,
            ilf_after=ilf_after,
        )
        self._mutation_log.append(record)

        if result == MutationResult.ACCEPTED:
            return result, state, ilf_after
        else:
            # Non applica la mutazione
            return result, state, ilf_before

    # ------------------------------------------------------------------ #
    # Query & Audit
    # ------------------------------------------------------------------ #

    def get_mutation_log(
        self,
        gene_name: Optional[str] = None,
        result: Optional[MutationResult] = None,
    ) -> List[MutationRecord]:
        """Restituisce il log delle mutazioni con filtri."""
        log = list(self._mutation_log)
        if gene_name:
            log = [r for r in log if r.gene_name == gene_name]
        if result:
            log = [r for r in log if r.result == result]
        return log

    def get_accepted_mutations(self) -> List[MutationRecord]:
        return self.get_mutation_log(result=MutationResult.ACCEPTED)

    def get_rejected_mutations(self) -> List[MutationRecord]:
        return [r for r in self._mutation_log if r.result.value.startswith("rejected")]

    def get_reversion_count(self) -> int:
        return sum(1 for r in self._mutation_log if r.result == MutationResult.REVERTED)

    def get_acceptance_rate(self) -> float:
        if not self._mutation_log:
            return 0.0
        accepted = sum(1 for r in self._mutation_log if r.result == MutationResult.ACCEPTED)
        return accepted / len(self._mutation_log)

    def clear_history(self) -> None:
        """Pulisce la storia (usare con cautela!)."""
        self._rollback_stack.clear()
        self._mutation_log.clear()
        self._current_state = None