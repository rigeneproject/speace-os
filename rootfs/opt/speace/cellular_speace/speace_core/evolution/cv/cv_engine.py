from typing import Optional, Dict, Any, List, Callable
import time
import uuid

from speace_core.evolution.cv.stagnation_detector import (
    CognitiveBranch,
    BranchStatus,
    StagnationDetector,
    BranchGenerator,
    BranchGeneratorConfig,
)
from speace_core.evolution.cv.branch_evaluator import BranchEvaluator


class CVEngine:
    """Cosmic Virus Engine - Motore di innovazione strutturale.

    Responsabilità:
    - Rilevare stagnazione
    - Generare branch cognitivi/architetturali/memoria/apprendimento
    - Valutare branch tramite ILF
    - Promuovere i migliori

    Attivazione:
    - Solo se delta_ilf < threshold per N cicli consecutivi
    """

    def __init__(
        self,
        ilf_engine: Any,
        tracker: Optional[Any] = None,
        stagnation_config: Optional[Dict[str, Any]] = None,
        max_active_branches: int = 5,
        exploration_depth: int = 3,
    ):
        self.ilf_engine = ilf_engine
        self.tracker = tracker
        self.max_active_branches = max_active_branches
        self.exploration_depth = exploration_depth

        # Componenti
        stag_config = stagnation_config or {}
        self._stagnation_detector = StagnationDetector(
            window_size=stag_config.get("window_size", 5),
            min_delta_threshold=stag_config.get("min_delta_threshold", 0.01),
            consecutive_cycles=stag_config.get("consecutive_cycles", 3),
        )

        branch_config = BranchGeneratorConfig(
            max_branch_depth=exploration_depth,
        )
        self._branch_generator = BranchGenerator(branch_config)

        self._branch_evaluator = BranchEvaluator(
            min_ilf_improvement=stag_config.get("min_ilf_improvement", 0.02),
            max_stability_drop=stag_config.get("max_stability_drop", 0.1),
            min_ilf_score=stag_config.get("min_ilf_score", 0.3),
        )

        # Stato
        self._active_branches: List[CognitiveBranch] = []
        self._branch_history: List[CognitiveBranch] = []
        self._ilf_history: List[float] = []
        self._base_ilf: float = 0.5
        self._is_active = False

    # ------------------------------------------------------------------ #
    # Main Interface
    # ------------------------------------------------------------------ #

    def should_activate(
        self,
        current_ilf: float,
        ilf_history: Optional[List[float]] = None,
    ) -> tuple[bool, Dict[str, Any]]:
        """Verifica se il CV Engine dovrebbe attivarsi.

        Returns:
            (should_activate, details)
        """
        if ilf_history:
            self._ilf_history = ilf_history

        self._ilf_history.append(current_ilf)

        # Mantieni solo storia rilevante
        max_history = self._stagnation_detector.window_size * 3
        if len(self._ilf_history) > max_history:
            self._ilf_history = self._ilf_history[-max_history:]

        is_stagnant, details = self._stagnation_detector.is_stagnant(
            self._ilf_history,
            current_ilf,
        )

        details["current_ilf"] = current_ilf
        details["is_stagnant"] = is_stagnant

        return is_stagnant, details

    def activate(
        self,
        base_ilf: float,
        current_genome: Dict[str, Any],
        ilf_metrics_fn: Callable[[], Any],
    ) -> List[CognitiveBranch]:
        """Attiva il CV Engine e genera branch.

        Returns:
            Lista di branch generati
        """
        self._is_active = True
        self._base_ilf = base_ilf

        # Pulisci branch obsoleti
        self._prune_inactive_branches()

        # Genera nuovi branch
        new_branches = self._generate_branches(current_genome)

        # Valuta branch esistenti non valutati
        self._evaluate_all_branches(ilf_metrics_fn)

        # Limita branch attivi
        if len(self._active_branches) > self.max_active_branches:
            self._active_branches = self._active_branches[: self.max_active_branches]

        return self._active_branches

    def deactivate(self) -> None:
        """Disattiva il CV Engine."""
        self._is_active = False

    def evaluate_cycle(
        self,
        current_ilf: float,
        current_genome: Dict[str, Any],
        ilf_metrics_fn: Callable[[], Any],
    ) -> Dict[str, Any]:
        """Valuta un ciclo del CV Engine.

        Returns:
            Stats sul ciclo
        """
        stats = {
            "timestamp": time.time(),
            "is_active": self._is_active,
            "active_branches": len(self._active_branches),
            "total_branches": len(self._branch_history),
        }

        if not self._is_active:
            should_act, details = self.should_activate(current_ilf)
            stats["should_activate"] = should_act
            stats["activation_reason"] = details.get("reason", "unknown")
            return stats

        # Valuta branch
        if self._active_branches:
            best_branch = max(
                self._active_branches,
                key=lambda b: b.ilf_score if b.ilf_score > 0 else b.ilf_before,
            )
            stats["best_branch"] = best_branch.to_summary()
            stats["best_ilf_delta"] = best_branch.ilf_delta

        # Check se abbiamo un branch da promuovere
        promotable = [b for b in self._active_branches if b.ilf_delta > 0.02]
        if promotable:
            stats["has_promotable"] = True
            stats["promote_candidates"] = [b.id for b in promotable]
        else:
            stats["has_promotable"] = False

        return stats

    # ------------------------------------------------------------------ #
    # Branch Management
    # ------------------------------------------------------------------ #

    def _generate_branches(
        self, current_genome: Dict[str, Any]
    ) -> List[CognitiveBranch]:
        """Genera nuovi branch."""
        new_branches = []

        # Numero di branch da generare
        num_branches = min(3, self.max_active_branches - len(self._active_branches))

        for i in range(num_branches):
            # Scegli un parent (casuale tra i migliori esistenti, o None per nuovo)
            parent = None
            if self._active_branches:
                sorted_branches = sorted(
                    self._active_branches,
                    key=lambda b: b.ilf_score if b.ilf_score > 0 else b.ilf_before,
                    reverse=True,
                )
                # Probabilità di avere un parent
                if sorted_branches and (i == 0 or len(self._active_branches) > 1):
                    parent = sorted_branches[0]

            branch = self._branch_generator.generate_branch(
                parent=parent,
                trigger_reason="stagnation",
                current_genome=current_genome,
            )
            branch.ilf_before = self._base_ilf

            new_branches.append(branch)
            self._active_branches.append(branch)
            self._branch_history.append(branch)

            # Registra nel tracker
            if self.tracker:
                self.tracker.record_cv_event(
                    branch_id=branch.id,
                    branch_name=branch.name,
                    parent_branch=parent.id if parent else None,
                    trigger_reason="stagnation",
                    ilf_before=self._base_ilf,
                    status="exploring",
                    explored_depth=branch.depth,
                )

        return new_branches

    def _evaluate_all_branches(
        self, ilf_metrics_fn: Callable[[], Any]
    ) -> None:
        """Valuta tutti i branch attivi."""
        for branch in self._active_branches:
            if branch.status == BranchStatus.EVALUATED:
                continue

            if branch.depth >= self.exploration_depth and branch.ilf_delta <= 0:
                # Profondità massima e nessun miglioramento - rimuovi
                branch.mark_pruned()
                continue

            result = self._branch_evaluator.evaluate(
                branch=branch,
                base_ilf=branch.ilf_before,
                ilf_engine=self.ilf_engine,
                ilf_metrics_fn=ilf_metrics_fn,
            )

            branch.mark_evaluated(
                ilf_score=result["ilf_score"],
                ilf_delta=result["ilf_delta"],
            )

            # Aggiorna tracker
            if self.tracker:
                self.tracker.record_cv_event(
                    branch_id=branch.id,
                    branch_name=branch.name,
                    parent_branch=branch.parent_id,
                    ilf_before=branch.ilf_before,
                    ilf_after=result["ilf_score"],
                    ilf_delta=result["ilf_delta"],
                    status="evaluated",
                    explored_depth=branch.depth,
                )

    def _prune_inactive_branches(self) -> None:
        """Rimuove branch obsoleti o falliti."""
        # Rimuovi branch valutati e non promettenti
        to_remove = []
        for branch in self._active_branches:
            if branch.status == BranchStatus.EVALUATED:
                if branch.ilf_delta < 0 and branch.depth >= 2:
                    to_remove.append(branch)
                elif branch.age > 300:  # 5 minuti
                    to_remove.append(branch)

        for branch in to_remove:
            branch.mark_pruned()
            self._active_branches.remove(branch)

            if self.tracker:
                self.tracker.record_branch(
                    branch_id=branch.id,
                    branch_name=branch.name,
                    status="pruned",
                    ilf_score=branch.ilf_score,
                )

    def promote_best_branch(self) -> Optional[CognitiveBranch]:
        """Promuove il miglior branch."""
        if not self._active_branches:
            return None

        # Trova il migliore
        best = max(
            self._active_branches,
            key=lambda b: b.ilf_delta,
        )

        if best.ilf_delta <= 0:
            return None

        best.mark_promoted()

        if self.tracker:
            self.tracker.record_branch(
                branch_id=best.id,
                branch_name=best.name,
                status="promoted",
                ilf_score=best.ilf_score,
            )

        return best

    # ------------------------------------------------------------------ #
    # Accessors
    # ------------------------------------------------------------------ #

    def get_active_branches(self) -> List[CognitiveBranch]:
        return list(self._active_branches)

    def get_best_branch(self) -> Optional[CognitiveBranch]:
        if not self._active_branches:
            return None
        return max(
            self._active_branches,
            key=lambda b: b.ilf_score if b.ilf_score > 0 else b.ilf_before,
        )

    def get_branch(self, branch_id: str) -> Optional[CognitiveBranch]:
        for branch in self._branch_history:
            if branch.id == branch_id:
                return branch
        return None

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "is_active": self._is_active,
            "active_branches": len(self._active_branches),
            "total_branches": len(self._branch_history),
            "exploration_depth": self.exploration_depth,
            "base_ilf": self._base_ilf,
            "ilf_history_len": len(self._ilf_history),
        }