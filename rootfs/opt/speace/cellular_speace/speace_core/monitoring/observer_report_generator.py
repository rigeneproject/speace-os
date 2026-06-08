"""ObserverReportGenerator — T103 daily/observer report generation.

Aggregates organismic state, historical alerts, anomalies, and trends
into a unified ObserverReport (JSON + Markdown).
"""

import json
import pathlib
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from speace_core.monitoring.alert_engine import AlertEngine
from speace_core.monitoring.anomaly_panel import AnomalyPanel
from speace_core.monitoring.observer_report import (
    AlertSummary,
    AnomalySummary,
    ObserverReport,
    Recommendation,
    ReportMeta,
    TrendAnalysis,
)
from speace_core.monitoring.organism_state_collector import OrganismStateCollector


class ObserverReportGenerator:
    """Generates a read-only observer report from current state and historical data."""

    def __init__(
        self,
        data_root: str = "data",
        alerts_path: str = "data/monitoring/alerts.jsonl",
    ) -> None:
        self.data_root = pathlib.Path(data_root)
        self.collector = OrganismStateCollector(data_root=data_root)
        self.alert_engine = AlertEngine(alerts_path=alerts_path)
        self.anomaly_panel = AnomalyPanel()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate(self, lookback_hours: int = 24) -> ObserverReport:
        now = time.time()
        cutoff = now - (lookback_hours * 3600)

        # Current state snapshot
        current_state = self.collector.collect_all()
        current_state["timestamp"] = now

        # Alert summary
        alert_summary = self._build_alert_summary(cutoff, current_state)

        # Anomaly summary
        anomaly_summary = self._build_anomaly_summary(cutoff)

        # Trend analysis
        trend = self._build_trend_analysis(cutoff)

        # Recommendations
        recommendations = self._build_recommendations(current_state, alert_summary, trend)

        # Verdict
        verdict = self._compute_verdict(alert_summary, trend, recommendations)

        return ObserverReport(
            meta=ReportMeta(
                lookback_window_hours=lookback_hours,
            ),
            organismic_summary={
                "body": current_state.get("body", {}),
                "cognition": current_state.get("cognition", {}),
                "dynamics": current_state.get("dynamics", {}),
                "identity": current_state.get("identity", {}),
                "drives": current_state.get("drives", {}),
                "safety": current_state.get("safety", {}),
                "embodiment": current_state.get("embodiment", {}),
            },
            alert_summary=alert_summary,
            anomaly_summary=anomaly_summary,
            trend_analysis=trend,
            recommendations=recommendations,
            verdict=verdict,
        )

    # ------------------------------------------------------------------ #
    # Builders
    # ------------------------------------------------------------------ #

    def _build_alert_summary(self, cutoff: float, current_state: Dict[str, Any]) -> AlertSummary:
        alerts = self._read_jsonl_since(self.alert_engine.alerts_path, cutoff)
        counts = Counter(a.get("severity", "unknown") for a in alerts)

        # Health score range over window
        health_scores: List[float] = []
        # We don't have per-tick historical states, so compute health on current state
        # and assume min/max from alert density as heuristic
        current_health = self.alert_engine.health_score(current_state)
        health_scores.append(current_health)
        # If alerts are dense, health was likely low
        if alerts:
            # Heuristic: health drops with alert density
            density = len(alerts) / max(1, (alerts[-1].get("timestamp", time.time()) - alerts[0].get("timestamp", time.time())) / 3600)
            estimated_min = max(0.0, current_health - min(density * 0.1, 0.5))
            health_scores.append(estimated_min)

        return AlertSummary(
            total_count=len(alerts),
            critical_count=counts.get("critical", 0),
            warning_count=counts.get("warning", 0),
            info_count=counts.get("info", 0),
            health_score_current=current_health,
            health_score_min=min(health_scores) if health_scores else 0.0,
            health_score_max=max(health_scores) if health_scores else current_health,
            recent_alerts=alerts[-20:][::-1],  # last 20, most recent first
        )

    def _build_anomaly_summary(self, cutoff: float) -> AnomalySummary:
        interventions = self._read_jsonl_since(
            self.data_root / "regulation" / "stabilizer_interventions.jsonl", cutoff
        )
        patterns = Counter(i.get("pattern_detected", "unknown") for i in interventions)
        return AnomalySummary(
            total_interventions=len(interventions),
            pattern_counts=dict(patterns),
            recent_interventions=interventions[-10:][::-1],
            overall_status="critical" if len(interventions) > 10 else "warning" if len(interventions) > 3 else "normal",
        )

    def _build_trend_analysis(self, cutoff: float) -> TrendAnalysis:
        snaps = self._read_jsonl_since(
            self.data_root / "morphological_memory" / "snapshots.jsonl", cutoff
        )
        if len(snaps) < 2:
            return TrendAnalysis()

        first = snaps[0]
        last = snaps[-1]

        phi_start = first.get("coherence_phi", 0.0)
        phi_end = last.get("coherence_phi", 0.0)
        chaos_start = first.get("chaos_score", 0.0)
        chaos_end = last.get("chaos_score", 0.0)
        rigidity_start = first.get("rigidity_score", 0.0)
        rigidity_end = last.get("rigidity_score", 0.0)
        drift_start = first.get("drift", 0.0)
        drift_end = last.get("drift", 0.0)
        pred_start = first.get("prediction_error", 0.0)
        pred_end = last.get("prediction_error", 0.0)
        branch_start = first.get("branching_ratio", 0.0)
        branch_end = last.get("branching_ratio", 0.0)

        phi_delta = phi_end - phi_start
        chaos_delta = chaos_end - chaos_start
        rigidity_delta = rigidity_end - rigidity_start
        drift_delta = drift_end - drift_start
        pred_delta = pred_end - pred_start
        branch_delta = branch_end - branch_start

        # Trend direction: if phi increased and chaos/rigidity decreased = improving
        if phi_delta > 0.05 and chaos_delta < 0 and rigidity_delta < 0:
            direction = "improving"
        elif phi_delta < -0.05 or chaos_delta > 0.1 or rigidity_delta > 0.1:
            direction = "degrading"
        else:
            direction = "stable"

        return TrendAnalysis(
            coherence_phi_delta=phi_delta,
            chaos_score_delta=chaos_delta,
            rigidity_score_delta=rigidity_delta,
            drift_delta=drift_delta,
            prediction_error_delta=pred_delta,
            branching_ratio_delta=branch_delta,
            trend_direction=direction,
        )

    def _build_recommendations(
        self,
        current_state: Dict[str, Any],
        alert_summary: AlertSummary,
        trend: TrendAnalysis,
    ) -> List[Recommendation]:
        recs: List[Recommendation] = []

        # Safety recommendations
        safety = current_state.get("safety", {})
        risk = safety.get("risk_level", "low")
        if risk in ("high", "critical"):
            recs.append(Recommendation(
                category="safety",
                message="Consider reviewing pending proposals and blocked actions.",
                severity="warning" if risk == "high" else "critical",
                confidence=0.85,
            ))

        # Drive recommendations
        drives = current_state.get("drives", {})
        drive_list = drives.get("drives", [])
        for d in drive_list:
            if d.get("urgency", 0.0) > 0.7:
                recs.append(Recommendation(
                    category="drive",
                    message=f"Drive '{d.get('name', 'unknown')}' urgency is elevated. Consider modulation.",
                    severity="warning",
                    confidence=0.75,
                ))

        # Dynamics recommendations
        if trend.chaos_score_delta > 0.1:
            recs.append(Recommendation(
                category="stability",
                message="Chaos is increasing. Consider increasing stability bias.",
                severity="warning",
                confidence=0.8,
            ))
        if trend.rigidity_score_delta > 0.1:
            recs.append(Recommendation(
                category="stability",
                message="Rigidity is increasing. Consider reducing exploration drive.",
                severity="warning",
                confidence=0.8,
            ))

        # Identity recommendations
        identity = current_state.get("identity", {})
        if identity.get("divergence_detected", False):
            recs.append(Recommendation(
                category="identity",
                message="Identity divergence detected. Review distributed node sync.",
                severity="critical",
                confidence=0.9,
            ))

        return recs

    def _compute_verdict(
        self,
        alert_summary: AlertSummary,
        trend: TrendAnalysis,
        recommendations: List[Recommendation],
    ) -> str:
        if alert_summary.critical_count > 0 or any(r.severity == "critical" for r in recommendations):
            return "INTERVENTION_RECOMMENDED"
        if alert_summary.warning_count > 3 or trend.trend_direction == "degrading":
            return "WATCH"
        return "STABLE"

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _read_jsonl_since(path: pathlib.Path, cutoff: float) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("timestamp")
                    if isinstance(ts, (int, float)) and ts >= cutoff:
                        entries.append(entry)
        except OSError:
            return []
        return entries
