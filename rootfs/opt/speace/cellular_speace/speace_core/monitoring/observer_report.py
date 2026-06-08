"""ObserverReport — Pydantic model for T103 organismic daily/observer reports.

Produces both JSON (canonical) and Markdown (human-readable) views.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from speace_core.cli import SPEACE_VERSION


class ReportMeta(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    speace_version: str = SPEACE_VERSION
    lookback_window_hours: int = 24
    report_type: str = "observer_daily"


class OrganismicSummary(BaseModel):
    body: Dict[str, Any] = Field(default_factory=dict)
    cognition: Dict[str, Any] = Field(default_factory=dict)
    dynamics: Dict[str, Any] = Field(default_factory=dict)
    identity: Dict[str, Any] = Field(default_factory=dict)
    drives: Dict[str, Any] = Field(default_factory=dict)
    safety: Dict[str, Any] = Field(default_factory=dict)
    embodiment: Dict[str, Any] = Field(default_factory=dict)


class AlertSummary(BaseModel):
    total_count: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    health_score_current: float = 0.0
    health_score_min: float = 0.0
    health_score_max: float = 0.0
    recent_alerts: List[Dict[str, Any]] = Field(default_factory=list)


class AnomalySummary(BaseModel):
    total_interventions: int = 0
    pattern_counts: Dict[str, int] = Field(default_factory=dict)
    recent_interventions: List[Dict[str, Any]] = Field(default_factory=list)
    overall_status: str = "unknown"


class TrendAnalysis(BaseModel):
    coherence_phi_delta: float = 0.0
    chaos_score_delta: float = 0.0
    rigidity_score_delta: float = 0.0
    drift_delta: float = 0.0
    prediction_error_delta: float = 0.0
    branching_ratio_delta: float = 0.0
    trend_direction: str = "stable"  # stable, improving, degrading


class Recommendation(BaseModel):
    category: str = ""  # drive, stability, safety, identity, embodiment
    message: str = ""
    severity: str = "info"  # info, warning, critical
    confidence: float = 0.0  # 0.0-1.0


class ObserverReport(BaseModel):
    meta: ReportMeta = Field(default_factory=ReportMeta)
    organismic_summary: OrganismicSummary = Field(default_factory=OrganismicSummary)
    alert_summary: AlertSummary = Field(default_factory=AlertSummary)
    anomaly_summary: AnomalySummary = Field(default_factory=AnomalySummary)
    trend_analysis: TrendAnalysis = Field(default_factory=TrendAnalysis)
    recommendations: List[Recommendation] = Field(default_factory=list)
    verdict: str = "UNKNOWN"  # STABLE, WATCH, INTERVENTION_RECOMMENDED

    def to_markdown(self) -> str:
        """Render a human-readable Markdown report."""
        lines: List[str] = []
        m = self.meta
        lines.append(f"# SPEACE Observer Report")
        lines.append(f"**Version:** {m.speace_version}  ")
        lines.append(f"**Generated:** {m.timestamp}  ")
        lines.append(f"**Lookback:** {m.lookback_window_hours}h  ")
        lines.append(f"**Verdict:** {self.verdict}")
        lines.append("")

        # Organismic Summary
        lines.append("## Organismic Summary")
        o = self.organismic_summary
        if o.body:
            lines.append(f"- **CPU:** {o.body.get('cpu', '—')}%")
            lines.append(f"- **Memory:** {o.body.get('memory_bytes', 0) / (1024**3):.2f} GB")
        if o.cognition:
            sm = o.cognition.get("self_model", {})
            lines.append(f"- **Coherence Phi:** {sm.get('coherence_phi', '—')}")
            lines.append(f"- **Stage:** {sm.get('developmental_stage', '—')}")
        if o.dynamics:
            lines.append(f"- **Chaos:** {o.dynamics.get('chaos_score', '—')}")
            lines.append(f"- **Rigidity:** {o.dynamics.get('rigidity_score', '—')}")
            lines.append(f"- **Drift:** {o.dynamics.get('drift', '—')}")
        lines.append("")

        # Alert Summary
        lines.append("## Alert Summary")
        a = self.alert_summary
        lines.append(f"- **Total Alerts:** {a.total_count}")
        lines.append(f"- **Critical:** {a.critical_count}")
        lines.append(f"- **Warning:** {a.warning_count}")
        lines.append(f"- **Info:** {a.info_count}")
        lines.append(f"- **Health Score (current):** {a.health_score_current:.4f}")
        lines.append(f"- **Health Score (range):** {a.health_score_min:.4f} - {a.health_score_max:.4f}")
        if a.recent_alerts:
            lines.append("### Recent Alerts")
            for al in a.recent_alerts[:10]:
                ts = al.get("timestamp", "—")
                sev = al.get("severity", "—")
                msg = al.get("message", "—")
                lines.append(f"- `{ts}` **{sev.upper()}** — {msg}")
        lines.append("")

        # Anomaly Summary
        lines.append("## Anomaly Summary")
        an = self.anomaly_summary
        lines.append(f"- **Total Interventions:** {an.total_interventions}")
        lines.append(f"- **Overall Status:** {an.overall_status}")
        if an.pattern_counts:
            lines.append("### Pattern Counts")
            for pattern, count in an.pattern_counts.items():
                lines.append(f"- {pattern}: {count}")
        lines.append("")

        # Trend Analysis
        lines.append("## Trend Analysis")
        t = self.trend_analysis
        lines.append(f"- **Direction:** {t.trend_direction}")
        lines.append(f"- **Coherence Phi Delta:** {t.coherence_phi_delta:+.4f}")
        lines.append(f"- **Chaos Delta:** {t.chaos_score_delta:+.4f}")
        lines.append(f"- **Rigidity Delta:** {t.rigidity_score_delta:+.4f}")
        lines.append(f"- **Drift Delta:** {t.drift_delta:+.4f}")
        lines.append(f"- **Prediction Error Delta:** {t.prediction_error_delta:+.4f}")
        lines.append(f"- **Branching Ratio Delta:** {t.branching_ratio_delta:+.4f}")
        lines.append("")

        # Recommendations
        if self.recommendations:
            lines.append("## Recommendations")
            for rec in self.recommendations:
                sev_badge = f"**{rec.severity.upper()}**" if rec.severity != "info" else "INFO"
                lines.append(f"- {sev_badge} [{rec.category}] {rec.message} (confidence: {rec.confidence:.2f})")
            lines.append("")

        lines.append("---")
        lines.append("*Generated by SPEACE Observer Report Generator (T103)*")
        return "\n".join(lines)
