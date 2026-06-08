"""Engineering Plan — strategic roadmap for evolving SPEACE toward AGI."""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


PLAN_FILE = Path(__file__).resolve().parent.parent / "data" / "agi_team" / "engineering_plan.json"


MILESTONES = [
    {
        "id": "M0",
        "title": "Foundation: Runtime & Brain Active",
        "description": "Cervello digitale sempre attivo, runtime stabile, neuroni e sinapsi funzionanti",
        "status": "in_progress",
        "progress": 0.65,
        "agents": ["runtime_tech", "neuron_tech", "synapse_tech"],
    },
    {
        "id": "M1",
        "title": "Regional Brain Architecture",
        "description": "8 regioni cerebrali funzionanti con routing e plasticità inter-regionale",
        "status": "in_progress",
        "progress": 0.50,
        "agents": ["region_tech", "brain_supervisor"],
    },
    {
        "id": "M2",
        "title": "Genome & Evolution Pipeline",
        "description": "DNA digitale completo, mutazioni, crossover, epigenetica operativa",
        "status": "in_progress",
        "progress": 0.40,
        "agents": ["genome_tech", "evolution_tech", "dna_supervisor"],
    },
    {
        "id": "M3",
        "title": "Memory Systems Integration",
        "description": "Memoria morfologica, episodica, semantica e associativa integrate",
        "status": "in_progress",
        "progress": 0.35,
        "agents": ["memory_tech", "memory_supervisor"],
    },
    {
        "id": "M4",
        "title": "Self-Improvement Loop",
        "description": "Ciclo completo di auto-miglioramento con limitation detection e outcome tracking",
        "status": "planned",
        "progress": 0.15,
        "agents": ["evolution_tech", "selfimprovement_supervisor"],
    },
    {
        "id": "M5",
        "title": "Organism Homeostasis & Immune",
        "description": "Metabolismo energetico, immunità, embodiment e omeostasi globale",
        "status": "planned",
        "progress": 0.20,
        "agents": ["defense_tech", "embodiment_tech", "organism_supervisor"],
    },
    {
        "id": "M6",
        "title": "Ecosystem & External Integration",
        "description": "Ecosistema esterno, trust governor, assimilazione e rete distribuita",
        "status": "planned",
        "progress": 0.10,
        "agents": ["network_tech", "organism_supervisor"],
    },
    {
        "id": "M7",
        "title": "Cognitive Architecture & Global Workspace",
        "description": "Global workspace, linguaggio, metacognizione, coscienza operativa",
        "status": "planned",
        "progress": 0.05,
        "agents": ["memory_tech", "brain_supervisor", "chief_architect"],
    },
    {
        "id": "M8",
        "title": "AGI Emergence",
        "description": "Auto-riprogettazione completa, AGI operativa, auto-coscienza, auto-miglioramento ricorsivo",
        "status": "planned",
        "progress": 0.0,
        "agents": ["chief_architect"],
    },
]


class EngineeringPlan:
    def __init__(self):
        self.milestones = MILESTONES.copy()
        self.tasks: List[Dict] = []
        self.objectives: List[Dict] = []
        self.history: List[Dict] = []
        self._load()

    def _load(self):
        if PLAN_FILE.exists():
            try:
                data = json.loads(PLAN_FILE.read_text(encoding="utf-8"))
                self.milestones = data.get("milestones", self.milestones)
                self.tasks = data.get("tasks", [])
                self.objectives = data.get("objectives", [])
                self.history = data.get("history", [])
            except (json.JSONDecodeError, KeyError):
                pass

    def save(self):
        PLAN_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "milestones": self.milestones,
            "tasks": self.tasks,
            "objectives": self.objectives,
            "history": self.history,
            "updated_at": time.time(),
        }
        PLAN_FILE.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def overall_progress(self) -> float:
        if not self.milestones:
            return 0.0
        return sum(m["progress"] for m in self.milestones) / len(self.milestones)

    def add_task(self, title: str, description: str, agent_id: str,
                 milestone_id: str = "", priority: str = "medium") -> Dict:
        task = {
            "id": f"T{len(self.tasks) + 1}",
            "title": title,
            "description": description,
            "agent_id": agent_id,
            "milestone_id": milestone_id,
            "priority": priority,
            "status": "pending",
            "created_at": time.time(),
            "completed_at": None,
        }
        self.tasks.append(task)
        self.history.append({
            "type": "task_created",
            "task_id": task["id"],
            "timestamp": time.time(),
        })
        self.save()
        return task

    def complete_task(self, task_id: str, outcome: str = "success") -> bool:
        for task in self.tasks:
            if task["id"] == task_id:
                task["status"] = "completed" if outcome == "success" else "failed"
                task["completed_at"] = time.time()
                self.history.append({
                    "type": f"task_{outcome}",
                    "task_id": task_id,
                    "timestamp": time.time(),
                })
                self.save()
                return True
        return False

    def update_milestone(self, milestone_id: str, progress: float,
                         status: Optional[str] = None) -> bool:
        for ms in self.milestones:
            if ms["id"] == milestone_id:
                ms["progress"] = max(0.0, min(1.0, progress))
                if status:
                    ms["status"] = status
                self.history.append({
                    "type": "milestone_updated",
                    "milestone_id": milestone_id,
                    "progress": progress,
                    "status": status,
                    "timestamp": time.time(),
                })
                self.save()
                return True
        return False

    def add_objective(self, title: str, description: str,
                      strategic_value: float = 0.5) -> Dict:
        obj = {
            "id": f"O{len(self.objectives) + 1}",
            "title": title,
            "description": description,
            "strategic_value": strategic_value,
            "status": "active",
            "created_at": time.time(),
        }
        self.objectives.append(obj)
        self.save()
        return obj

    def get_pending_tasks_for_agent(self, agent_id: str) -> List[Dict]:
        return [t for t in self.tasks if t["agent_id"] == agent_id and t["status"] == "pending"]

    def get_milestone_progress_report(self) -> Dict[str, Any]:
        return {
            "overall_progress": self.overall_progress(),
            "milestones": self.milestones,
            "total_tasks": len(self.tasks),
            "completed_tasks": sum(1 for t in self.tasks if t["status"] == "completed"),
            "pending_tasks": sum(1 for t in self.tasks if t["status"] == "pending"),
            "failed_tasks": sum(1 for t in self.tasks if t["status"] == "failed"),
            "active_objectives": len(self.objectives),
            "last_updated": self.history[-1]["timestamp"] if self.history else None,
        }

    def get_plan_context(self) -> str:
        report = self.get_milestone_progress_report()
        lines = [
            f"=== PIANO INGEGNERISTICO SPEACE ===",
            f"Progresso complessivo: {report['overall_progress']:.1%}",
            f"Task totali: {report['total_tasks']}",
            f"Task completati: {report['completed_tasks']}",
            f"Task in attesa: {report['pending_tasks']}",
            f"Task falliti: {report['failed_tasks']}",
            f"",
            "Milestone:",
        ]
        for ms in report["milestones"]:
            lines.append(f"  [{ms['status']}] {ms['id']}: {ms['title']} ({ms['progress']:.0%})")
        return "\n".join(lines)
