"""RuntimeLatentIntegrator — T117: observe-only integration of T116 into runtime.

Extracts latent vectors from internal SPEACE modules, packages them as
LatentPackets, computes drift/cosine-similarity metrics, and routes them
through a LOCAL-ONLY CrossNodeLatentBus. No remote transmission. No
automatic behavior modification.
"""

import math
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

import numpy as np

from speace_core.cellular_brain.latent_transfer.latent_packet import LatentPacket, VectorSource
from speace_core.cellular_brain.latent_transfer.cross_node_latent_bus import CrossNodeLatentBus


class RuntimeLatentIntegrator:
    """Observe-only latent vector extractor and metric tracker."""

    def __init__(
        self,
        orchestrator: Any,
        vector_dim: int = 64,
        history_window: int = 100,
        narrative_engine: Any = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.vector_dim = vector_dim
        self.history_window = history_window
        self.narrative_engine = narrative_engine

        # Local-only bus (no peers = no remote send)
        self.local_bus = CrossNodeLatentBus(
            node_id="local_runtime",
            default_vector_dim=vector_dim,
        )

        # History per source for drift tracking
        self._history: Dict[str, Deque[LatentPacket]] = {
            src: deque(maxlen=history_window)
            for src in (
                VectorSource.MEMORY,
                VectorSource.WORKSPACE,
                VectorSource.DRIVE,
                VectorSource.HEALTH,
                VectorSource.NARRATIVE,
                VectorSource.EXPERIENCE,
                VectorSource.SKILL,
            )
        }

        self._tick_count = 0
        self._last_metrics: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Main tick hook (called from runtime loop)
    # ------------------------------------------------------------------ #

    def tick(self) -> Dict[str, Any]:
        """Extract latent vectors, compute metrics, return observation report."""
        self._tick_count += 1
        packets: List[LatentPacket] = []

        # 1. GlobalWorkspace
        gw_packet = self._extract_workspace()
        if gw_packet is not None:
            packets.append(gw_packet)

        # 2. Memory / MorphologicalMemory
        mem_packet = self._extract_memory()
        if mem_packet is not None:
            packets.append(mem_packet)

        # 3. HomeostaticDrives
        drive_packet = self._extract_drives()
        if drive_packet is not None:
            packets.append(drive_packet)

        # 4. SelfModel (if present on orchestrator)
        self_packet = self._extract_self_model()
        if self_packet is not None:
            packets.append(self_packet)

        # 5. Experience / Narrative
        exp_packet = self._extract_experience()
        if exp_packet is not None:
            packets.append(exp_packet)

        # 6. DialogueManager
        dia_packet = self._extract_dialogue()
        if dia_packet is not None:
            packets.append(dia_packet)

        # 7. SkillTransfer
        skill_packet = self._extract_skill()
        if skill_packet is not None:
            packets.append(skill_packet)

        # Append to history before computing metrics
        for pkt in packets:
            hist = self._history.get(pkt.source)
            if hist is not None:
                hist.append(pkt)

        # Compute drift / similarity metrics
        metrics = self._compute_metrics(packets)
        self._last_metrics = metrics

        # Local-only bus injection (observe-only; no peers = no remote)
        for pkt in packets:
            self.local_bus._inbound.append(pkt)  # local queue only

        # Narrative log (low frequency: every 10 ticks)
        if self.narrative_engine is not None and self._tick_count % 10 == 0:
            try:
                self.narrative_engine.record(
                    event_type="latent_integrator_tick",
                    description=f"T117: {len(packets)} packets, drift={metrics.get('mean_drift', 0):.4f}",
                    importance=2,
                    metadata={
                        "tick": self._tick_count,
                        "packets": len(packets),
                        "metrics": metrics,
                    },
                )
            except Exception:
                pass

        return {
            "tick": self._tick_count,
            "packets_generated": len(packets),
            "sources": [p.source for p in packets],
            "metrics": metrics,
        }

    # ------------------------------------------------------------------ #
    # Extractors
    # ------------------------------------------------------------------ #

    def _extract_workspace(self) -> Optional[LatentPacket]:
        gw = getattr(self.orchestrator, "_global_workspace", None)
        if gw is None:
            return None
        try:
            state = gw.get_global_state()
            # Combine recurrent_state + symbolic_state into a single vector
            recurrent = state.get("recurrent_state", [])
            symbolic = state.get("symbolic_state", [])
            combined = self._pad_or_truncate(recurrent + symbolic, self.vector_dim)
            return LatentPacket(
                vector=combined,
                source=VectorSource.WORKSPACE,
                metadata={
                    "awareness": state.get("awareness_level", 0.0),
                    "coherence": state.get("coherence", 0.0),
                    "energy": state.get("energy", 0.0),
                    "prediction_error": state.get("prediction_error", 0.0),
                },
            )
        except Exception:
            return None

    def _extract_memory(self) -> Optional[LatentPacket]:
        mem = getattr(self.orchestrator, "_memory", None)
        if mem is None:
            return None
        try:
            events = getattr(mem, "events", [])
            event_count = len(events)
            # Simple proxy: event density + recency-weighted activity
            vector = [0.0] * self.vector_dim
            vector[0] = min(1.0, event_count / 1000.0)
            vector[1] = getattr(mem, "coherence_phi", 0.0)
            return LatentPacket(
                vector=vector,
                source=VectorSource.MEMORY,
                metadata={"event_count": event_count},
            )
        except Exception:
            return None

    def _extract_drives(self) -> Optional[LatentPacket]:
        hd = getattr(self.orchestrator, "_homeostatic_drive", None)
        if hd is None:
            return None
        try:
            drives = hd.list_drives()
            signals = [hd.get_drive_signal(d) for d in drives]
            vector = self._pad_or_truncate(signals, self.vector_dim)
            modulation = hd.get_global_modulation()
            return LatentPacket(
                vector=vector,
                source=VectorSource.DRIVE,
                metadata={
                    "drives": drives,
                    "modulation": modulation,
                },
            )
        except Exception:
            return None

    def _extract_self_model(self) -> Optional[LatentPacket]:
        sm = getattr(self.orchestrator, "_self_model", None)
        if sm is None:
            return None
        try:
            identity = sm.get_identity_signature()
            vector = self._pad_or_truncate(identity, self.vector_dim)
            return LatentPacket(
                vector=vector,
                source=VectorSource.HEALTH,  # closest semantic mapping
                metadata={
                    "developmental_stage": sm.get_developmental_stage(),
                    "coherent": sm.is_coherent(),
                },
            )
        except Exception:
            return None

    def _extract_experience(self) -> Optional[LatentPacket]:
        # Experience proxy via metrics_log coherence and narrative density
        metrics_log = getattr(self.orchestrator, "metrics_log", [])
        if not metrics_log:
            return None
        try:
            recent = metrics_log[-min(10, len(metrics_log)):]
            phi_values = [getattr(m, "coherence_phi", 0.0) for m in recent]
            energy_values = [getattr(m, "mean_energy", 0.0) for m in recent]
            vector = [0.0] * self.vector_dim
            vector[0] = sum(phi_values) / len(phi_values) if phi_values else 0.0
            vector[1] = sum(energy_values) / len(energy_values) if energy_values else 0.0
            # Avoid absolute counts to keep vector stationary; metadata retains the count
            return LatentPacket(
                vector=vector,
                source=VectorSource.EXPERIENCE,
                metadata={"metrics_log_len": len(metrics_log)},
            )
        except Exception:
            return None

    def _extract_dialogue(self) -> Optional[LatentPacket]:
        dm = getattr(self.orchestrator, "_dialogue_manager", None)
        if dm is None:
            return None
        try:
            turn_count = getattr(dm, "_turn_count", 0)
            state = getattr(dm, "state", "unknown")
            vector = [0.0] * self.vector_dim
            vector[0] = min(1.0, turn_count / 100.0)
            vector[1] = 1.0 if state == "active" else 0.0
            return LatentPacket(
                vector=vector,
                source=VectorSource.NARRATIVE,
                metadata={"turn_count": turn_count, "state": state},
            )
        except Exception:
            return None

    def _extract_skill(self) -> Optional[LatentPacket]:
        st = getattr(self.orchestrator, "_skill_transfer_layer", None)
        if st is None:
            return None
        try:
            stages = st.get_stages()
            candidates = getattr(st, "_registry", None)
            candidate_count = 0
            if candidates is not None:
                candidate_count = len(getattr(candidates, "_candidates", []))
            vector = [0.0] * self.vector_dim
            vector[0] = candidate_count / 100.0
            vector[1] = len(stages) / 10.0
            return LatentPacket(
                vector=vector,
                source=VectorSource.SKILL,
                metadata={"candidate_count": candidate_count, "stages": stages},
            )
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Metrics
    # ------------------------------------------------------------------ #

    def _compute_metrics(self, packets: List[LatentPacket]) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {
            "packet_count": len(packets),
            "sources": {},
            "mean_drift": 0.0,
            "mean_cosine_similarity": 0.0,
            "alignment_confidence": 0.0,
        }
        if not packets:
            return metrics

        drift_sum = 0.0
        cos_sum = 0.0
        count = 0

        for pkt in packets:
            hist = self._history.get(pkt.source)
            if hist is None:
                continue

            if len(hist) >= 2:
                prev = hist[-2]
                drift = self._euclidean_distance(prev.vector, pkt.vector)
                cos_sim = self._cosine_similarity(prev.vector, pkt.vector)
                drift_sum += drift
                cos_sum += cos_sim
                count += 1
                metrics["sources"][pkt.source] = {
                    "drift": drift,
                    "cosine_similarity": cos_sim,
                }
            else:
                metrics["sources"][pkt.source] = {
                    "drift": None,
                    "cosine_similarity": None,
                }

        if count > 0:
            metrics["mean_drift"] = drift_sum / count
            metrics["mean_cosine_similarity"] = cos_sum / count
            # Alignment confidence: high cosine + low drift = high confidence
            metrics["alignment_confidence"] = (
                metrics["mean_cosine_similarity"] * 0.5
                + (1.0 / (1.0 + metrics["mean_drift"])) * 0.5
            )

        return metrics

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _pad_or_truncate(vec: List[float], target_len: int) -> List[float]:
        if len(vec) == target_len:
            return vec
        if len(vec) < target_len:
            mean = sum(vec) / len(vec) if vec else 0.0
            return vec + [mean] * (target_len - len(vec))
        return vec[:target_len]

    @staticmethod
    def _euclidean_distance(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return float("inf")
        return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (mag_a * mag_b)))

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def latest_metrics(self) -> Dict[str, Any]:
        return dict(self._last_metrics)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "tick": self._tick_count,
            "vector_dim": self.vector_dim,
            "history_window": self.history_window,
            "local_bus": self.local_bus.snapshot(),
            "latest_metrics": self._last_metrics,
        }
