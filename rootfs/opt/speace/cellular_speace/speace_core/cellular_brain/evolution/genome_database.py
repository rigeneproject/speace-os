import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GenomeRecord(BaseModel):
    genome_id: str
    parent_ids: List[str] = Field(default_factory=list)
    generation: int = 0
    genome: Dict[str, Any]
    created_at: str
    mutation_operator: Optional[str] = None
    crossover_operator: Optional[str] = None
    fitness_score: Optional[float] = None
    benchmark_case: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    lineage_notes: Optional[str] = None


class EvolutionRunRecord(BaseModel):
    run_id: str
    generation: int
    candidate_genome_ids: List[str] = Field(default_factory=list)
    selected_genome_ids: List[str] = Field(default_factory=list)
    best_genome_id: Optional[str] = None
    best_fitness: Optional[float] = None
    created_at: str
    notes: Optional[str] = None


class GenomeDatabase:
    """Persistent JSONL store for genomes and evolution runs."""

    def __init__(self, base_path: str = "data/evolution"):
        self.base_dir = Path(base_path)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.genomes_path = self.base_dir / "genomes.jsonl"
        self.runs_path = self.base_dir / "evolution_runs.jsonl"
        self.lineages_path = self.base_dir / "lineages.jsonl"

    # ------------------------------------------------------------------ #
    # Genome records
    # ------------------------------------------------------------------ #

    def save_genome(self, record: GenomeRecord) -> str:
        """Append a genome record to the JSONL store."""
        with self.genomes_path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
        return record.genome_id

    def load_genome(self, genome_id: str) -> Optional[GenomeRecord]:
        """Find the first genome record matching genome_id."""
        if not self.genomes_path.exists():
            return None
        with self.genomes_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if data.get("genome_id") == genome_id:
                    return GenomeRecord(**data)
        return None

    def list_genomes(self) -> List[GenomeRecord]:
        """Return all genome records."""
        records: List[GenomeRecord] = []
        if not self.genomes_path.exists():
            return records
        with self.genomes_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(GenomeRecord(**json.loads(line)))
        return records

    def list_by_generation(self, generation: int) -> List[GenomeRecord]:
        """Filter genome records by generation number."""
        return [r for r in self.list_genomes() if r.generation == generation]

    def get_best_genomes(self, limit: int = 5) -> List[GenomeRecord]:
        """Return top genomes sorted by fitness_score descending."""
        scored = [r for r in self.list_genomes() if r.fitness_score is not None]
        scored.sort(key=lambda r: r.fitness_score, reverse=True)  # type: ignore[arg-type]
        return scored[:limit]

    # ------------------------------------------------------------------ #
    # Evolution run records
    # ------------------------------------------------------------------ #

    def save_evolution_run(self, record: EvolutionRunRecord) -> str:
        """Append an evolution run record to the JSONL store."""
        with self.runs_path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json() + "\n")
        return record.run_id

    def list_evolution_runs(self) -> List[EvolutionRunRecord]:
        """Return all evolution run records."""
        records: List[EvolutionRunRecord] = []
        if not self.runs_path.exists():
            return records
        with self.runs_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                records.append(EvolutionRunRecord(**json.loads(line)))
        return records

    # ------------------------------------------------------------------ #
    # Lineage helpers
    # ------------------------------------------------------------------ #

    def record_lineage(self, child_id: str, parent_ids: List[str], generation: int) -> None:
        """Write a simple lineage entry."""
        entry = {
            "child_id": child_id,
            "parent_ids": parent_ids,
            "generation": generation,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with self.lineages_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
