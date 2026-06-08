"""T146 — First Controlled Dialogue Evolution Experiment.

Pipeline:
1. Send 10 Italian messages → collect coherence reports.
2. Let T144 generate proposals.
3. Approve one harmless proposal (highest fitness).
4. Send 10 more messages → collect post-approval coherence.
5. Compare average coherence.
6. Rollback if coherence worsens > 10%.
7. Emit JSON report.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.language.dialogue_manager import DialogueManager


def _average(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pick_best_pending(proposals: List[Dict[str, Any]]) -> Optional[str]:
    pending = [p for p in proposals if p.get("status") == "pending_approval"]
    if not pending:
        return None
    # Prefer highest fitness
    pending.sort(key=lambda p: p.get("fitness", {}).get("fitness", 0.0), reverse=True)
    return pending[0].get("proposal_id")


def run_experiment(
    dm: Optional[DialogueManager] = None,
    pre_messages: Optional[List[str]] = None,
    post_messages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    dm = dm or DialogueManager()
    cla = dm._cla_feedback

    pre_messages = pre_messages or [
        "Ciao SPEACE, come stai?",
        "Parlami della tua salute.",
        "Chi sei?",
        "Cosa pensi della regolazione?",
        "Hai allerte attive?",
        "Dimmi del tuo stato cognitivo.",
        "Cosa significa metacognizione?",
        "Puoi parlare?",
        "Come funziona il nodo distribuito?",
        "Grazie per la risposta.",
    ]

    post_messages = post_messages or [
        "Ciao di nuovo, come va?",
        "Stai bene oggi?",
        "Ricordi chi sono?",
        "Parlami delle proposte.",
        "C'è qualche pericolo?",
        "Cosa stai pensando?",
        "Spiegami la cognizione.",
        "Il tuo organo vocale è attivo?",
        "I nodi sono sincronizzati?",
        "Arrivederci.",
    ]

    pre_scores: List[float] = []
    pre_proposals: List[Dict[str, Any]] = []

    for msg in pre_messages:
        result = dm.receive(msg)
        report = result.get("coherence_report", {})
        score = report.get("overall_coherence_score", 0.0)
        pre_scores.append(score)
        cla_result = result.get("cla_feedback", {})
        pre_proposals.extend(cla_result.get("proposals", []))

    pre_avg = _average(pre_scores)

    # Pick and approve one harmless proposal
    approved_id: Optional[str] = None
    approval_result: Optional[Dict[str, Any]] = None
    best_id = _pick_best_pending(pre_proposals)
    if best_id:
        approval_result = cla.approve_proposal(best_id, reviewer="T146_experiment", current_health=pre_avg)
        if approval_result.get("status") == "applied":
            approved_id = best_id

    post_scores: List[float] = []
    for msg in post_messages:
        result = dm.receive(msg)
        report = result.get("coherence_report", {})
        post_scores.append(report.get("overall_coherence_score", 0.0))

    post_avg = _average(post_scores)
    delta = post_avg - pre_avg
    worsened = delta < -0.1

    rollback_result: Optional[Dict[str, Any]] = None
    if worsened and approved_id:
        rollback_result = cla.rollback_proposal(approved_id, reviewer="T146_experiment")

    report: Dict[str, Any] = {
        "experiment": "T146_dialogue_evolution",
        "pre_turns": len(pre_scores),
        "pre_average_coherence": round(pre_avg, 4),
        "pre_proposals_generated": len(pre_proposals),
        "approved_proposal_id": approved_id,
        "approval_result": approval_result,
        "post_turns": len(post_scores),
        "post_average_coherence": round(post_avg, 4),
        "delta": round(delta, 4),
        "worsened": worsened,
        "rollback_result": rollback_result,
        "conclusion": (
            "rollback_executed" if rollback_result
            else "kept" if approved_id
            else "no_proposal_approved"
        ),
    }

    # Persist report
    out_dir = Path("data/dialogue")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "t146_experiment_report.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")

    return report


if __name__ == "__main__":
    report = run_experiment()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["worsened"]:
        sys.exit(1)
