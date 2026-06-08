from typing import Optional, Dict, Any, List, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
import time

if TYPE_CHECKING:
    from speace_core.ilf.ilf_engine import ILFEngine, ILFState
    from speace_core.experiments.experiment_tracker import ExperimentTracker
    from speace_core.evolution.safety.safety_layer import SafetyLayer


class EvolutionEngine(Enum):
    """Motore evolutivo attivo."""

    NONE = "none"
    GENETIC = "genetic"
    CV = "cv"


class CycleDecision(Enum):
    """Decisione del ciclo evolutivo."""

    IDLE = "idle"
    EVOLVE_GENETIC = "evolve_genetic"
    EVOLVE_CV = "evolve_cv"
    COOLDOWN = "cooldown"


@dataclass
class EvolutionControllerState:
    """Stato corrente del controller."""

    cycle: int
    active_engine: EvolutionEngine
    ilf_current: float
    ilf_previous: float
    delta_ilf: float
    stagnation_cycles: int
    last_engine_used: EvolutionEngine
    cooldown_remaining: int
    trend: str
    is_stagnant: bool
    should_evolve: bool


@dataclass
class EvolutionPolicy:
    """Policy di configurazione per il controller."""

    # Soglie di stagnazione
    stagnation_threshold: float = 0.01
    stagnation_window: int = 5
    max_stagnation_cycles: int = 10

    # Soglie ILF
    min_ilf_for_growth: float = 0.3
    min_ilf_for_cv: float = 0.4

    # Delta ILF per attivazione
    min_delta_ilf_for_cv: float = 0.005
    min_delta_ilf_for_genetic: float = 0.002

    # Cooldown tra evoluzioni
    cooldown_cycles: int = 3

    # Priorità engine
    cv_priority_over_genetic: bool = True

    # Limiti
    max_genetic_per_window: int = 5
    max_cv_per_window: int = 2


