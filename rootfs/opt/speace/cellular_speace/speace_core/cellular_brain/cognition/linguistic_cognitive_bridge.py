"""LinguisticCognitiveBridge — bidirectional bridge between GlobalWorkspace and language areas.

Connects the recurrent cognitive workspace (GlobalWorkspace) with Broca (production)
and Wernicke (comprehension), enabling linguistic expression of internal cognitive
states and absorption of language into the workspace.

Flow:
  Cognition → Language: workspace symbolic state → Broca token sequence → speech
  Language → Cognition: Wernicke assembly → workspace broadcast → cognitive integration
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from speace_core.cellular_brain.language.broca_area import DigitalBrocaArea
from speace_core.cellular_brain.language.wernicke_area import DigitalWernickeArea, SemanticAssembly
from speace_core.cellular_brain.cognition.global_workspace import GlobalWorkspace
from speace_core.cellular_brain.language.linguistic_inhibition_controller import (
    LinguisticInhibitionController,
)


class LinguisticCognitiveBridge:
    """Bidirectional bridge between GlobalWorkspace and linguistic areas.

    The bridge translates between the workspace's high-dimensional symbolic state
    and the language system's token-based representations, completing the cognitive
    loop: thought ↔ language.
    """

    def __init__(
        self,
        workspace: GlobalWorkspace,
        broca: DigitalBrocaArea,
        wernicke: DigitalWernickeArea,
        verbalisation_threshold: float = 0.3,
        workspace_broadcast_label: str = "cognition",
        inhibition_controller: Optional[LinguisticInhibitionController] = None,
    ):
        self.workspace = workspace
        self.broca = broca
        self.wernicke = wernicke
        self._verbalisation_threshold = verbalisation_threshold
        self._workspace_broadcast_label = workspace_broadcast_label
        self._inhibition = inhibition_controller or LinguisticInhibitionController()

        self._verbalisation_history: List[Dict[str, Any]] = []
        self._comprehension_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Cognition → Language: workspace state → Broca → speech
    # ------------------------------------------------------------------ #

    def verbalise_workspace_state(self) -> Optional[str]:
        """Translate the current workspace symbolic state into a verbal utterance.

        Reads the workspace's symbolic state (compressed representation of the
        current cognitive focus), maps it to a token sequence in Broca, and
        returns the verbalised text. Returns None if the state is below the
        verbalisation threshold or if linguistic inhibition is active.
        """
        if self._inhibition.is_production_inhibited():
            return None

        symbolic_state = self.workspace._current_symbolic_state
        if np.mean(np.abs(symbolic_state)) < self._verbalisation_threshold:
            return None

        tokens = self._symbolic_state_to_tokens(symbolic_state)
        if not tokens:
            return None

        self.broca.activate_sequence(tokens)
        produced: List[str] = []
        for _ in range(len(tokens) * 6):
            if self._inhibition.is_production_inhibited():
                self.broca.pause()
                break
            tok = self.broca.next_token()
            if tok is not None:
                check = self._inhibition.record_production(tok)
                if check["inhibited"]:
                    self.broca.pause()
                    break
                produced.append(tok)
            elif not self.broca.is_active:
                break

        utterance = " ".join(produced) if produced else None
        if utterance:
            self._verbalisation_history.append({
                "utterance": utterance,
                "symbolic_state_mean": float(np.mean(symbolic_state)),
                "tick": self.workspace._tick_count,
            })
        self.broca.resume()
        return utterance

    def _symbolic_state_to_tokens(self, state: np.ndarray) -> List[str]:
        """Map the symbolic state vector to a sequence of token-like symbols.

        Each dimension with absolute activation above the threshold contributes
        a token. This provides a primitive mapping from workspace state to
        linguistic symbols.
        """
        tokens: List[str] = []
        threshold = self._verbalisation_threshold
        for i, val in enumerate(state):
            if abs(val) > threshold:
                tokens.append(f"concept_{i}")
        return tokens[:8]

    # ------------------------------------------------------------------ #
    # Language → Cognition: Wernicke assembly → workspace broadcast
    # ------------------------------------------------------------------ #

    def absorb_comprehension(self, assembly: SemanticAssembly) -> bool:
        """Send a Wernicke comprehension assembly into the GlobalWorkspace.

        Converts the semantic assembly into a workspace broadcast vector,
        enabling cognitive integration of linguistic input.
        """
        vec = np.zeros(self.workspace._broadcast_dim, dtype=np.float64)

        if assembly.dominant_concept:
            h = hash(assembly.dominant_concept) % self.workspace._broadcast_dim
            vec[h] = assembly.coherence

        # Encode activation vector into the workspace
        n = min(len(assembly.activation_vector), self.workspace._broadcast_dim)
        vec[:n] = assembly.activation_vector[:n]

        self.workspace.broadcast("linguistic", vec.tolist())
        self._comprehension_history.append({
            "dominant_concept": assembly.dominant_concept,
            "coherence": assembly.coherence,
            "tick": self.workspace._tick_count,
        })
        return True

    def absorb_text(self, text: str) -> bool:
        """Convenience: receive text, process through Wernicke, broadcast to workspace."""
        from speace_core.cellular_brain.language.dialogue_manager import _tokenise
        tokens = _tokenise(text)
        self.wernicke.clear_buffer()
        self.wernicke.receive_tokens(tokens)
        assembly = self.wernicke.decode_to_assembly()
        return self.absorb_comprehension(assembly)

    # ------------------------------------------------------------------ #
    # Cog-Linguistic tick: single-step the entire bridge
    # ------------------------------------------------------------------ #

    def tick(self) -> Dict[str, Any]:
        """Full cognitive-linguistic cycle:
        1. Verbalise workspace state → Broca (with inhibition checks)
        2. Optionally absorb any pending comprehension
        Returns diagnostic info.
        """
        utterance = self.verbalise_workspace_state()
        inhibition = self._inhibition.inhibition_status()
        return {
            "utterance": utterance,
            "verbalisation_history_len": len(self._verbalisation_history),
            "comprehension_history_len": len(self._comprehension_history),
            "inhibition": inhibition,
        }

    def get_state(self) -> Dict[str, Any]:
        """Return diagnostic state snapshot."""
        return {
            "verbalisation_threshold": self._verbalisation_threshold,
            "last_utterance": self._verbalisation_history[-1] if self._verbalisation_history else None,
            "last_comprehension": self._comprehension_history[-1] if self._comprehension_history else None,
            "verbalisation_count": len(self._verbalisation_history),
            "comprehension_count": len(self._comprehension_history),
            "inhibition": self._inhibition.inhibition_status(),
        }
