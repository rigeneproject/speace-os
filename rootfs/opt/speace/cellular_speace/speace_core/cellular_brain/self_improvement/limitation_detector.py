import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LimitationSignal(BaseModel):
    id: str
    source: str
    category: str
    severity: float
    confidence: float
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    detected_at: str


class LimitationDiagnosis(BaseModel):
    id: str
    signals: List[LimitationSignal] = Field(default_factory=list)
    primary_category: str
    root_cause_hypothesis: str
    affected_modules: List[str] = Field(default_factory=list)
    recurrence_score: float = 0.0
    urgency_score: float = 0.0
    confidence: float = 0.0
    recommended_action_type: str = "no_action"


class LimitationDetector:
    """T45 — Detect functional and structural limitations from metrics,
    audit reports, morphological memory, and regression guard."""

    def __init__(
        self,
        memory=None,
        regression_guard=None,
        recovery_policy=None,
        genome_database=None,
        thresholds: Optional[Dict[str, float]] = None,
    ):
        self.memory = memory
        self.regression_guard = regression_guard
        self.recovery_policy = recovery_policy
        self.genome_database = genome_database
        self.thresholds = thresholds or {
            "cognitive_delta": -0.03,
            "phi_delta": -0.03,
            "energy_delta": -0.05,
            "semantic_recall_rate": 0.2,
            "cellular_resilience_score": 0.4,
            "suppression_cost": 0.15,
        }

    # ------------------------------------------------------------------ #
    # Detection methods
    # ------------------------------------------------------------------ #

    def detect_from_metrics(self, metrics: Dict[str, Any]) -> List[LimitationSignal]:
        signals: List[LimitationSignal] = []
        now = datetime.now(timezone.utc).isoformat()

        cognitive_delta = metrics.get("cognitive_delta", metrics.get("cognitive_score_delta", 0.0))
        if cognitive_delta < self.thresholds["cognitive_delta"]:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="cognitive_regression",
                    severity=abs(cognitive_delta) * 10,
                    confidence=0.8,
                    description=f"Cognitive score delta {cognitive_delta:.4f} below threshold",
                    evidence={"cognitive_delta": cognitive_delta},
                    detected_at=now,
                )
            )

        phi_delta = metrics.get("phi_delta", metrics.get("coherence_phi_delta", 0.0))
        if phi_delta < self.thresholds["phi_delta"]:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="phi_regression",
                    severity=abs(phi_delta) * 10,
                    confidence=0.8,
                    description=f"Coherence phi delta {phi_delta:.4f} below threshold",
                    evidence={"phi_delta": phi_delta},
                    detected_at=now,
                )
            )

        energy_delta = metrics.get("energy_delta", metrics.get("energy_efficiency_delta", 0.0))
        if energy_delta < self.thresholds["energy_delta"]:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="energy_regression",
                    severity=abs(energy_delta) * 10,
                    confidence=0.7,
                    description=f"Energy efficiency delta {energy_delta:.4f} below threshold",
                    evidence={"energy_delta": energy_delta},
                    detected_at=now,
                )
            )

        # Semantic recall weak
        recall_rate = metrics.get("semantic_recall_success_rate", 0.0)
        semantic_enabled = metrics.get("semantic_memory_enabled", False)
        if semantic_enabled and recall_rate < self.thresholds["semantic_recall_rate"]:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="semantic_recall_weak",
                    severity=1.0 - recall_rate,
                    confidence=0.75,
                    description=f"Semantic recall rate {recall_rate:.4f} below threshold",
                    evidence={"recall_rate": recall_rate},
                    detected_at=now,
                )
            )

        # Semantic association missing
        assembly_count = metrics.get("semantic_assembly_count", 0)
        association_count = metrics.get("semantic_association_count", 0)
        if assembly_count > 0 and association_count == 0:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="semantic_association_missing",
                    severity=0.6,
                    confidence=0.85,
                    description="Assemblies exist but no associative links detected",
                    evidence={"assembly_count": assembly_count, "association_count": association_count},
                    detected_at=now,
                )
            )

        # Routing no effect
        routing_enabled = metrics.get("region_signal_routing_enabled", False)
        routing_score = metrics.get("regional_signal_flow_score", None)
        if routing_enabled and routing_score is not None and routing_score == 0.0:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="routing_no_effect",
                    severity=0.5,
                    confidence=0.7,
                    description="Routing enabled but signal flow score is zero",
                    evidence={"routing_score": routing_score},
                    detected_at=now,
                )
            )

        # Plasticity no effect
        plasticity_enabled = metrics.get("inter_region_plasticity_enabled", False)
        plasticity_events = metrics.get("inter_region_plasticity_events", None)
        if plasticity_enabled and plasticity_events is not None and plasticity_events == 0:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="plasticity_no_effect",
                    severity=0.5,
                    confidence=0.7,
                    description="Inter-region plasticity enabled but no events recorded",
                    evidence={"plasticity_events": plasticity_events},
                    detected_at=now,
                )
            )

        # Over-suppression
        suppression_cost = metrics.get("brainstem_suppression_cost", 0.0)
        if suppression_cost > self.thresholds["suppression_cost"]:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="over_suppression",
                    severity=suppression_cost * 2,
                    confidence=0.75,
                    description=f"Suppression cost {suppression_cost:.4f} exceeds threshold",
                    evidence={"suppression_cost": suppression_cost},
                    detected_at=now,
                )
            )

        # Cellular damage / resilience low
        resilience = metrics.get("cellular_resilience_score", None)
        if resilience is not None and resilience < self.thresholds["cellular_resilience_score"]:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="cellular_damage",
                    severity=1.0 - resilience,
                    confidence=0.7,
                    description=f"Cellular resilience score {resilience:.4f} below threshold",
                    evidence={"cellular_resilience_score": resilience},
                    detected_at=now,
                )
            )

        # Benchmark stagnation
        stagnation = metrics.get("benchmark_stagnation_score", 0.0)
        if stagnation > 0.8:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="metrics",
                    category="benchmark_stagnation",
                    severity=stagnation,
                    confidence=0.6,
                    description="Benchmark metrics show stagnation",
                    evidence={"stagnation": stagnation},
                    detected_at=now,
                )
            )

        return signals

    def detect_from_audit_report(self, report: Dict[str, Any]) -> List[LimitationSignal]:
        signals: List[LimitationSignal] = []
        now = datetime.now(timezone.utc).isoformat()
        verdict = report.get("verdict", "")

        if "REGRESSION" in verdict or verdict == "POLICY_UNSAFE":
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="audit_report",
                    category="insufficient_evidence" if "INSUFFICIENT" in verdict else verdict.lower().replace("_", " "),
                    severity=0.9,
                    confidence=0.85,
                    description=f"Audit verdict: {verdict}",
                    evidence={"audit_verdict": verdict},
                    detected_at=now,
                )
            )

        # Recall weak from audit
        if report.get("semantic_recall_success_rate", 1.0) < 0.2:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="audit_report",
                    category="semantic_recall_weak",
                    severity=0.7,
                    confidence=0.75,
                    description="Semantic recall weak in audit",
                    evidence={"recall_rate": report.get("semantic_recall_success_rate")},
                    detected_at=now,
                )
            )

        return signals

    def detect_from_morphological_memory(self, memory) -> List[LimitationSignal]:
        signals: List[LimitationSignal] = []
        if memory is None or not hasattr(memory, "events"):
            return signals

        now = datetime.now(timezone.utc).isoformat()
        events = getattr(memory, "events", [])

        # Count recent event types
        event_counts: Dict[str, int] = {}
        for e in events:
            key = e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type)
            event_counts[key] = event_counts.get(key, 0) + 1

        if event_counts.get("cellular_immune_alert", 0) > 3:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="morphological_memory",
                    category="cellular_damage",
                    severity=0.7,
                    confidence=0.65,
                    description="Multiple immune alerts in morphological memory",
                    evidence={"immune_alerts": event_counts.get("cellular_immune_alert")},
                    detected_at=now,
                )
            )

        if event_counts.get("region_instability_detected", 0) > 2:
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="morphological_memory",
                    category="instability",
                    severity=0.6,
                    confidence=0.6,
                    description="Repeated regional instability detected",
                    evidence={"instability_events": event_counts.get("region_instability_detected")},
                    detected_at=now,
                )
            )

        return signals

    def detect_from_regression_guard(
        self, verdict: str, details: Dict[str, Any]
    ) -> List[LimitationSignal]:
        signals: List[LimitationSignal] = []
        now = datetime.now(timezone.utc).isoformat()

        if verdict in ("POLICY_MAJOR_REGRESSION", "POLICY_UNSAFE"):
            signals.append(
                LimitationSignal(
                    id=f"lim-{uuid.uuid4().hex[:8]}",
                    source="regression_guard",
                    category="cognitive_regression" if "cognitive" in str(details).lower() else "insufficient_evidence",
                    severity=0.95,
                    confidence=0.9,
                    description=f"RegressionGuard verdict: {verdict}",
                    evidence={"regression_guard_verdict": verdict, "details": details},
                    detected_at=now,
                )
            )

        return signals

    # ------------------------------------------------------------------ #
    # Aggregation
    # ------------------------------------------------------------------ #

    def aggregate_signals(self, signals: List[LimitationSignal]) -> List[LimitationDiagnosis]:
        if not signals:
            return []

        # Group by category
        by_category: Dict[str, List[LimitationSignal]] = {}
        for s in signals:
            by_category.setdefault(s.category, []).append(s)

        diagnoses: List[LimitationDiagnosis] = []
        for category, sigs in by_category.items():
            severity_sum = sum(s.severity for s in sigs)
            confidence_avg = sum(s.confidence for s in sigs) / len(sigs)
            recurrence = len(sigs)

            action_map = {
                "cognitive_regression": "parameter_tuning",
                "phi_regression": "stability_control",
                "energy_regression": "parameter_tuning",
                "routing_no_effect": "routing_redesign",
                "plasticity_no_effect": "plasticity_redesign",
                "semantic_recall_weak": "memory_redesign",
                "semantic_association_missing": "module_addition",
                "over_suppression": "parameter_tuning",
                "cellular_damage": "module_refactor",
                "instability": "stability_control",
                "benchmark_stagnation": "benchmark_redesign",
                "genome_fitness_low": "genome_mutation",
                "insufficient_evidence": "benchmark_redesign",
            }

            # Affected modules inference
            module_map = {
                "cognitive_regression": ["neurofunctional_benchmark", "brainstem_controller"],
                "phi_regression": ["region_stability_controller", "homeostasis_engine"],
                "energy_regression": ["energy_control_agent", "brainstem_controller"],
                "routing_no_effect": ["region_signal_router"],
                "plasticity_no_effect": ["inter_region_plasticity", "stdp_plasticity_engine"],
                "semantic_recall_weak": ["semantic_recall_engine", "cell_assembly_engine"],
                "semantic_association_missing": ["semantic_memory", "cell_assembly_store"],
                "over_suppression": ["brainstem_controller", "inhibition_engine"],
                "cellular_damage": ["cellular_repair_engine", "cellular_defense_engine"],
                "instability": ["region_stability_controller"],
                "benchmark_stagnation": ["neurofunctional_benchmark"],
                "genome_fitness_low": ["genome_database", "evolution_engine"],
                "insufficient_evidence": ["neurofunctional_benchmark"],
            }

            diagnoses.append(
                LimitationDiagnosis(
                    id=f"diag-{uuid.uuid4().hex[:8]}",
                    signals=sigs,
                    primary_category=category,
                    root_cause_hypothesis=f"Recurring {category} detected across {recurrence} signal(s)",
                    affected_modules=module_map.get(category, ["unknown"]),
                    recurrence_score=min(1.0, recurrence / 5.0),
                    urgency_score=min(1.0, severity_sum / 3.0),
                    confidence=confidence_avg,
                    recommended_action_type=action_map.get(category, "no_action"),
                )
            )

        # Sort by urgency descending
        diagnoses.sort(key=lambda d: d.urgency_score, reverse=True)
        return diagnoses