@dataclass
class EvolutionCycleResult:
    """Risultato di un ciclo di valutazione."""

    decision: CycleDecision
    engine_used: Optional[EvolutionEngine]
    ilf_before: float
    ilf_after: float
    delta_ilf: float
    stagnation_cycles: int
    should_evolve: bool
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvolutionController:
    """Controller che centralizza le decisioni evolutive.

    Responsabilità:
    - Monitorare l'ILF e i suoi trend
    - Rilevare stagnazione
    - Decidere quando attivare Genetic Engine o CV Engine
    - Coordinare il cooldown tra evoluzioni
    """

    def __init__(
        self,
        ilf_engine: "ILFEngine",
        tracker: Optional["ExperimentTracker"] = None,
        safety: Optional["SafetyLayer"] = None,
        policy: Optional[EvolutionPolicy] = None,
    ):
        self.ilf_engine = ilf_engine
        self.tracker = tracker
        self.safety = safety
        self.policy = policy or EvolutionPolicy()

        self._state = EvolutionControllerState(
            cycle=0,
            active_engine=EvolutionEngine.NONE,
            ilf_current=0.0,
            ilf_previous=0.0,
            delta_ilf=0.0,
            stagnation_cycles=0,
            last_engine_used=EvolutionEngine.NONE,
            cooldown_remaining=0,
            trend="stable",
            is_stagnant=False,
            should_evolve=False,
        )

        self._ilf_history: List["ILFState"] = []
        self._genetic_count_this_window = 0
        self._cv_count_this_window = 0
        self._window_start_cycle = 0

    # ------------------------------------------------------------------ #
    # Main Interface
    # ------------------------------------------------------------------ #

    def evaluate_cycle(
        self,
        ilf_state: "ILFState",
    ) -> EvolutionCycleResult:
        """Valuta un ciclo e decide l'azione evolutiva.

        Questo è il metodo principale chiamato ad ogni ciclo.
        """
        self._update_state(ilf_state)

        # Registra l'ILF
        if self.tracker:
            self.tracker.record_ilf(
                cycle=self._state.cycle,
                ilf_state=ilf_state.to_summary(),
                delta_ilf=self._state.delta_ilf,
                trend=self._state.trend,
            )

        # Controlla cooldown
        if self._state.cooldown_remaining > 0:
            return self._create_idle_result("cooldown_active")

        # Controlla stagnazione
        if self._state.is_stagnant:
            return self._handle_stagnation()

        # Controlla se l'ILF è abbastanza alto per evolversi
        if self._state.ilf_current < self.policy.min_ilf_for_growth:
            return self._create_idle_result("ilf_too_low")

        # Valuta se evolvere
        decision = self._decide_evolution()
        return decision

    def _update_state(self, ilf_state: "ILFState") -> None:
        """Aggiorna lo stato interno."""
        self._ilf_history.append(ilf_state)

        # Mantieni solo la storia rilevante
        max_history = self.policy.stagnation_window * 3
        if len(self._ilf_history) > max_history:
            self._ilf_history = self._ilf_history[-max_history:]

        self._state.ilf_previous = self._state.ilf_current
        self._state.ilf_current = ilf_state.value
        self._state.delta_ilf = self._state.ilf_current - self._state.ilf_previous

        # Trend
        self._state.trend = self.ilf_engine.get_ilf_trend(
            self._ilf_history,
            window=min(10, len(self._ilf_history)),
        )

        # Stagnazione
        self._state.is_stagnant = self.ilf_engine.detect_stagnation(
            self._ilf_history,
            window=self.policy.stagnation_window,
            threshold=self.policy.stagnation_threshold,
        )

        if self._state.is_stagnant:
            self._state.stagnation_cycles += 1
        else:
            self._state.stagnation_cycles = 0

        # Cooldown
        if self._state.cooldown_remaining > 0:
            self._state.cooldown_remaining -= 1

        # Reset window counter
        if self._state.cycle - self._window_start_cycle >= 20:
            self._genetic_count_this_window = 0
            self._cv_count_this_window = 0
            self._window_start_cycle = self._state.cycle

        self._state.cycle += 1

    def _decide_evolution(self) -> EvolutionCycleResult:
        """Decide quale motore evolutivo attivare."""
        # Controlla se possiamo evolvere
        if self._state.ilf_current < self.policy.min_ilf_for_growth:
            return self._create_idle_result("ilf_below_threshold")

        # Se stagnazione, CV ha priorità
        if self._state.is_stagnant and self.policy.cv_priority_over_genetic:
            if self._can_use_cv():
                return self._trigger_cv()
            elif self._can_use_genetic():
                return self._trigger_genetic()
            else:
                return self._create_idle_result("max_engines_reached")

        # Non stagnante: usa genetic per miglioramento incrementale
        if self._state.delta_ilf < self.policy.min_delta_ilf_for_genetic:
            if self._can_use_genetic():
                return self._trigger_genetic()
            elif self._can_use_cv():
                return self._trigger_cv()
            else:
                return self._create_idle_result("max_engines_reached")

        # L'ILF sta migliorando - idla
        return self._create_idle_result("ilf_improving")

    def _handle_stagnation(self) -> EvolutionCycleResult:
        """Gestisce la stagnazione."""
        if self._state.stagnation_cycles >= self.policy.max_stagnation_cycles:
            # Stagnazione critica - forza CV
            if self._can_use_cv():
                return self._trigger_cv()
            elif self._can_use_genetic():
                return self._trigger_genetic()
            else:
                return self._create_idle_result("max_stagnation_no_engine")

        # CV se disponibile e configured
        if self._can_use_cv():
            return self._trigger_cv()
        elif self._can_use_genetic():
            return self._trigger_genetic()

        return self._create_idle_result("stagnation_no_engine")

    def _can_use_genetic(self) -> bool:
        return self._genetic_count_this_window < self.policy.max_genetic_per_window

    def _can_use_cv(self) -> bool:
        return self._cv_count_this_window < self.policy.max_cv_per_window

    def _trigger_genetic(self) -> EvolutionCycleResult:
        self._genetic_count_this_window += 1
        self._state.active_engine = EvolutionEngine.GENETIC
        self._state.last_engine_used = EvolutionEngine.GENETIC
        self._state.cooldown_remaining = self.policy.cooldown_cycles

        reason = (
            f"Genetic triggered: delta_ilf={self._state.delta_ilf:.4f}, "
            f"trend={self._state.trend}"
        )

        # Registra
        if self.tracker:
            self.tracker.record_fitness_evolution(
                cycle=self._state.cycle,
                population_size=0,  # Verrà popolato dal genetic engine
                fitness_mean=self._state.ilf_current,
                fitness_std=0.0,
                fitness_best=self._state.ilf_current,
                diversity_score=0.0,
                stagnation_cycles=self._state.stagnation_cycles,
                active_engine="genetic",
            )

        return EvolutionCycleResult(
            decision=CycleDecision.EVOLVE_GENETIC,
            engine_used=EvolutionEngine.GENETIC,
            ilf_before=self._state.ilf_previous,
            ilf_after=self._state.ilf_current,
            delta_ilf=self._state.delta_ilf,
            stagnation_cycles=self._state.stagnation_cycles,
            should_evolve=True,
            reason=reason,
            metadata={"genetic_count": self._genetic_count_this_window},
        )

    def _trigger_cv(self) -> EvolutionCycleResult:
        self._cv_count_this_window += 1
        self._state.active_engine = EvolutionEngine.CV
        self._state.last_engine_used = EvolutionEngine.CV
        self._state.cooldown_remaining = self.policy.cooldown_cycles

        reason = (
            f"CV triggered: stagnation_cycles={self._state.stagnation_cycles}, "
            f"is_stagnant={self._state.is_stagnant}"
        )

        # Registra
        if self.tracker:
            self.tracker.record_fitness_evolution(
                cycle=self._state.cycle,
                population_size=0,
                fitness_mean=self._state.ilf_current,
                fitness_std=0.0,
                fitness_best=self._state.ilf_current,
                diversity_score=0.0,
                stagnation_cycles=self._state.stagnation_cycles,
                active_engine="cv",
            )

        return EvolutionCycleResult(
            decision=CycleDecision.EVOLVE_CV,
            engine_used=EvolutionEngine.CV,
            ilf_before=self._state.ilf_previous,
            ilf_after=self._state.ilf_current,
            delta_ilf=self._state.delta_ilf,
            stagnation_cycles=self._state.stagnation_cycles,
            should_evolve=True,
            reason=reason,
            metadata={"cv_count": self._cv_count_this_window},
        )

    def _create_idle_result(self, reason: str) -> EvolutionCycleResult:
        return EvolutionCycleResult(
            decision=CycleDecision.IDLE,
            engine_used=None,
            ilf_before=self._state.ilf_previous,
            ilf_after=self._state.ilf_current,
            delta_ilf=self._state.delta_ilf,
            stagnation_cycles=self._state.stagnation_cycles,
            should_evolve=False,
            reason=reason,
        )

    # ------------------------------------------------------------------ #
    # State Access
    # ------------------------------------------------------------------ #

    def get_state(self) -> EvolutionControllerState:
        return self._state

    def get_ilf_history(self) -> List["ILFState"]:
        return list(self._ilf_history)

    def get_policy(self) -> EvolutionPolicy:
        return self.policy

    def update_policy(self, **kwargs) -> None:
        """Aggiorna la policy."""
        for key, value in kwargs.items():
            if hasattr(self.policy, key):
                setattr(self.policy, key, value)

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "cycle": self._state.cycle,
            "active_engine": self._state.active_engine.value,
            "ilf_current": self._state.ilf_current,
            "ilf_previous": self._state.ilf_previous,
            "delta_ilf": self._state.delta_ilf,
            "trend": self._state.trend,
            "is_stagnant": self._state.is_stagnant,
            "stagnation_cycles": self._state.stagnation_cycles,
            "cooldown_remaining": self._state.cooldown_remaining,
            "last_engine_used": self._state.last_engine_used.value,
            "genetic_this_window": self._genetic_count_this_window,
            "cv_this_window": self._cv_count_this_window,
            "ilf_history_len": len(self._ilf_history),
        }