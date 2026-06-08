"""Avvio rapido del SPEACE AGI Team."""

import sys
import io

# Forza UTF-8 su stdout per compatibilità Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

from speace_agi_team.config import AgentConfig
from speace_agi_team.supervisor_agents import (
    ChiefArchitect, BrainSupervisor, DNASupervisor,
    OrganismSupervisor, MemorySupervisor, SelfImprovementSupervisor,
)
from speace_agi_team.technical_agents import (
    NeuronTechnician, SynapseTechnician, RegionTechnician,
    GenomeTechnician, RuntimeTechnician, DefenseTechnician,
    MemoryTechnician, EvolutionTechnician, NetworkTechnician,
    EmbodimentTechnician,
)
from speace_agi_team.engineering_plan import EngineeringPlan


def main():
    print("=" * 70)
    print("  SPEACE AGI TEAM — Inizializzazione")
    print("=" * 70)
    print()
    cfg = AgentConfig()
    print(f"LLM Model : {cfg.model}")
    print(f"Endpoint  : {cfg.endpoint}")
    print(f"MaxTokens : {cfg.max_tokens}")
    print(f"Temperat. : {cfg.temperature}")
    print()

    supervisors = [
        ChiefArchitect(cfg), BrainSupervisor(cfg), DNASupervisor(cfg),
        OrganismSupervisor(cfg), MemorySupervisor(cfg),
        SelfImprovementSupervisor(cfg),
    ]
    technicians = [
        NeuronTechnician(cfg), SynapseTechnician(cfg), RegionTechnician(cfg),
        GenomeTechnician(cfg), RuntimeTechnician(cfg), DefenseTechnician(cfg),
        MemoryTechnician(cfg), EvolutionTechnician(cfg), NetworkTechnician(cfg),
        EmbodimentTechnician(cfg),
    ]

    print(f"Supervisor: {len(supervisors)}")
    for s in supervisors:
        print(f"  - {s.name} ({s.agent_id})")
    print()
    print(f"Tecnici   : {len(technicians)}")
    for t in technicians:
        print(f"  - {t.name} ({t.agent_id})")
    print()

    plan = EngineeringPlan()
    report = plan.get_milestone_progress_report()
    print("Piano Ingegneristico:")
    print(f"  Progresso complessivo: {report['overall_progress']:.1%}")
    print(f"  Milestone totali     : {len(report['milestones'])}")
    print()
    for ms in report["milestones"]:
        bar_len = 20
        filled = int(bar_len * ms["progress"])
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"  [{ms['id']}] {bar} {ms['progress']:5.0%}  {ms['title']}")
    print()
    print("Pronto. Avvia il web server con:")
    print("  python -m speace_agi_team.main --port 8686")


if __name__ == "__main__":
    main()
