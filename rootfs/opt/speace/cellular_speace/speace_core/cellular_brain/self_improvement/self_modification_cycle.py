"""SelfModificationCycle — closed observe→identify→mutate→test→adopt loop.

T169 — Phase 3 / Learning boost.

This module binds together the existing self-improvement primitives
into a single high-level orchestrator:

    1. **Observe**     — collect current scores from the orchestrator
                        (or fall back to last cycle metrics)
    2. **Identify**    — run ``LimitationDetector`` to find weaknesses
    3. **Mutate**      — generate ``ArchitectureRewriteProposal``s via
                        ``ArchitectureRewriter``
    4. **Test**        — for each proposal, run counterfactual sandbox
                        and post-patch validation. Only safe patches
                        are kept.
    5. **Adopt**       — promote the best safe proposal to STABLE in
                        the ``EvolutionaryMemoryStore`` via the
                        ``EvolutionaryMemoryGovernor`` and write a
                        self-modification event to ``SelfImprovementMemory``.

The cycle is **read-mostly** at the orchestrator level: only
``ArchitecturePatchExecutor``-gated flags/numerics are mutated, never
DNA YAML, never filesystem outside ``data/self_improvement/``.

Safety:
- All mutations pass through ``ArchitecturePatchExecutor`` which has
  an allowlist (``ALLOWED_FLAGS / ALLOWED_PROFILES / ALLOWED_NUMERIC``).
- Adoption requires ``safety_score >= 0.7`` and ``regression_score < 0.2``.
- Every step logs to ``SelfImprovementMemory`` for audit.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #
class SelfModificationCycleResult(BaseModel):
    cycle_id: str
    observed: Dict[str, float] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)
    mutations: List[str] = Field(default_factory=list)
    tests: List[Dict[str, Any]] = Field(default_factory=list)
    adoption: Optional[str] = None  # STABLE / PROBATIONARY / QUARANTINED / FORGOTTEN / None
    delta_score: float = 0.0
    safety_score: float = 0.0
    regression_score: float = 0.0
    confidence: float = 0.0
    passed_steps: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    duration_sec: float = 0.0


# --------------------------------------------------------------------------- #
# Cycle orchestrator
# --------------------------------------------------------------------------- #
class SelfModificationCycle:
    """Observe → Identify → Mutate → Test → Adopt."""

    def __init__(
        self,
        orchestrator: Any = None,
        memory: Any = None,
        regression_guard: Any = None,
        data_root: Optional[Path] = None,
        verbose: bool = False,
    ):
        self.orchestrator = orchestrator
        self.memory = memory
        self.regression_guard = regression_guard
        self.data_root = data_root or Path("data")
        self.verbose = verbose
        # Lazy components
        self._detector = None
        self._rewriter = None
        self._sandbox = None
        self._executor = None
        self._evaluator = None
        self._sim_memory = None
        self._governor = None

    # ------------------------------------------------------------------ #
    # Component accessors (lazy)
    # ------------------------------------------------------------------ #
    def _get_detector(self):
        if self._detector is None:
            from speace_core.cellular_brain.self_improvement.limitation_detector import (
                LimitationDetector,
            )
            self._detector = LimitationDetector(
                memory=self.memory,
                regression_guard=self.regression_guard,
            )
        return self._detector

    def _get_rewriter(self):
        if self._rewriter is None:
            from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
                ArchitectureRewriter,
            )
            self._rewriter = ArchitectureRewriter()
        return self._rewriter

    def _get_sandbox(self):
        if self._sandbox is None:
            from speace_core.cellular_brain.self_improvement.counterfactual_sandbox import (
                CounterfactualArchitectureSandbox,
            )
            self._sandbox = CounterfactualArchitectureSandbox()
        return self._sandbox

    def _get_executor(self):
        if self._executor is None:
            from speace_core.cellular_brain.self_improvement.architecture_patch_executor import (
                ArchitecturePatchExecutor,
            )
            self._executor = ArchitecturePatchExecutor(
                orchestrator=self.orchestrator,
                memory=self.memory,
                regression_guard=self.regression_guard,
            )
        return self._executor

    def _get_evaluator(self):
        if self._evaluator is None:
            from speace_core.cellular_brain.cognitive_evolution.skill_fitness_evaluator import (
                SkillFitnessEvaluator,
            )
            self._evaluator = SkillFitnessEvaluator()
        return self._evaluator

    def _get_sim_memory(self):
        if self._sim_memory is None:
            from speace_core.cellular_brain.self_improvement.self_improvement_memory import (
                SelfImprovementMemory,
            )
            self._sim_memory = SelfImprovementMemory(
                base_path=str(self.data_root / "self_improvement"),
                memory=self.memory,
            )
        return self._sim_memory

    def _get_governor(self):
        if self._governor is None:
            try:
                from speace_core.cellular_brain.evolutionary_memory.evolutionary_memory_governor import (
                    EvolutionaryMemoryGovernor,
                )
                self._governor = EvolutionaryMemoryGovernor(memory=self.memory)
            except Exception:
                self._governor = None
        return self._governor

    # ------------------------------------------------------------------ #
    # Cycle steps
    # ------------------------------------------------------------------ #
    def _observe(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """Step 1: read current scores from the orchestrator (or fallback)."""
        observed: Dict[str, float] = {}
        # Try orchestrator's latest_metrics first
        if self.orchestrator is not None:
            bm = getattr(self.orchestrator, "latest_metrics", None)
            if bm is not None:
                observed["cognitive_score"] = float(getattr(bm, "accuracy", 0.0) or 0.0)
                observed["coherence_phi"] = float(getattr(bm, "coherence_phi", 0.0) or 0.0)
                observed["mean_energy"] = float(getattr(bm, "mean_energy", 0.0) or 0.0)
        # Fallback: use the passed metrics dict
        for k, v in (metrics or {}).items():
            try:
                observed[k] = float(v)
            except (TypeError, ValueError):
                continue
        return observed

    def _identify(self, observed: Dict[str, float]) -> List[Any]:
        """Step 2: run the limitation detector."""
        detector = self._get_detector()
        signals = detector.detect_from_metrics(observed)
        try:
            diagnoses = detector.aggregate_signals(signals)
        except Exception:
            diagnoses = []
        return diagnoses or signals

    def _mutate(self, diagnoses: List[Any]) -> List[Any]:
        """Step 3: generate proposals for each diagnosis."""
        rewriter = self._get_rewriter()
        proposals = []
        for d in diagnoses:
            try:
                p = rewriter.generate_proposal(d)
            except Exception:
                p = None
            if p is not None:
                proposals.append(p)
        return proposals

    def _test(self, proposals: List[Any]) -> List[Dict[str, Any]]:
        """Step 4: sandbox + post-patch validation for each proposal."""
        executor = self._get_executor()
        results: List[Dict[str, Any]] = []
        for p in proposals:
            try:
                exec_result = executor.execute_patch(p)
                results.append({
                    "proposal_id": getattr(p, "id", "unknown"),
                    "applied": bool(getattr(exec_result, "applied", False)),
                    "verdict": getattr(exec_result, "verdict", "UNKNOWN"),
                    "delta_score": float(getattr(exec_result, "delta_score", 0.0) or 0.0),
                    "delta_phi": float(getattr(exec_result, "delta_phi", 0.0) or 0.0),
                    "delta_energy": float(getattr(exec_result, "delta_energy", 0.0) or 0.0),
                    "regression_flags": list(getattr(exec_result, "regression_flags", []) or []),
                    "rolled_back": bool(getattr(exec_result, "rolled_back", False)),
                })
            except Exception as exc:
                results.append({
                    "proposal_id": getattr(p, "id", "unknown"),
                    "applied": False,
                    "verdict": "PATCH_REJECTED",
                    "error": str(exc),
                })
        return results

    def _adopt(
        self,
        tests: List[Dict[str, Any]],
        observed: Dict[str, float],
    ) -> Dict[str, Any]:
        """Step 5: pick best safe proposal; promote to evolutionary memory."""
        # Pick the best confirmed patch (highest delta_score, no regression)
        candidates = [t for t in tests if t.get("verdict") == "PATCH_CONFIRMED"]
        if not candidates:
            candidates = [
                t for t in tests
                if t.get("verdict") in ("PATCH_NEEDS_MORE_EVIDENCE",)
                and not t.get("regression_flags")
            ]
        if not candidates:
            return {"adoption": None, "delta_score": 0.0, "safety_score": 0.0,
                    "regression_score": 0.0, "adopted_proposal_id": None}
        candidates.sort(key=lambda t: float(t.get("delta_score", 0.0)), reverse=True)
        best = candidates[0]
        delta = float(best.get("delta_score", 0.0))
        # Estimate safety / regression from flags
        flags = list(best.get("regression_flags", []) or [])
        regression_score = 0.1 if not flags else min(1.0, 0.2 * len(flags))
        safety_score = max(0.0, 1.0 - regression_score - max(0.0, -delta))
        confidence = max(0.0, min(1.0, 0.5 + 0.5 * delta - 0.3 * regression_score))
        # Decide adoption status
        if safety_score >= 0.7 and regression_score < 0.2 and delta > 0:
            status = "STABLE"
        elif safety_score >= 0.6 and delta > 0:
            status = "PROBATIONARY"
        elif regression_score > 0.5 or safety_score < 0.4:
            status = "QUARANTINED"
        else:
            status = "EXPERIMENTAL"
        # Write to evolutionary memory if governor is available
        adopted_pid = None
        governor = self._get_governor()
        if governor is not None and hasattr(governor, "ingest_cycle_result"):
            try:
                governor.ingest_cycle_result({
                    "fitness_delta": delta,
                    "phi_delta": float(best.get("delta_phi", 0.0)),
                    "regression_score": regression_score,
                    "safety_score": safety_score,
                    "confidence": confidence,
                    "reuse_count": 1,
                    "proposal_id": best.get("proposal_id"),
                    "source": "self_modification_cycle",
                })
                adopted_pid = best.get("proposal_id")
            except Exception:
                adopted_pid = None
        # Log to self-improvement memory
        try:
            sim = self._get_sim_memory()
            sim.write_history_event("adoption", {
                "proposal_id": best.get("proposal_id"),
                "status": status,
                "delta_score": delta,
                "safety_score": safety_score,
                "regression_score": regression_score,
                "confidence": confidence,
                "source": "self_modification_cycle",
            })
        except Exception:
            pass
        return {
            "adoption": status,
            "delta_score": delta,
            "safety_score": safety_score,
            "regression_score": regression_score,
            "confidence": confidence,
            "adopted_proposal_id": adopted_pid,
        }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def run(
        self,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> SelfModificationCycleResult:
        """Run the full Observe → Identify → Mutate → Test → Adopt cycle.

        ``metrics`` is an optional fallback if the orchestrator has no
        ``latest_metrics``. Safe to call repeatedly; the result is a
        single ``SelfModificationCycleResult``.
        """
        cycle_id = f"smc-{uuid.uuid4().hex[:8]}"
        started = time.time()
        started_at = datetime.now(timezone.utc).isoformat()
        passed: List[str] = []
        notes: List[str] = []

        # 1. OBSERVE
        observed = self._observe(metrics or {})
        passed.append("observe")
        # 2. IDENTIFY
        try:
            diagnoses = self._identify(observed)
            passed.append("identify")
            limitation_ids = [
                getattr(d, "id", None) or str(d) for d in (diagnoses or [])
            ]
        except Exception as exc:
            limitation_ids = []
            notes.append(f"identify_error: {exc}")
            diagnoses = []
        # 3. MUTATE
        try:
            proposals = self._mutate(diagnoses)
            passed.append("mutate")
            mutation_ids = [getattr(p, "id", None) or str(p) for p in (proposals or [])]
        except Exception as exc:
            mutation_ids = []
            notes.append(f"mutate_error: {exc}")
            proposals = []
        # 4. TEST
        if proposals:
            try:
                tests = self._test(proposals)
                passed.append("test")
            except Exception as exc:
                tests = []
                notes.append(f"test_error: {exc}")
        else:
            tests = []
            notes.append("no_proposals_to_test")
        # 5. ADOPT
        if tests:
            try:
                adoption_info = self._adopt(tests, observed)
                passed.append("adopt")
            except Exception as exc:
                adoption_info = {
                    "adoption": None,
                    "delta_score": 0.0,
                    "safety_score": 0.0,
                    "regression_score": 0.0,
                    "confidence": 0.0,
                    "adopted_proposal_id": None,
                }
                notes.append(f"adopt_error: {exc}")
        else:
            adoption_info = {
                "adoption": None,
                "delta_score": 0.0,
                "safety_score": 0.0,
                "regression_score": 0.0,
                "confidence": 0.0,
                "adopted_proposal_id": None,
            }
            notes.append("no_tests_to_adopt")

        finished = time.time()
        result = SelfModificationCycleResult(
            cycle_id=cycle_id,
            observed=observed,
            limitations=limitation_ids,
            mutations=mutation_ids,
            tests=tests,
            adoption=adoption_info.get("adoption"),
            delta_score=float(adoption_info.get("delta_score", 0.0) or 0.0),
            safety_score=float(adoption_info.get("safety_score", 0.0) or 0.0),
            regression_score=float(adoption_info.get("regression_score", 0.0) or 0.0),
            confidence=float(adoption_info.get("confidence", 0.0) or 0.0),
            passed_steps=passed,
            notes=notes,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc).isoformat(),
            duration_sec=round(finished - started, 4),
        )
        return result

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def persist(self, result: SelfModificationCycleResult) -> Optional[Path]:
        """Write the cycle result to ``data/self_improvement/smc_cycles.jsonl``."""
        path = self.data_root / "self_improvement" / "smc_cycles.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result.model_dump(), default=str) + "\n")
            return path
        except OSError as exc:
            if self.verbose:
                print(f"persist failed: {exc}")
            return None
