import math
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from speace_core.cellular_brain.memory.morphology_events import MorphologyEvent, MorphologyEventType


class GlobalWorkspace:
    """T71 — Global Cognitive Workspace: recurrent shared cognitive field that
    broadcasts representations across modules, acting as an "operational
    consciousness / global workspace" for emergent thought.
    """

    def __init__(
        self,
        broadcast_dim: int = 64,
        symbolic_dim: int = 16,
        num_modules: int = 10,
        seed: int = 42,
        memory: Any = None,
    ):
        self._broadcast_dim = broadcast_dim
        self._symbolic_dim = symbolic_dim
        self._num_modules = num_modules
        self._seed = seed
        self._rng = random.Random(seed)
        self._np_rng = np.random.default_rng(seed)
        self.memory = memory

        # Recurrent activation state (maintained across steps)
        self._recurrent_state: np.ndarray = np.zeros(broadcast_dim, dtype=np.float64)

        # Symbolic compression: learned projection matrix (broadcast_dim -> symbolic_dim)
        self._compression_matrix: np.ndarray = self._np_rng.normal(
            0.0, 0.1, size=(symbolic_dim, broadcast_dim)
        )
        self._compression_bias: np.ndarray = np.zeros(symbolic_dim, dtype=np.float64)

        # Prediction loop: transition matrix (symbolic_dim -> symbolic_dim)
        self._prediction_matrix: np.ndarray = self._np_rng.normal(
            0.0, 0.1, size=(symbolic_dim, symbolic_dim)
        )
        self._prediction_bias: np.ndarray = np.zeros(symbolic_dim, dtype=np.float64)

        # Attention weights per module (learned over time)
        self._module_attention_weights: Dict[str, float] = {}
        self._module_activity_history: Dict[str, List[float]] = {}

        # Current workspace state
        self._current_broadcast: Optional[Tuple[str, np.ndarray]] = None
        self._current_symbolic_state: np.ndarray = np.zeros(symbolic_dim, dtype=np.float64)
        self._predicted_next_symbolic_state: np.ndarray = np.zeros(symbolic_dim, dtype=np.float64)
        self._prediction_error: float = 0.0

        # Self-state model
        self._awareness_level: float = 0.0
        self._coherence: float = 0.0
        self._energy: float = 1.0
        self._tick_count: int = 0

        # Broadcast queue (allows multiple modules to submit per step)
        self._broadcast_queue: List[Tuple[str, np.ndarray]] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def broadcast(self, module_id: str, representation: List[float]) -> None:
        """Queue a representation from a module for potential broadcast."""
        vec = np.array(representation, dtype=np.float64)
        if vec.shape[0] != self._broadcast_dim:
            # Pad or truncate to broadcast_dim
            if vec.shape[0] < self._broadcast_dim:
                padded = np.zeros(self._broadcast_dim, dtype=np.float64)
                padded[: vec.shape[0]] = vec
                vec = padded
            else:
                vec = vec[: self._broadcast_dim]
        self._broadcast_queue.append((module_id, vec))
        self._log_event(
            MorphologyEventType.GLOBAL_WORKSPACE_BROADCAST_QUEUED,
            {"module_id": module_id, "queue_length": len(self._broadcast_queue)},
        )

    def broadcast_with_phase_gain(
        self,
        module_id: str,
        representation: List[float],
        phase: Optional[float] = None,
        gain_amplitude: float = 0.5,
    ) -> None:
        """T-PBGW — phase-gated broadcast.

        The representation is multiplied by ``1 + gain_amplitude * sin(phase)``
        before being queued, so the workspace sees a temporally-modulated
        copy. ``phase`` is in radians (e.g. the gamma-band phase from a
        :class:`NeuralOscillatorBank`). When ``phase`` is ``None`` the call
        behaves exactly like :meth:`broadcast`.
        """
        import math

        if phase is None:
            self.broadcast(module_id, representation)
            return
        gain = 1.0 + float(gain_amplitude) * math.sin(float(phase))
        gated = [float(v) * gain for v in representation]
        self.broadcast(module_id, gated)
        self._log_event(
            MorphologyEventType.GLOBAL_WORKSPACE_BROADCAST_QUEUED,
            {
                "module_id": module_id,
                "phase_gate": True,
                "phase": float(phase),
                "gain": gain,
            },
        )

    def broadcast_arc_deliberation(
        self,
        deliberation: Dict[str, Any],
    ) -> None:
        """T169 — encode an MM-APR council deliberation into a workspace
        representation and queue it for broadcast.

        The representation is a fixed-shape vector where:
        - First slot = emergent_confidence (0..1)
        - Slots 1..4 = one slot per agent (verifier, critic, auditor, interpreter)
          holding that agent's accept flag (-1 reject, +1 accept, 0 abstain).
        - Remaining slots = a stable hash of the deliberation_id (so two
          distinct verdicts with the same confidence produce distinct vectors).

        The workspace is then advanced by one step, which propagates the
        consensus into the recurrent state and symbolic compression,
        increasing ignition and coherence when the council reaches agreement.
        """
        vec = np.zeros(self._broadcast_dim, dtype=np.float64)
        emergent = float(deliberation.get("emergent_confidence", 0.0) or 0.0)
        accept = bool(deliberation.get("accept", False))
        vec[0] = emergent
        votes = deliberation.get("votes", []) or []
        for i, v in enumerate(votes[:4]):
            conf = float(v.get("confidence", 0.0) or 0.0)
            is_accept = bool(v.get("accept", False))
            vec[1 + i] = conf if is_accept else -conf
        # Stable hash of deliberation_id
        did = str(deliberation.get("deliberation_id", ""))
        if did:
            h = abs(hash(did)) % (10 ** 8)
            for i in range(min(8, self._broadcast_dim - 5)):
                vec[5 + i] = ((h >> (i * 4)) & 0xF) / 16.0 - 0.5
        # Module id encodes the verdict polarity
        module_id = "mmapr_consensus" if accept else "mmapr_rejection"
        self.broadcast(module_id, vec.tolist())
        # Step the workspace to propagate the broadcast
        self.step()

    def step(self) -> Dict[str, Any]:
        """Run one full workspace cycle:
        1) attention_routing selects the winning representation
        2) recurrent_activation blends it with the recurrent state
        3) symbolic_compression produces the symbolic vector
        4) prediction_loop estimates next state
        5) self_state_model updates awareness/coherence/energy
        """
        self._tick_count += 1

        # 1. Attention routing
        winning_module, winning_repr = self.attention_routing(self._broadcast_queue)
        self._current_broadcast = (winning_module, winning_repr.copy())
        self._broadcast_queue.clear()

        # 2. Recurrent activation update
        self._recurrent_state = self.recurrent_activation(winning_repr)

        # 3. Symbolic compression
        self._current_symbolic_state = self.symbolic_compression(self._recurrent_state)

        # 4. Prediction loop
        self._predicted_next_symbolic_state = self.prediction_loop(self._current_symbolic_state)

        # 5. Self-state model update
        self_state = self.self_state_model()

        # Compute prediction error for monitoring
        if self._tick_count > 1:
            self._prediction_error = float(
                np.mean(np.abs(self._predicted_next_symbolic_state - self._current_symbolic_state))
            )
        else:
            self._prediction_error = 0.0

        self._log_event(
            MorphologyEventType.GLOBAL_WORKSPACE_STEP_COMPLETED,
            {
                "tick": self._tick_count,
                "winning_module": winning_module,
                "awareness": round(self._awareness_level, 4),
                "coherence": round(self._coherence, 4),
                "energy": round(self._energy, 4),
                "prediction_error": round(self._prediction_error, 4),
            },
        )

        return {
            "tick": self._tick_count,
            "winning_module": winning_module,
            "awareness_level": self._awareness_level,
            "coherence": self._coherence,
            "energy": self._energy,
            "prediction_error": self._prediction_error,
            "symbolic_state": self._current_symbolic_state.tolist(),
            "predicted_next_symbolic_state": self._predicted_next_symbolic_state.tolist(),
        }

    def get_global_state(self) -> Dict[str, Any]:
        """Return the current global workspace state."""
        return {
            "tick": self._tick_count,
            "recurrent_state": self._recurrent_state.tolist(),
            "symbolic_state": self._current_symbolic_state.tolist(),
            "predicted_next_symbolic_state": self._predicted_next_symbolic_state.tolist(),
            "awareness_level": self._awareness_level,
            "coherence": self._coherence,
            "energy": self._energy,
            "prediction_error": self._prediction_error,
            "winning_module": self._current_broadcast[0] if self._current_broadcast else None,
            "module_attention_weights": dict(self._module_attention_weights),
        }

    def get_attention_focus(self) -> Optional[str]:
        """Return the module_id currently holding attention focus."""
        if self._current_broadcast is None:
            return None
        return self._current_broadcast[0]

    # ------------------------------------------------------------------ #
    # Core mechanisms
    # ------------------------------------------------------------------ #

    def attention_routing(
        self,
        queue: List[Tuple[str, np.ndarray]],
    ) -> Tuple[str, np.ndarray]:
        """Select which module's representation gets broadcast based on salience
        and learned attention weights. If queue is empty, returns a noise vector
        under a special "spontaneous" module id.
        """
        if not queue:
            noise = self._np_rng.normal(0.0, 0.05, size=self._broadcast_dim)
            return ("spontaneous", noise)

        # Compute salience = vector norm + variance bonus
        saliences: List[float] = []
        for module_id, vec in queue:
            norm = float(np.linalg.norm(vec))
            variance = float(np.var(vec))
            salience = norm + 0.5 * variance
            # Modulate by learned attention weight
            weight = self._module_attention_weights.get(module_id, 1.0)
            salience *= max(0.1, weight)
            saliences.append(salience)

        # Softmax over saliences for probabilistic winner-take-all
        exp_saliences = np.exp(np.array(saliences) - np.max(saliences))
        probs = exp_saliences / (np.sum(exp_saliences) + 1e-12)
        winner_idx = int(self._np_rng.choice(len(queue), p=probs))
        winning_module, winning_vec = queue[winner_idx]

        # Update attention weights with a simple Hebb-like rule:
        # winner gains a small boost, all others decay slightly
        for module_id, _ in queue:
            current = self._module_attention_weights.get(module_id, 1.0)
            if module_id == winning_module:
                self._module_attention_weights[module_id] = min(2.0, current + 0.02)
            else:
                self._module_attention_weights[module_id] = max(0.1, current * 0.995)

            # Track activity history for stability metrics
            history = self._module_activity_history.setdefault(module_id, [])
            history.append(1.0 if module_id == winning_module else 0.0)
            if len(history) > 100:
                history.pop(0)

        self._log_event(
            MorphologyEventType.GLOBAL_WORKSPACE_ATTENTION_ROUTED,
            {
                "winning_module": winning_module,
                "salience": round(saliences[winner_idx], 4),
                "queue_size": len(queue),
            },
        )
        return (winning_module, winning_vec)

    def recurrent_activation(self, broadcast_vector: np.ndarray) -> np.ndarray:
        """Maintain a recurrent activation state vector by blending the
        broadcast vector with the previous state (leaky integration).
        """
        leak = 0.7
        new_state = leak * self._recurrent_state + (1.0 - leak) * broadcast_vector
        # Apply tanh nonlinearity for bounded dynamics
        new_state = np.tanh(new_state)
        return new_state

    def symbolic_compression(self, high_dim_vector: np.ndarray) -> np.ndarray:
        """Compress high-dimensional cell assembly activations into a lower-
        dimensional symbolic vector via learned affine transform + nonlinearity.
        """
        symbolic = self._compression_matrix @ high_dim_vector + self._compression_bias
        # ReLU-like with small negative leakage for richer representation
        symbolic = np.where(symbolic > 0, symbolic, 0.01 * symbolic)
        # L2 normalize for stable symbolic geometry
        norm = np.linalg.norm(symbolic) + 1e-12
        return symbolic / norm

    def prediction_loop(self, current_symbolic_state: np.ndarray) -> np.ndarray:
        """Predict next global state based on current symbolic state."""
        predicted = self._prediction_matrix @ current_symbolic_state + self._prediction_bias
        # Smooth prediction through tanh
        predicted = np.tanh(predicted)
        # L2 normalize
        norm = np.linalg.norm(predicted) + 1e-12
        return predicted / norm

    def self_state_model(self) -> Dict[str, float]:
        """Track the workspace's own state: awareness level, coherence, energy.
        - awareness: driven by recurrent state magnitude and broadcast salience
        - coherence: inverse of variance across symbolic dimensions
        - energy: decays slowly, boosted by broadcast activity
        """
        recurrent_magnitude = float(np.linalg.norm(self._recurrent_state))
        symbolic_entropy = self._compute_entropy(self._current_symbolic_state)

        # Awareness rises with strong recurrent activity and low entropy (focused state)
        self._awareness_level = min(1.0, recurrent_magnitude / (recurrent_magnitude + 1.0))
        self._awareness_level *= (1.0 - 0.5 * symbolic_entropy)
        self._awareness_level = float(np.clip(self._awareness_level, 0.0, 1.0))

        # Coherence = 1 - normalized variance of symbolic state
        sym_std = float(np.std(self._current_symbolic_state))
        self._coherence = float(np.clip(1.0 - sym_std * 2.0, 0.0, 1.0))

        # Energy: metabolic budget — decays, then recovers slightly with each broadcast
        self._energy = max(0.0, self._energy * 0.995 + 0.05 * recurrent_magnitude)
        self._energy = float(np.clip(self._energy, 0.0, 1.0))

        return {
            "awareness_level": self._awareness_level,
            "coherence": self._coherence,
            "energy": self._energy,
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _compute_entropy(vector: np.ndarray) -> float:
        """Compute normalized Shannon entropy of a vector."""
        abs_vec = np.abs(vector) + 1e-12
        probs = abs_vec / np.sum(abs_vec)
        entropy = -np.sum(probs * np.log2(probs))
        max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
        return float(entropy / max_entropy)

    def _log_event(
        self,
        event_type: MorphologyEventType,
        metadata: Dict[str, Any],
    ) -> None:
        if self.memory is None or not hasattr(self.memory, "log_event"):
            return
        try:
            event = MorphologyEvent(
                event_id=f"evt-{uuid.uuid4().hex[:8]}",
                event_type=event_type,
                timestamp=datetime.now(timezone.utc).timestamp(),
                metadata=metadata,
            )
            self.memory.log_event(event)
        except Exception:
            pass
