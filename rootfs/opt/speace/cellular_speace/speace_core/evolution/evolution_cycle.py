from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import hashlib
import json


@dataclass
class EvolutionCycle:
    """Un singolo ciclo evolutivo."""

    cycle: int
    trigger: str  # "genetic", "cv", "manual"
    ilf_before: float
    ilf_after: float
    delta_ilf: float
    mutations_proposed: int
    mutations_accepted: int
    duration_ms: float
    genome_hash: str
    success: bool
    metadata: Dict[str, Any]


class EvolutionCycleManager:
    """Gestisce i cicli evolutivi e la loro storia.

    Responsabilità:
    - Registrare cicli completi
    - Calcolare statistiche aggregate
    - Identificare pattern (miglioramenti, peggioramenti)
    """

    def __init__(self):
        self._cycles: List[EvolutionCycle] = []

    def record_cycle(
        self,
        cycle: int,
        trigger: str,
        ilf_before: float,
        ilf_after: float,
        mutations_proposed: int,
        mutations_accepted: int,
        duration_ms: float,
        genome_state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvolutionCycle:
        """Registra un ciclo evolutivo completato."""
        # Calcola hash del genoma
        genome_str = json.dumps(genome_state, sort_keys=True)
        genome_hash = hashlib.sha256(genome_str.encode()).hexdigest()[:16]

        ec = EvolutionCycle(
            cycle=cycle,
            trigger=trigger,
            ilf_before=ilf_before,
            ilf_after=ilf_after,
            delta_ilf=ilf_after - ilf_before,
            mutations_proposed=mutations_proposed,
            mutations_accepted=mutations_accepted,
            duration_ms=duration_ms,
            genome_hash=genome_hash,
            success=ilf_after >= ilf_before,
            metadata=metadata or {},
        )

        self._cycles.append(ec)
        return ec

    def get_recent_cycles(self, n: int = 10) -> List[EvolutionCycle]:
        """Restituisce gli ultimi N cicli."""
        return self._cycles[-n:] if len(self._cycles) >= n else self._cycles

    def get_cycle_count(self) -> int:
        return len(self._cycles)

    def get_success_rate(self, window: Optional[int] = None) -> float:
        """Calcola il tasso di successo degli ultimi cicli."""
        if not self._cycles:
            return 0.0

        cycles = self._cycles[-window:] if window else self._cycles
        successes = sum(1 for c in cycles if c.success)
        return successes / len(cycles)

    def get_average_delta_ilf(self, window: Optional[int] = None) -> float:
        """Calcola il delta ILF medio."""
        if not self._cycles:
            return 0.0

        cycles = self._cycles[-window:] if window else self._cycles
        if not cycles:
            return 0.0

        return sum(c.delta_ilf for c in cycles) / len(cycles)

    def get_trigger_distribution(self) -> Dict[str, int]:
        """Distribuzione dei trigger."""
        dist = {}
        for c in self._cycles:
            dist[c.trigger] = dist.get(c.trigger, 0) + 1
        return dist

    def get_consecutive_failures(self) -> int:
        """Numero di fallimenti consecutivi recenti."""
        count = 0
        for c in reversed(self._cycles):
            if not c.success:
                count += 1
            else:
                break
        return count

    def should_abort_evolution(self, max_consecutive_failures: int = 5) -> bool:
        """Se dovremmo abortire l'evoluzione per troppi fallimenti."""
        return self.get_consecutive_failures() >= max_consecutive_failures