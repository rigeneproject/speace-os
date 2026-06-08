"""Causal Adaptation Loop — ponte tra CausalMemory ed EpigeneticTagsManager.

Chiude il primo anello del ciclo:
    esperienza → memoria causale → epigenetica → ristrutturazione → nuova esperienza

Legge gli insights dalla CausalMemory e li traduce in marcature epigenetiche
(metilazione/acetilazione) che modulano l'espressione genica dell'organismo.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.autonomic.causal_memory import (
    CausalInsight,
    CausalMemory,
)
from speace_core.epigenetics import EpigeneticTagsManager

logger = logging.getLogger("speace.causal_adaptation")


# ------------------------------------------------------------------ #
# Mapping: insight pattern → azione epigenetica
# ------------------------------------------------------------------ #

# Ogni insight può suggerire più azioni della forma "action:gene".
# Questa tabella traduce le azioni in chiamate a EpigeneticTagsManager.
_EPIGENETIC_ACTIONS: Dict[str, str] = {
    "methylate:plasticity": "methylate:plasticity",
    "acetylate:energy_conservation": "acetylate:energy_conservation",
    "methylate:energy_expression": "methylate:energy_expression",
    "acetylate:repair_expression": "acetylate:repair_expression",
    "methylate:routing_habit": "methylate:routing_habit",
    "acetylate:plasticity": "acetylate:plasticity",
    "acetylate:energy_expression": "acetylate:energy_expression",
    "silence:plasticity": "silence:plasticity",
}


class CausalAdaptationLoop:
    """Chiude il loop: causal insights → epigenetic tagging → modulazione ANS.

    Usage:
        loop = CausalAdaptationLoop(causal_memory, epigenetics)
        loop.tick()  # chiamato periodicamente da ANS.pulse()
    """

    def __init__(
        self,
        causal_memory: CausalMemory,
        epigenetics: EpigeneticTagsManager,
        adaptation_interval: int = 10,  # ogni N pulse
    ):
        self.causal_memory = causal_memory
        self.epigenetics = epigenetics
        self.adaptation_interval = adaptation_interval

        self._tick_count = 0
        self._last_adaptation: Dict[str, float] = {}  # pattern → tick

    # ------------------------------------------------------------------ #
    # Main
    # ------------------------------------------------------------------ #

    def tick(self) -> List[Dict[str, Any]]:
        """Esegue un passo del loop.

        Returns:
            Lista di azioni epigenetiche applicate (vuota se nessuna).
        """
        self._tick_count += 1
        if self._tick_count % self.adaptation_interval != 0:
            return []

        insights = self.causal_memory.analyze()
        if not insights:
            return []

        applied: List[Dict[str, Any]] = []
        for insight in insights:
            actions = self._translate_insight(insight)
            for action in actions:
                result = self._apply_epigenetic_action(action, insight)
                if result:
                    applied.append(result)
        return applied

    # ------------------------------------------------------------------ #
    # Translation
    # ------------------------------------------------------------------ #

    def _translate_insight(self, insight: CausalInsight) -> List[str]:
        """Traduce un insight in azioni epigenetiche."""
        actions: List[str] = []
        for suggested in insight.suggested_actions:
            mapped = _EPIGENETIC_ACTIONS.get(suggested)
            if mapped is not None:
                # Applica solo se confidence > 0.5
                if insight.confidence >= 0.5:
                    actions.append(mapped)
        return actions

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #

    def _apply_epigenetic_action(
        self, action: str, insight: CausalInsight,
    ) -> Optional[Dict[str, Any]]:
        """Applica un'azione epigenetica."""
        try:
            action_type, gene = action.split(":", 1)
            duration = 300.0  # 5 minuti default

            if action_type == "methylate":
                self.epigenetics.apply_methylation(
                    gene, level=insight.confidence, duration=duration,
                    source="causal_adaptation",
                )
            elif action_type == "acetylate":
                self.epigenetics.apply_acetylation(
                    gene, level=insight.confidence, duration=duration,
                    source="causal_adaptation",
                )
            elif action_type == "silence":
                self.epigenetics.silence_gene(gene, duration=duration)
            elif action_type == "activate":
                self.epigenetics.activate_gene(gene, duration=duration)
            else:
                return None

            logger.info(
                "Epigenetica: %s %s (conf=%.3f, pattern=%s)",
                action_type, gene, insight.confidence, insight.pattern_name,
            )

            self._last_adaptation[insight.pattern_name] = self._tick_count

            return {
                "action": action,
                "confidence": insight.confidence,
                "pattern": insight.pattern_name,
                "tick": self._tick_count,
            }

        except Exception as exc:
            logger.warning("Azione epigenetica fallita: %s — %s", action, exc)
            return None

    # ------------------------------------------------------------------ #
    # Query
    # ------------------------------------------------------------------ #

    def get_expression_modifier(self, gene: str, context: Dict[str, float]) -> float:
        """Legge il modificatore di espressione per un gene.

        Chiamato dall'ANS per sapere quanto un gene è attualmente espresso.
        """
        return self.epigenetics.get_expression_modifier(gene, context)

    def summary(self) -> Dict[str, Any]:
        return {
            "tick_count": self._tick_count,
            "adaptation_interval": self.adaptation_interval,
            "last_adaptations": {
                k: v for k, v in sorted(
                    self._last_adaptation.items(), key=lambda x: -x[1],
                )[:5]
            },
            "epigenetics": {
                "active_tags": len(self.epigenetics.get_active_tags()),
                "total_genes_tagged": len(self.epigenetics._tags),
            },
        }
