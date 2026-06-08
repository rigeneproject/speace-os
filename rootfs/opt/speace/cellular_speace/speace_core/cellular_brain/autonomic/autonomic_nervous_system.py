"""Autonomic Nervous System (ANS) for SPEACE.

Trasforma l'``ignition`` da "rianimatore manuale" verso un sistema nervoso
autonomo intrinseco. Invece di un battito casuale esterno, l'ANS:

* **Metabolismo cognitivo (Liv.1)** — genera attività interna quando non
  arriva input esterno (``generate_internal_thought``), così il cervello non
  si spegne mai del tutto.
* **Goal engine (Liv.2)** — usa l'``AutonomousDriveEngine`` esistente (7 drive
  vitali) per leggere lo stato dell'organismo e produrre una *tendenza
  d'azione* che plasma l'attività spontanea (esplorare, stabilizzare,
  conservare, riparare...).
* **Riflessi vitali / auto-revive (la visione del file)** — quando rileva
  energia bassa, attività nulla o coerenza in calo, interviene da solo:
  rialza l'energia, abbassa le soglie, rinforza le sinapsi attive, inietta uno
  stimolo endogeno. Nessun comando ``ignite`` manuale necessario.
* **(Nuovo) Ciclo causale-adattativo** — scrive i propri bisogni/obiettivi
  nel campo ILF (canali endocrini ``needs``/``goals``/``alarms``) e alimenta
  la ``CausalMemory`` che, via ``CausalAdaptationLoop``, marca geni
  epigeneticamente. Il ciclo si chiude quando l'ANS legge i modificatori
  epigenetici per regolare soglie e intensità dei riflessi.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.drives.autonomous_drive_engine import (
    AutonomousDriveEngine,
)

logger = logging.getLogger("speace.ans")


@dataclass
class AutonomicPulse:
    """Esito di un battito autonomo."""

    tick: int
    energy: float
    coherence: float
    active_neurons: int
    action_tendency: str
    dominant_drive: Optional[str]
    reflexes: List[str] = field(default_factory=list)
    injected_thought: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "energy": round(self.energy, 4),
            "coherence": round(self.coherence, 4),
            "active_neurons": self.active_neurons,
            "action_tendency": self.action_tendency,
            "dominant_drive": self.dominant_drive,
            "reflexes": self.reflexes,
            "injected_thought": self.injected_thought,
        }


class AutonomicNervousSystem:
    """Anello autonomo che mantiene vivo e coerente l'organismo, senza stimoli esterni.

    Parametri nuovi (opzionali):
        causal_memory: registra outcomes e rileva pattern ripetuti
        causal_adaptation_loop: traduce pattern in marcature epigenetiche
    """

    def __init__(
        self,
        orchestrator: Any,
        drive_engine: Optional[AutonomousDriveEngine] = None,
        *,
        energy_floor: float = 0.3,
        coherence_floor: float = 0.2,
        activity_floor: int = 1,
        input_size: int = 10,
        revive_energy_target: float = 0.7,
        causal_memory: Any = None,
        causal_adaptation_loop: Any = None,
    ) -> None:
        self.orch = orchestrator
        self.drives = drive_engine or AutonomousDriveEngine()
        self.energy_floor = energy_floor
        self.coherence_floor = coherence_floor
        self.activity_floor = activity_floor
        self.input_size = input_size
        self.revive_energy_target = revive_energy_target
        self.causal_memory = causal_memory
        self.causal_adaptation_loop = causal_adaptation_loop

        self._rng = random.Random(1234)
        self._prev_coherence: Optional[float] = None
        self._last_successful_pattern: Optional[List[float]] = None
        self._pulse_count = 0

    # ------------------------------------------------------------------ #
    # Sensing — leggi i segni vitali dell'organismo
    # ------------------------------------------------------------------ #
    def _all_neurons(self) -> list:
        c = self.orch.circuit
        return c.input_neurons + c.hidden_neurons + c.output_neurons

    def sense(self) -> Dict[str, float]:
        m = self.orch.latest_metrics
        energy = float(getattr(m, "mean_energy", 0.0)) if m else 0.0
        coherence = float(getattr(m, "coherence_phi", 0.0)) if m else 0.0
        active = int(getattr(m, "active_neurons", 0)) if m else 0
        noise = float(getattr(m, "noise_level", 0.0)) if m else 0.0

        neurons = self._all_neurons()
        total = len(neurons) or 1
        idle_ratio = 1.0 - (active / total)
        novelty = 0.0
        if self._prev_coherence is not None:
            novelty = min(1.0, abs(coherence - self._prev_coherence) * 3.0)

        return {
            "uptime": min(1.0, self.orch.current_tick / 1000.0),
            "error_rate": min(1.0, noise),
            "coherence": coherence,
            "novelty_score": novelty,
            "idle_ratio": idle_ratio,
            "internal_variance": min(1.0, noise),
            "_energy": energy,
            "_active": active,
        }

    # ------------------------------------------------------------------ #
    # Epigenetic modulation
    # ------------------------------------------------------------------ #
    def _get_epigenetic_modifier(self, gene: str, context: Dict[str, float]) -> float:
        """Legge il modificatore di espressione per un gene (default 1.0)."""
        if self.causal_adaptation_loop is not None:
            try:
                return self.causal_adaptation_loop.get_expression_modifier(gene, context)
            except Exception:
                pass
        return 1.0

    # ------------------------------------------------------------------ #
    # Metabolismo cognitivo — attività interna senza input esterno
    # ------------------------------------------------------------------ #
    def generate_internal_thought(self, tendency: str) -> List[float]:
        """Produce un pattern endogeno modulato dalla tendenza dei drive."""
        pattern = [0.0] * self.input_size
        if tendency == "integrate" and self._last_successful_pattern is not None:
            return list(self._last_successful_pattern)
        if tendency in ("explore", "adapt"):
            k = self._rng.randint(2, max(2, self.input_size // 3))
            for idx in self._rng.sample(range(self.input_size), k):
                pattern[idx] = self._rng.uniform(0.5, 1.0)
            return pattern
        if tendency == "conserve":
            pattern[self._pulse_count % self.input_size] = 0.3
            return pattern
        pattern[self._pulse_count % self.input_size] = 0.7
        return pattern

    # ------------------------------------------------------------------ #
    # Riflessi vitali — auto-revive
    # ------------------------------------------------------------------ #
    def _reflex_revive_energy(self) -> None:
        for n in self._all_neurons():
            if getattr(n, "energy", 1.0) < self.revive_energy_target:
                n.energy = self.revive_energy_target
        drive = getattr(self.orch, "_homeostatic_drive", None)
        if drive is not None:
            try:
                drive.update_drive("survival", 0.9)
            except Exception:
                pass

    def _reflex_lower_thresholds(self) -> None:
        for n in self._all_neurons():
            n.threshold = max(0.15, getattr(n, "threshold", 0.5) * 0.9)

    def _reflex_reinforce_synapses(self) -> None:
        for s in self.orch.circuit.synapses:
            if getattr(s, "state", None) == "active":
                s.weight = min(1.0, s.weight * 1.03)

    # ------------------------------------------------------------------ #
    # ILF endocrine messaging
    # ------------------------------------------------------------------ #
    def _write_field_messages(self, pulse: AutonomicPulse) -> None:
        """Scrive bisogni/obiettivi/allarmi nel campo ILF.

        Questi messaggi vengono propagati a tutti i sottosistemi al prossimo
        broadcast del campo (canali ``needs``, ``goals``, ``alarms``).
        """
        needs = {
            "energy": max(0.0, 1.0 - pulse.energy),
            "coherence": max(0.0, 1.0 - pulse.coherence),
            "activity": max(0.0, 1.0 - pulse.active_neurons / 10.0),
        }
        goals = {}
        if pulse.dominant_drive:
            goals[pulse.dominant_drive] = 0.7
        alarms = []
        if pulse.energy < self.energy_floor:
            alarms.append("energy_low")
        if pulse.coherence < self.coherence_floor:
            alarms.append("coherence_low")
        if pulse.reflexes:
            alarms.append(f"reflex:{pulse.reflexes[-1]}")

        if hasattr(self.orch, "inject_field_messages"):
            try:
                self.orch.inject_field_messages(
                    needs=needs, goals=goals, alarms=alarms,
                )
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Battito autonomo
    # ------------------------------------------------------------------ #
    def pulse(self) -> AutonomicPulse:
        self._pulse_count += 1
        state = self.sense()
        energy = state.pop("_energy")
        active = int(state.pop("_active"))
        coherence = state["coherence"]

        # 0) Modulazione epigenetica: leggi modificatori e adatta soglie
        context = {"energy": energy, "coherence": coherence, "activity": float(active)}
        plasticity_mod = self._get_epigenetic_modifier("plasticity", context)
        energy_mod = self._get_epigenetic_modifier("energy_conservation", context)
        repair_mod = self._get_epigenetic_modifier("repair_expression", context)

        effective_energy_floor = self.energy_floor
        if energy_mod < 1.0:
            effective_energy_floor = self.energy_floor * (1.5 - energy_mod * 0.5)
        effective_revive_target = self.revive_energy_target
        if repair_mod > 1.0:
            effective_revive_target = min(1.0, self.revive_energy_target * repair_mod)

        # 1) Goal engine: aggiorna i drive e ottieni la tendenza d'azione.
        tendency = self.drives.step(state)
        highest = self.drives.get_highest_priority_drive()
        dominant = highest[0] if highest else None

        reflexes: List[str] = []

        # 2) Riflessi vitali (auto-revive) — soglie modulate epigeneticamente.
        if energy < effective_energy_floor:
            self._reflex_revive_energy()
            reflexes.append("revive_energy")
        if active < self.activity_floor:
            self._reflex_lower_thresholds()
            reflexes.append("lower_thresholds")
        if (
            self._prev_coherence is not None
            and coherence < self._prev_coherence
            and coherence < self.coherence_floor
        ):
            self._reflex_reinforce_synapses()
            reflexes.append("reinforce_synapses")

        # 3) Metabolismo cognitivo: attività interna, modulata da plasticità.
        injected = False
        should_think = active < self.activity_floor or tendency in ("explore", "adapt", "integrate")
        if plasticity_mod < 0.5:
            should_think = False  # plasticità soppressa → non generare pensieri
        if should_think:
            thought = self.generate_internal_thought(tendency)
            try:
                self.orch.inject(thought)
                injected = True
            except Exception:
                injected = False

        # 4) Apprendimento del successo: se la coerenza migliora, memorizza il pattern.
        if (
            self._prev_coherence is not None
            and coherence > self._prev_coherence
            and injected
        ):
            self._last_successful_pattern = self.generate_internal_thought(tendency)
            try:
                self.orch.feedback(1.0)
            except Exception:
                pass

        self._prev_coherence = coherence

        pulse_result = AutonomicPulse(
            tick=self.orch.current_tick,
            energy=energy,
            coherence=coherence,
            active_neurons=active,
            action_tendency=tendency,
            dominant_drive=dominant,
            reflexes=reflexes,
            injected_thought=injected,
        )

        # 5) Memoria causale: registra l'esito del battito.
        if self.causal_memory is not None:
            try:
                self.causal_memory.record(pulse_result.to_dict())
            except Exception:
                pass

        # 6) Loop adattativo: analizza pattern e applica marcature epigenetiche.
        if self.causal_adaptation_loop is not None:
            try:
                actions = self.causal_adaptation_loop.tick()
                if actions:
                    logger.debug(
                        "Adattamento causale: %d azioni epigenetiche applicate",
                        len(actions),
                    )
            except Exception:
                pass

        # 7) Scrivi messaggi endocrini nel campo ILF.
        self._write_field_messages(pulse_result)

        return pulse_result

    def snapshot(self) -> Dict[str, Any]:
        s: Dict[str, Any] = {
            "pulse_count": self._pulse_count,
            "drives": self.drives.snapshot(),
            "has_successful_pattern": self._last_successful_pattern is not None,
        }
        if self.causal_memory is not None:
            try:
                s["causal_memory"] = self.causal_memory.summary()
            except Exception:
                pass
        if self.causal_adaptation_loop is not None:
            try:
                s["causal_adaptation_loop"] = self.causal_adaptation_loop.summary()
            except Exception:
                pass
        return s
