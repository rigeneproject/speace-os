"""EcosystemAudit — T131 governance audits for ecosystem sources.

Audits required before assimilation:
- stability: source has been stable for sufficient observations
- semantic: source type maps to a known organismic metaphor
- trust: trust score is above threshold and no anomalies detected
- identity_drift: source identity has not drifted over time
- reversibility: source can be disassimilated without harm to the organism
"""

import time
from typing import Any, Dict, List, Optional

from speace_core.ecosystem.ecosystem_state import EcosystemSource
from speace_core.ecosystem.semantic_mapper import SemanticMapper
from speace_core.ecosystem.trust_governor import TrustGovernor


class EcosystemAudit:
    """Runs governance audits on ecosystem sources."""

    def __init__(
        self,
        semantic_mapper: Optional[SemanticMapper] = None,
        trust_governor: Optional[TrustGovernor] = None,
    ) -> None:
        self._semantic_mapper = semantic_mapper or SemanticMapper()
        self._trust_governor = trust_governor or TrustGovernor()

    # ------------------------------------------------------------------ #
    # Stability audit
    # ------------------------------------------------------------------ #

    def audit_stability(
        self,
        source: EcosystemSource,
        observations: List[Dict[str, Any]],
        min_observations: int = 10,
        max_error_rate: float = 0.2,
    ) -> Dict[str, Any]:
        """Check if source has been sufficiently stable."""
        total = len(observations)
        if total < min_observations:
            return {"passed": False, "reason": f"insufficient_observations ({total}/{min_observations})"}

        errors = sum(1 for o in observations if o.get("status") != "ok")
        error_rate = errors / total if total else 0.0
        passed = error_rate <= max_error_rate
        return {
            "passed": passed,
            "total_observations": total,
            "error_rate": round(error_rate, 4),
            "reason": "stable" if passed else f"high_error_rate ({error_rate:.2f})",
        }

    # ------------------------------------------------------------------ #
    # Semantic audit
    # ------------------------------------------------------------------ #

    def audit_semantic(self, source: EcosystemSource) -> Dict[str, Any]:
        """Check if source type maps to a known organismic metaphor."""
        metaphor = self._semantic_mapper.map(source.source_type)
        system = self._semantic_mapper.system_class(source.source_type)
        passed = metaphor is not None and system is not None
        return {
            "passed": passed,
            "metaphor": metaphor,
            "system_class": system,
            "reason": "mapped" if passed else "unknown_source_type",
        }

    # ------------------------------------------------------------------ #
    # Trust audit
    # ------------------------------------------------------------------ #

    def audit_trust(
        self,
        source: EcosystemSource,
        recent_observations: List[Dict[str, Any]],
        min_trust: float = 0.7,
        max_recent_anomalies: int = 0,
    ) -> Dict[str, Any]:
        """Check trust score and recent anomaly history."""
        trust_ok = source.trust_score >= min_trust
        anomalies = [
            o for o in recent_observations
            if o.get("status") == "blocked" or self._trust_governor.assess_anomaly([o])
        ]
        anomaly_ok = len(anomalies) <= max_recent_anomalies
        passed = trust_ok and anomaly_ok
        return {
            "passed": passed,
            "trust_score": source.trust_score,
            "trust_ok": trust_ok,
            "anomaly_count": len(anomalies),
            "anomaly_ok": anomaly_ok,
            "reason": "trusted" if passed else ("low_trust" if not trust_ok else "recent_anomalies"),
        }

    # ------------------------------------------------------------------ #
    # Identity drift audit
    # ------------------------------------------------------------------ #

    def audit_identity_drift(
        self,
        source: EcosystemSource,
        observations: List[Dict[str, Any]],
        max_payload_variance: float = 10.0,
    ) -> Dict[str, Any]:
        """Detect if source payload structure drifts over time (sign of identity change)."""
        if len(observations) < 3:
            return {"passed": False, "reason": "insufficient_history"}

        # Simple heuristic: count unique top-level keys in payloads over time
        key_sets: List[set] = []
        for obs in observations:
            payload = obs.get("raw_payload", {})
            if isinstance(payload, dict):
                key_sets.append(set(payload.keys()))

        if len(key_sets) < 2:
            return {"passed": False, "reason": "no_structured_payloads"}

        # Jaccard distance between consecutive key sets
        distances: List[float] = []
        for i in range(1, len(key_sets)):
            a, b = key_sets[i - 1], key_sets[i]
            union = a | b
            inter = a & b
            dist = 1.0 - (len(inter) / len(union)) if union else 0.0
            distances.append(dist)

        avg_dist = sum(distances) / len(distances) if distances else 0.0
        passed = avg_dist <= max_payload_variance
        return {
            "passed": passed,
            "avg_payload_distance": round(avg_dist, 4),
            "observations_checked": len(key_sets),
            "reason": "stable_identity" if passed else f"high_drift ({avg_dist:.2f})",
        }

    # ------------------------------------------------------------------ #
    # Reversibility audit
    # ------------------------------------------------------------------ #

    def audit_reversibility(
        self,
        source: EcosystemSource,
        sibling_sources: Optional[List[EcosystemSource]] = None,
        min_reversibility_score: float = 0.5,
    ) -> Dict[str, Any]:
        """Check if source can be disassimilated without harm.

        A source is reversible if:
        - it has been assimilated and revoked before without issues, OR
        - it is not the only source of its system class (redundancy exists), OR
        - its functional role is non-critical (input/storage vs processing/output).
        """
        # Past reversibility evidence
        past_reversible = False
        if source.assimilation_count > 0 and source.last_revoked_at > source.last_assimilated_at:
            # Was previously assimilated and later revoked
            past_reversible = True

        # Redundancy check
        redundancy = False
        if sibling_sources is not None:
            same_type_count = sum(1 for s in sibling_sources if s.source_type == source.source_type and s.source_id != source.source_id)
            redundancy = same_type_count > 0

        # Functional criticality
        role = self._semantic_mapper.functional_role(source.source_type)
        is_critical = role in ("output", "processing", "relay")

        # Compute score
        score = 0.0
        if past_reversible:
            score += 0.4
        if redundancy:
            score += 0.3
        if not is_critical:
            score += 0.3

        passed = score >= min_reversibility_score
        return {
            "passed": passed,
            "reversibility_score": round(score, 4),
            "past_reversible": past_reversible,
            "redundancy": redundancy,
            "is_critical": is_critical,
            "reason": "reversible" if passed else "irreversible_or_critical",
        }

    # ------------------------------------------------------------------ #
    # Full audit
    # ------------------------------------------------------------------ #

    def full_audit(
        self,
        source: EcosystemSource,
        observations: List[Dict[str, Any]],
        sibling_sources: Optional[List[EcosystemSource]] = None,
    ) -> Dict[str, Any]:
        """Run all five required audits and return combined result."""
        stability = self.audit_stability(source, observations)
        semantic = self.audit_semantic(source)
        trust = self.audit_trust(source, observations[-20:] if len(observations) > 20 else observations)
        identity = self.audit_identity_drift(source, observations)
        reversibility = self.audit_reversibility(source, sibling_sources=sibling_sources)

        all_passed = (
            stability["passed"]
            and semantic["passed"]
            and trust["passed"]
            and identity["passed"]
            and reversibility["passed"]
        )

        return {
            "timestamp": time.time(),
            "source_id": source.source_id,
            "overall_passed": all_passed,
            "stability": stability,
            "semantic": semantic,
            "trust": trust,
            "identity_drift": identity,
            "reversibility": reversibility,
        }
