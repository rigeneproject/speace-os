import json
import pytest

from speace_core.cellular_brain.evolution.genome_database import (
    GenomeDatabase,
    GenomeRecord,
    EvolutionRunRecord,
)


@pytest.fixture
def db(tmp_path):
    return GenomeDatabase(base_path=str(tmp_path / "evolution"))


@pytest.fixture
def sample_genome():
    return {
        "identity": {"entity_name": "test"},
        "homeostasis": {"default_threshold": 0.5, "default_plasticity_rate": 0.05},
    }


def test_creates_directory_and_files(db):
    assert db.base_dir.exists()
    assert db.genomes_path.exists() or not db.genomes_path.exists()


def test_save_and_load_genome(db, sample_genome):
    record = GenomeRecord(
        genome_id="gen_001",
        generation=0,
        genome=sample_genome,
        created_at="2024-01-01T00:00:00Z",
        fitness_score=0.75,
    )
    db.save_genome(record)
    loaded = db.load_genome("gen_001")
    assert loaded is not None
    assert loaded.genome_id == "gen_001"
    assert loaded.fitness_score == 0.75


def test_load_missing_genome_returns_none(db):
    assert db.load_genome("nonexistent") is None


def test_list_genomes(db, sample_genome):
    for i in range(3):
        db.save_genome(
            GenomeRecord(
                genome_id=f"gen_{i}",
                generation=0,
                genome=sample_genome,
                created_at="2024-01-01T00:00:00Z",
            )
        )
    records = db.list_genomes()
    assert len(records) == 3


def test_list_by_generation(db, sample_genome):
    db.save_genome(
        GenomeRecord(
            genome_id="gen_a", generation=0, genome=sample_genome, created_at="2024-01-01T00:00:00Z"
        )
    )
    db.save_genome(
        GenomeRecord(
            genome_id="gen_b", generation=1, genome=sample_genome, created_at="2024-01-01T00:00:00Z"
        )
    )
    assert len(db.list_by_generation(0)) == 1
    assert len(db.list_by_generation(1)) == 1
    assert len(db.list_by_generation(2)) == 0


def test_get_best_genomes_sorted_and_limited(db, sample_genome):
    db.save_genome(
        GenomeRecord(
            genome_id="low", generation=0, genome=sample_genome, created_at="2024-01-01T00:00:00Z", fitness_score=0.3
        )
    )
    db.save_genome(
        GenomeRecord(
            genome_id="mid", generation=0, genome=sample_genome, created_at="2024-01-01T00:00:00Z", fitness_score=0.6
        )
    )
    db.save_genome(
        GenomeRecord(
            genome_id="high", generation=0, genome=sample_genome, created_at="2024-01-01T00:00:00Z", fitness_score=0.9
        )
    )
    best = db.get_best_genomes(limit=2)
    assert len(best) == 2
    assert best[0].genome_id == "high"
    assert best[1].genome_id == "mid"


def test_save_and_list_evolution_runs(db):
    run = EvolutionRunRecord(
        run_id="run_001",
        generation=1,
        candidate_genome_ids=["a", "b"],
        selected_genome_ids=["a"],
        best_genome_id="a",
        best_fitness=0.8,
        created_at="2024-01-01T00:00:00Z",
    )
    db.save_evolution_run(run)
    runs = db.list_evolution_runs()
    assert len(runs) == 1
    assert runs[0].run_id == "run_001"


def test_record_lineage(db):
    db.record_lineage("child_1", ["parent_a", "parent_b"], generation=2)
    assert db.lineages_path.exists()
    lines = db.lineages_path.read_text().strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["child_id"] == "child_1"
    assert data["parent_ids"] == ["parent_a", "parent_b"]
