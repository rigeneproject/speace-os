"""Append Phase-1 proposals to data/self_improvement/proposals.jsonl.

Governance: all proposals are written with status="draft" and auto_apply=False.
This script is idempotent: it only appends if a given proposal id is not already
present in the file.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

PROPOSALS_PATH = Path("data/self_improvement/proposals.jsonl")
ts = datetime.now(timezone.utc).isoformat()

PROPOSALS = [
    {
        "id": "prop-ch-001",
        "diagnosis_id": "diag-phase1-2026-06-04",
        "title": "Add self_model + morphological_memory writers (eliminates false coherence_phi=0 alert)",
        "proposal_type": "infrastructure",
        "target_modules": [
            "monitoring.organism_state_collector",
            "cognitive_homeostasis",
            "morphological_memory",
        ],
        "rationale": (
            "organism_state_collector.coherence_phi reads from "
            "data/self_model/snapshots.jsonl which is never written. Confirmed via Glob: "
            "data/self_model and data/morphological_memory do not exist. Fallback in "
            "collect_cognition hard-codes coherence_phi=0.0. This generates a false-positive "
            "coherence_phi_critical alert every 5s on the gateway. Fix: add periodic writers "
            "from the cognitive homeostatic subsystem and from the morphogenetic memory "
            "subsystem, on the same cadence as the runtime tick."
        ),
        "expected_benefits": {
            "alert_false_positive_removed": 1,
            "coherence_phi_accuracy": 1.0,
            "drift_signal_restored": 1,
        },
        "expected_risks": {"safety": 0.05, "regression": 0.05, "storage_growth": 0.1},
        "implementation_plan": [
            "Add MorphologySnapshotWriter at cadence=10s, writes (tick, neuron_count, "
            "active_neuron_count, synapse_count, active_synapse_count, activation_distribution, "
            "coherence_phi) to data/morphological_memory/snapshots.jsonl",
            "Add SelfModelSnapshotWriter at cadence=30s, writes (tick, developmental_stage, "
            "coherence_phi, identity_vector) to data/self_model/snapshots.jsonl",
            "Verify collect_cognition and collect_dynamics pick up the new files "
            "(no code change needed; just verify the read path)",
        ],
        "rollback_plan": [
            "Stop both writers; the collector falls back to defaults automatically"
        ],
        "safety_constraints": [
            "No core mutation",
            "Writers are read-only side effects from existing snapshots",
        ],
        "status": "draft",
        "auto_apply": False,
        "created_at": ts,
        "_stored_at": ts,
    },
    {
        "id": "prop-ch-002",
        "diagnosis_id": "diag-phase1-2026-06-04",
        "title": "Investigate stabilizer loop: criticality_drift/rigidity recurring with severity 2.5",
        "proposal_type": "module_refactor",
        "target_modules": [
            "regulation.stabilizer",
            "region_stability_controller",
            "plasticity_engine",
        ],
        "rationale": (
            "data/regulation/stabilizer_interventions.jsonl shows 181 entries. Last 20: mean "
            "severity 2.34 (cap 2.5), 100% match criticality_drift/rigidity patterns. Modulation "
            "dampen_feedback uses factor=0.8 on activations already at ~0.08, producing numerical "
            "floor (0.08*0.8=0.064, but pattern detection ignores sub-0.05 changes). Chaos_score "
            "derived from severity_sum/len=2.34 -> clamped to 1.0. This drives the chaos_critical "
            "alert. Hypothesis: detection threshold for drift is too sensitive OR dampen feedback "
            "is mathematically ineffective at the current activation regime."
        ),
        "expected_benefits": {"chaos_score_reduction": 0.5, "alert_count_reduction": 1},
        "expected_risks": {"safety": 0.2, "regression": 0.3},
        "implementation_plan": [
            "Log severity + activation regime (mean/min/max) per intervention for 50 cycles to "
            "validate hypothesis",
            "Audit detection thresholds: what is the 5th-95th percentile of |phi_t - phi_{t-1}| "
            "when the system is actually stable",
            "If dampen_feedback is ineffective at low activation: add a regime-aware modulation "
            "that switches to additive bias when activations < 0.1",
        ],
        "rollback_plan": ["Restore previous dampen_feedback factor"],
        "safety_constraints": [
            "No core mutation",
            "Phase 1: telemetry only. Phase 2: parameter change under review.",
        ],
        "status": "draft",
        "auto_apply": False,
        "created_at": ts,
        "_stored_at": ts,
    },
    {
        "id": "prop-ch-003",
        "diagnosis_id": "diag-phase1-2026-06-04",
        "title": "energy_conservation drive stuck at urgency 0.84 - writer missing for current_value",
        "proposal_type": "module_refactor",
        "target_modules": ["drives.homeostatic_drive", "energy_control_agent"],
        "rationale": (
            "drives/drive_history.jsonl: 240 entries. Last entry: energy_conservation "
            "setpoint=0.7 current_value=0.0 urgency=0.84. The drive is being computed but its "
            "current_value is never updated, so the gap (setpoint-current) stays at 0.7 forever, "
            "producing urgency 0.84 indefinitely. Hypothesis: the energy writer is not subscribed "
            "to the energy_control_agent output. Verify integration."
        ),
        "expected_benefits": {
            "drive_instability_reduction": 0.6,
            "alert_count_reduction": 1,
        },
        "expected_risks": {"safety": 0.15, "regression": 0.2},
        "implementation_plan": [
            "Trace energy_control_agent: which output does it produce? Where is it consumed?",
            "Add explicit test: energy writer is invoked at least every 10s when "
            "energy_control_agent reports new value",
            "If gap is structural (energy_control_agent not running), wire it into the "
            "runtime tick pipeline",
        ],
        "rollback_plan": ["Revert writer wiring"],
        "safety_constraints": [
            "No core mutation",
            "Telemetry first, then small wiring change",
        ],
        "status": "draft",
        "auto_apply": False,
        "created_at": ts,
        "_stored_at": ts,
    },
    {
        "id": "prop-cg-001",
        "diagnosis_id": "diag-phase1-capability-gap",
        "title": "Add Cognitive Genome layer (primitive/strategy/policy/invariant) to speace_core.dna",
        "proposal_type": "new_module",
        "target_modules": ["speace_core.dna"],
        "rationale": (
            "Current DNA is a static genome YAML (homeostasis params, morphology rules). It does "
            "not represent the cognitive architecture as 4 distinguishable layers: primitive "
            "(e.g. FSPI rotations/flips/fills), strategy (e.g. FSPI.compose_and_validate), policy "
            "(e.g. dampen_feedback factor), invariant (e.g. coherence_phi >= 0.1). Adding this "
            "layer makes the architecture heritable, inspectable, and mutatable by the DNA updater."
        ),
        "expected_benefits": {
            "agi_axis_self_improvement": 0.15,
            "failure_memory_foundation": 1,
            "ari_alignment": 0.1,
        },
        "expected_risks": {"safety": 0.3, "regression": 0.25, "complexity": 0.4},
        "implementation_plan": [
            "Define CognitiveGenomeSchema with 4 layers: primitives[], strategies[], "
            "policies{}, invariants[]",
            "Autoseed primitives from FSPI registry (rotation_90, flip_h, fill_holes, ...) and "
            "from regulation (dampen_feedback, homeostasis, stdp)",
            "Autoseed strategies from FSPI (compose_and_validate) and from regulation "
            "(compensate, freeze_policy)",
            "Autoseed policies from current DNA params",
            "Autoseed invariants from existing thresholds (coherence_phi_critical=0.1, etc.)",
            "Persist to data/cognitive_genome/cgenome.jsonl with versioning",
            "Wire into the proposal flow: every CognitivePatch must be a structured mutation of "
            "one layer",
        ],
        "rollback_plan": [
            "Remove the cognitive_genome module; DNA falls back to current behavior"
        ],
        "safety_constraints": [
            "Schema validates that invariants cannot be removed (only patched with stricter "
            "bounds)",
            "All mutations go through proposal flow",
            "T104 governance applies",
        ],
        "status": "draft",
        "auto_apply": False,
        "created_at": ts,
        "_stored_at": ts,
    },
    {
        "id": "prop-fm-001",
        "diagnosis_id": "diag-phase1-capability-gap",
        "title": "Add Failure Memory module: persistent Failure Pattern / Cause / Hypothesis / "
        "Strategy per task",
        "proposal_type": "new_module",
        "target_modules": ["speace_core.cellular_brain.memory"],
        "rationale": (
            "ARC failures (3/5 in this run) currently emit zero persistent memory. We have "
            "episodic_memory and self_improvement_memory, but no dedicated FailureMemory where "
            "each failure produces a structured record (Pattern, Cause, FailedHypothesis, "
            "CorrectiveStrategy). This is a precondition for any self-improving ARC performance: "
            "the system cannot generalize from failure without first remembering it."
        ),
        "expected_benefits": {
            "arc_score_baseline": 0.1,
            "cross_task_transfer": 1,
            "failure_learning_loop": 1,
        },
        "expected_risks": {"safety": 0.2, "regression": 0.15, "storage_growth": 0.2},
        "implementation_plan": [
            "Define FailureRecord schema: {failure_id, task_id, task_kind, pattern, cause, "
            "failed_hypotheses[], corrective_strategy, weight}",
            "Hook into ARCRunner._attempt_task: on failure, classify (no_candidate | "
            "wrong_primitive | wrong_composition | grid_mismatch)",
            "Hook into FSPIEngine.induce: record which primitives were hypothesised, which were "
            "rejected, why",
            "Persist to data/memory/failure_memory/failures.jsonl",
            "Add a query API for self_improvement_engine: 'given current task, what strategies "
            "failed before?'",
        ],
        "rollback_plan": ["Remove hook; no behavioral change"],
        "safety_constraints": [
            "Read-only on existing modules",
            "No automatic corrective strategy application without proposal approval",
        ],
        "status": "draft",
        "auto_apply": False,
        "created_at": ts,
        "_stored_at": ts,
    },
    {
        "id": "prop-ocr-001",
        "diagnosis_id": "diag-phase1-capability-gap",
        "title": "Promote Object-Centric Representation to a dedicated module (slot-attention-style)",
        "proposal_type": "new_module",
        "target_modules": ["speace_core.cellular_brain.cognition"],
        "rationale": (
            "Object extraction exists in spatial_symbolic_reasoning_layer.extract_objects and "
            "extract_hierarchical_objects, but there is no canonical ObjectCentricRepresentation "
            "module with a stable API (ObjectCentricScene, ObjectSlot, slot attention). For "
            "Few-Shot Program Induction to compose over object structures (not raw grids), we "
            "need a first-class object representation. This unblocks OCR-style reasoning and "
            "accelerates generalisation."
        ),
        "expected_benefits": {
            "object_centric_api": 1,
            "fspi_composability": 0.4,
            "ari_axis_generalization": 0.05,
        },
        "expected_risks": {"safety": 0.2, "regression": 0.3, "complexity": 0.5},
        "implementation_plan": [
            "Define ObjectCentricScene (slots[] each with id, mask, attributes) and "
            "ObjectCentricEncoder (wraps extract_objects + extract_hierarchical_objects)",
            "Add a slot-attention-style slot competition (winner-takes-most) for unambiguous "
            "object identity",
            "Integrate into FSPI: a new primitive copy_object_by_slot that operates on slots, "
            "not raw grids",
            "Integrate into SpatialSymbolicReasoningLayer.diff_scenes: diff at the slot level, "
            "not pixel level",
        ],
        "rollback_plan": [
            "Keep existing extract_* methods; the new module is purely additive"
        ],
        "safety_constraints": [
            "Additive only; no removal of existing APIs",
            "Determinism preserved (seeded slot competition)",
        ],
        "status": "draft",
        "auto_apply": False,
        "created_at": ts,
        "_stored_at": ts,
    },
]


def _existing_ids() -> set:
    if not PROPOSALS_PATH.exists():
        return set()
    out = set()
    with PROPOSALS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            pid = rec.get("id")
            if pid:
                out.add(pid)
    return out


def main() -> int:
    existing = _existing_ids()
    added: list = []
    skipped: list = []
    with PROPOSALS_PATH.open("a", encoding="utf-8") as f:
        for p in PROPOSALS:
            if p["id"] in existing:
                skipped.append(p["id"])
                continue
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
            added.append(p["id"])
    print(f"Added: {len(added)} | Skipped (existing): {len(skipped)}")
    for pid in added:
        print(f"  + {pid}")
    for pid in skipped:
        print(f"  = {pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
