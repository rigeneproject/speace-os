import math
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EmergenceMetrics:
    """Measure whether the system forms emergent structures after perturbation."""

    def __init__(self, history_window: int = 10):
        self.history_window = history_window
        self._pre_perturbation: Optional[Dict[str, float]] = None
        self._post_perturbation: Optional[Dict[str, float]] = None
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Core metrics
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_modularity_gain(
        pre_modularity: float,
        post_modularity: float,
    ) -> float:
        return round(max(-1.0, min(1.0, post_modularity - pre_modularity)), 4)

    @staticmethod
    def compute_spontaneous_assembly_growth(
        pre_assembly_count: int,
        post_assembly_count: int,
    ) -> float:
        if pre_assembly_count == 0:
            return 0.0 if post_assembly_count == 0 else 1.0
        ratio = (post_assembly_count - pre_assembly_count) / pre_assembly_count
        return round(max(-1.0, min(1.0, ratio)), 4)

    @staticmethod
    def compute_semantic_cluster_coherence(
        cluster_strengths: List[float],
    ) -> float:
        if not cluster_strengths:
            return 0.0
        mean_strength = sum(cluster_strengths) / len(cluster_strengths)
        variance = sum((s - mean_strength) ** 2 for s in cluster_strengths) / len(cluster_strengths)
        # High coherence = high mean, low variance
        coherence = mean_strength * (1.0 - min(1.0, math.sqrt(variance)))
        return round(max(0.0, min(1.0, coherence)), 4)

    @staticmethod
    def compute_region_specialization_index(
        region_role_scores: Dict[str, float],
    ) -> float:
        if not region_role_scores:
            return 0.0
        values = list(region_role_scores.values())
        mean_score = sum(values) / len(values)
        variance = sum((v - mean_score) ** 2 for v in values) / len(values)
        # Higher variance = more specialization
        specialization = math.sqrt(variance)
        return round(min(1.0, specialization), 4)

    @staticmethod
    def compute_post_shock_recovery_gain(
        pre_phi: float,
        post_phi: float,
        baseline_phi: float,
    ) -> float:
        if baseline_phi == 0:
            return 0.0
        pre_distance = abs(pre_phi - baseline_phi)
        post_distance = abs(post_phi - baseline_phi)
        if pre_distance == 0:
            return 0.0
        gain = (pre_distance - post_distance) / pre_distance
        return round(max(-1.0, min(1.0, gain)), 4)

    @staticmethod
    def compute_novel_functional_pathways(
        pre_pathway_count: int,
        post_pathway_count: int,
        pruned_count: int,
    ) -> float:
        if pre_pathway_count == 0:
            return 0.0
        net = post_pathway_count - pre_pathway_count - pruned_count
        ratio = net / pre_pathway_count
        return round(max(-1.0, min(1.0, ratio)), 4)

    @staticmethod
    def compute_compression_of_successful_patterns(
        pattern_count: int,
        compressed_count: int,
    ) -> float:
        if pattern_count == 0:
            return 0.0
        return round(min(1.0, compressed_count / pattern_count), 4)

    @staticmethod
    def compute_cross_region_coordination_score(
        inter_region_flows: List[float],
    ) -> float:
        if not inter_region_flows:
            return 0.0
        mean_flow = sum(inter_region_flows) / len(inter_region_flows)
        # Score high when flow is significant but not saturated
        score = 2.0 * mean_flow * (1.0 - mean_flow)
        return round(max(0.0, min(1.0, score)), 4)

    # ------------------------------------------------------------------ #
    # Composite self-organization score
    # ------------------------------------------------------------------ #

    @classmethod
    def compute_self_organization_score(
        cls,
        modularity_gain: float,
        spontaneous_assembly_growth: float,
        semantic_cluster_coherence: float,
        region_specialization_index: float,
        post_shock_recovery_gain: float,
        novel_functional_pathways: float,
        compression_of_successful_patterns: float,
        cross_region_coordination_score: float,
    ) -> float:
        score = (
            0.15 * modularity_gain
            + 0.10 * spontaneous_assembly_growth
            + 0.10 * semantic_cluster_coherence
            + 0.10 * region_specialization_index
            + 0.20 * post_shock_recovery_gain
            + 0.10 * novel_functional_pathways
            + 0.10 * compression_of_successful_patterns
            + 0.15 * cross_region_coordination_score
        )
        return round(max(-1.0, min(1.0, score)), 4)

    # ------------------------------------------------------------------ #
    # Measurement cycle
    # ------------------------------------------------------------------ #

    def measure_pre(
        self,
        modularity: float = 0.0,
        assembly_count: int = 0,
        phi: float = 0.0,
        pathway_count: int = 0,
    ) -> None:
        self._pre_perturbation = {
            "modularity": modularity,
            "assembly_count": assembly_count,
            "phi": phi,
            "pathway_count": pathway_count,
        }

    def measure_post(
        self,
        modularity: float = 0.0,
        assembly_count: int = 0,
        phi: float = 0.0,
        pathway_count: int = 0,
        pruned_count: int = 0,
        cluster_strengths: Optional[List[float]] = None,
        region_role_scores: Optional[Dict[str, float]] = None,
        inter_region_flows: Optional[List[float]] = None,
        pattern_count: int = 0,
        compressed_count: int = 0,
        baseline_phi: float = 0.25,
    ) -> Dict[str, float]:
        if self._pre_perturbation is None:
            self._pre_perturbation = {
                "modularity": modularity,
                "assembly_count": assembly_count,
                "phi": phi,
                "pathway_count": pathway_count,
            }

        pre = self._pre_perturbation
        mg = self.compute_modularity_gain(pre["modularity"], modularity)
        sag = self.compute_spontaneous_assembly_growth(pre["assembly_count"], assembly_count)
        scc = self.compute_semantic_cluster_coherence(cluster_strengths or [])
        rsi = self.compute_region_specialization_index(region_role_scores or {})
        psrg = self.compute_post_shock_recovery_gain(pre["phi"], phi, baseline_phi)
        nfp = self.compute_novel_functional_pathways(pre["pathway_count"], pathway_count, pruned_count)
        csp = self.compute_compression_of_successful_patterns(pattern_count, compressed_count)
        crcs = self.compute_cross_region_coordination_score(inter_region_flows or [])

        sos = self.compute_self_organization_score(
            modularity_gain=mg,
            spontaneous_assembly_growth=sag,
            semantic_cluster_coherence=scc,
            region_specialization_index=rsi,
            post_shock_recovery_gain=psrg,
            novel_functional_pathways=nfp,
            compression_of_successful_patterns=csp,
            cross_region_coordination_score=crcs,
        )

        result = {
            "modularity_gain": mg,
            "spontaneous_assembly_growth": sag,
            "semantic_cluster_coherence": scc,
            "region_specialization_index": rsi,
            "post_shock_recovery_gain": psrg,
            "novel_functional_pathways": nfp,
            "compression_of_successful_patterns": csp,
            "cross_region_coordination_score": crcs,
            "self_organization_score": sos,
        }
        self._history.append(result)
        if len(self._history) > self.history_window:
            self._history.pop(0)
        self._post_perturbation = result
        return result

    def latest(self) -> Optional[Dict[str, float]]:
        return self._history[-1] if self._history else None

    def summary(self) -> Dict[str, Any]:
        return {
            "latest": self.latest(),
            "history_length": len(self._history),
            "mean_self_organization_score": round(
                sum(h["self_organization_score"] for h in self._history) / len(self._history), 4
            ) if self._history else 0.0,
        }
