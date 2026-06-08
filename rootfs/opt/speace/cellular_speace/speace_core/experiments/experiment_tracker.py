import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from threading import Lock
import os


class ExperimentTracker:
    """Traccia tutti gli eventi evolutivi per audit e analisi.

    Formato: JSONL + SQLite per query efficienti.
    """

    def __init__(self, data_dir: str = "data/experiments"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # File JSONL per eventi completi
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.jsonl_path = self.data_dir / f"experiment_{timestamp}.jsonl"

        # Database SQLite per query
        self.db_path = self.data_dir / "experiments.db"
        self._lock = Lock()

        self._init_sqlite()

    def _init_sqlite(self) -> None:
        """Inizializza il database SQLite."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ilf_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    cycle INTEGER NOT NULL,
                    value REAL NOT NULL,
                    coherence REAL NOT NULL,
                    adaptation REAL NOT NULL,
                    continuity REAL NOT NULL,
                    goal_alignment REAL NOT NULL,
                    delta_ilf REAL DEFAULT 0.0,
                    trend TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dna_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    generation INTEGER NOT NULL,
                    genome_hash TEXT NOT NULL,
                    parent_hashes TEXT,
                    mutation_type TEXT,
                    mutation_details TEXT,
                    ilf_before REAL,
                    ilf_after REAL,
                    accepted BOOLEAN
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mutations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    generation INTEGER NOT NULL,
                    gene_name TEXT NOT NULL,
                    mutation_action TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    ilf_impact REAL,
                    accepted BOOLEAN
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cv_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    branch_id TEXT NOT NULL,
                    branch_name TEXT NOT NULL,
                    parent_branch TEXT,
                    trigger_reason TEXT,
                    ilf_before REAL,
                    ilf_after REAL,
                    ilf_delta REAL,
                    status TEXT,
                    explored_depth INTEGER DEFAULT 0
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fitness_evolution (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    cycle INTEGER NOT NULL,
                    population_size INTEGER,
                    fitness_mean REAL,
                    fitness_std REAL,
                    fitness_best REAL,
                    diversity_score REAL,
                    stagnation_cycles INTEGER DEFAULT 0,
                    active_engine TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS branch_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    branch_id TEXT NOT NULL,
                    parent_branch_id TEXT,
                    branch_name TEXT NOT NULL,
                    depth INTEGER,
                    ilf_score REAL,
                    status TEXT,
                    merged_into TEXT,
                    pruned_at REAL
                )
            """)

            # Indici per query efficienti
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_ilf_cycle ON ilf_history(cycle)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_dna_gen ON dna_versions(generation)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_cv_branch ON cv_events(branch_id)"
            )

            conn.commit()

    # ------------------------------------------------------------------ #
    # ILF Tracking
    # ------------------------------------------------------------------ #

    def record_ilf(
        self,
        cycle: int,
        ilf_state: Dict[str, float],
        delta_ilf: float = 0.0,
        trend: Optional[str] = None,
    ) -> None:
        """Registra uno stato ILF."""
        event = {
            "type": "ilf_snapshot",
            "timestamp": time.time(),
            "cycle": cycle,
            **ilf_state,
            "delta_ilf": delta_ilf,
            "trend": trend,
        }
        self._write_jsonl(event)
        self._record_ilf_sql(cycle, ilf_state, delta_ilf, trend)

    def _record_ilf_sql(
        self,
        cycle: int,
        ilf_state: Dict[str, float],
        delta_ilf: float,
        trend: Optional[str],
    ) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO ilf_history
                    (timestamp, cycle, value, coherence, adaptation,
                     continuity, goal_alignment, delta_ilf, trend)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        cycle,
                        ilf_state.get("value", 0.0),
                        ilf_state.get("coherence", 0.0),
                        ilf_state.get("adaptation", 0.0),
                        ilf_state.get("continuity", 0.0),
                        ilf_state.get("goal_alignment", 0.0),
                        delta_ilf,
                        trend,
                    ),
                )
                conn.commit()

    # ------------------------------------------------------------------ #
    # DNA Version Tracking
    # ------------------------------------------------------------------ #

    def record_dna_version(
        self,
        generation: int,
        genome_hash: str,
        parent_hashes: Optional[List[str]] = None,
        mutation_type: Optional[str] = None,
        mutation_details: Optional[Dict[str, Any]] = None,
        ilf_before: Optional[float] = None,
        ilf_after: Optional[float] = None,
        accepted: bool = True,
    ) -> None:
        """Registra una nuova versione del DNA."""
        event = {
            "type": "dna_version",
            "timestamp": time.time(),
            "generation": generation,
            "genome_hash": genome_hash,
            "parent_hashes": parent_hashes or [],
            "mutation_type": mutation_type,
            "mutation_details": mutation_details,
            "ilf_before": ilf_before,
            "ilf_after": ilf_after,
            "accepted": accepted,
        }
        self._write_jsonl(event)
        self._record_dna_sql(
            generation, genome_hash, parent_hashes,
            mutation_type, mutation_details, ilf_before, ilf_after, accepted
        )

    def _record_dna_sql(
        self,
        generation: int,
        genome_hash: str,
        parent_hashes: Optional[List[str]],
        mutation_type: Optional[str],
        mutation_details: Optional[Dict[str, Any]],
        ilf_before: Optional[float],
        ilf_after: Optional[float],
        accepted: bool,
    ) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO dna_versions
                    (timestamp, generation, genome_hash, parent_hashes,
                     mutation_type, mutation_details, ilf_before, ilf_after, accepted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        generation,
                        genome_hash,
                        json.dumps(parent_hashes) if parent_hashes else None,
                        mutation_type,
                        json.dumps(mutation_details) if mutation_details else None,
                        ilf_before,
                        ilf_after,
                        accepted,
                    ),
                )
                conn.commit()

    # ------------------------------------------------------------------ #
    # Mutation Tracking
    # ------------------------------------------------------------------ #

    def record_mutation(
        self,
        generation: int,
        gene_name: str,
        mutation_action: str,
        old_value: Any = None,
        new_value: Any = None,
        ilf_impact: Optional[float] = None,
        accepted: bool = False,
    ) -> None:
        """Registra una singola mutazione."""
        event = {
            "type": "mutation",
            "timestamp": time.time(),
            "generation": generation,
            "gene_name": gene_name,
            "mutation_action": mutation_action,
            "old_value": str(old_value) if old_value is not None else None,
            "new_value": str(new_value if new_value is not None else None),
            "ilf_impact": ilf_impact,
            "accepted": accepted,
        }
        self._write_jsonl(event)
        self._record_mutation_sql(
            generation, gene_name, mutation_action,
            old_value, new_value, ilf_impact, accepted
        )

    def _record_mutation_sql(
        self,
        generation: int,
        gene_name: str,
        mutation_action: str,
        old_value: Any,
        new_value: Any,
        ilf_impact: Optional[float],
        accepted: bool,
    ) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO mutations
                    (timestamp, generation, gene_name, mutation_action,
                     old_value, new_value, ilf_impact, accepted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        generation,
                        gene_name,
                        mutation_action,
                        str(old_value) if old_value is not None else None,
                        str(new_value) if new_value is not None else None,
                        ilf_impact,
                        accepted,
                    ),
                )
                conn.commit()

    # ------------------------------------------------------------------ #
    # CV Events Tracking
    # ------------------------------------------------------------------ #

    def record_cv_event(
        self,
        branch_id: str,
        branch_name: str,
        parent_branch: Optional[str] = None,
        trigger_reason: Optional[str] = None,
        ilf_before: Optional[float] = None,
        ilf_after: Optional[float] = None,
        ilf_delta: Optional[float] = None,
        status: str = "exploring",
        explored_depth: int = 0,
    ) -> None:
        """Registra un evento del CV Engine."""
        event = {
            "type": "cv_event",
            "timestamp": time.time(),
            "branch_id": branch_id,
            "branch_name": branch_name,
            "parent_branch": parent_branch,
            "trigger_reason": trigger_reason,
            "ilf_before": ilf_before,
            "ilf_after": ilf_after,
            "ilf_delta": ilf_delta,
            "status": status,
            "explored_depth": explored_depth,
        }
        self._write_jsonl(event)
        self._record_cv_sql(
            branch_id, branch_name, parent_branch, trigger_reason,
            ilf_before, ilf_after, ilf_delta, status, explored_depth
        )

    def _record_cv_sql(
        self,
        branch_id: str,
        branch_name: str,
        parent_branch: Optional[str],
        trigger_reason: Optional[str],
        ilf_before: Optional[float],
        ilf_after: Optional[float],
        ilf_delta: Optional[float],
        status: str,
        explored_depth: int,
    ) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO cv_events
                    (timestamp, branch_id, branch_name, parent_branch,
                     trigger_reason, ilf_before, ilf_after, ilf_delta,
                     status, explored_depth)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        branch_id,
                        branch_name,
                        parent_branch,
                        trigger_reason,
                        ilf_before,
                        ilf_after,
                        ilf_delta,
                        status,
                        explored_depth,
                    ),
                )
                conn.commit()

    # ------------------------------------------------------------------ #
    # Fitness Evolution Tracking
    # ------------------------------------------------------------------ #

    def record_fitness_evolution(
        self,
        cycle: int,
        population_size: int,
        fitness_mean: float,
        fitness_std: float,
        fitness_best: float,
        diversity_score: float,
        stagnation_cycles: int = 0,
        active_engine: str = "unknown",
    ) -> None:
        """Registra lo stato della popolazione."""
        event = {
            "type": "fitness_evolution",
            "timestamp": time.time(),
            "cycle": cycle,
            "population_size": population_size,
            "fitness_mean": fitness_mean,
            "fitness_std": fitness_std,
            "fitness_best": fitness_best,
            "diversity_score": diversity_score,
            "stagnation_cycles": stagnation_cycles,
            "active_engine": active_engine,
        }
        self._write_jsonl(event)
        self._record_fitness_sql(
            cycle, population_size, fitness_mean, fitness_std,
            fitness_best, diversity_score, stagnation_cycles, active_engine
        )

    def _record_fitness_sql(
        self,
        cycle: int,
        population_size: int,
        fitness_mean: float,
        fitness_std: float,
        fitness_best: float,
        diversity_score: float,
        stagnation_cycles: int,
        active_engine: str,
    ) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO fitness_evolution
                    (timestamp, cycle, population_size, fitness_mean,
                     fitness_std, fitness_best, diversity_score,
                     stagnation_cycles, active_engine)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        cycle,
                        population_size,
                        fitness_mean,
                        fitness_std,
                        fitness_best,
                        diversity_score,
                        stagnation_cycles,
                        active_engine,
                    ),
                )
                conn.commit()

    # ------------------------------------------------------------------ #
    # Branch History Tracking
    # ------------------------------------------------------------------ #

    def record_branch(
        self,
        branch_id: str,
        branch_name: str,
        parent_branch_id: Optional[str] = None,
        depth: int = 0,
        ilf_score: Optional[float] = None,
        status: str = "active",
        merged_into: Optional[str] = None,
        pruned_at: Optional[float] = None,
    ) -> None:
        """Registra la creazione o aggiornamento di un branch."""
        event = {
            "type": "branch",
            "timestamp": time.time(),
            "branch_id": branch_id,
            "branch_name": branch_name,
            "parent_branch_id": parent_branch_id,
            "depth": depth,
            "ilf_score": ilf_score,
            "status": status,
            "merged_into": merged_into,
            "pruned_at": pruned_at,
        }
        self._write_jsonl(event)
        self._record_branch_sql(
            branch_id, branch_name, parent_branch_id,
            depth, ilf_score, status, merged_into, pruned_at
        )

    def _record_branch_sql(
        self,
        branch_id: str,
        branch_name: str,
        parent_branch_id: Optional[str],
        depth: int,
        ilf_score: Optional[float],
        status: str,
        merged_into: Optional[str],
        pruned_at: Optional[float],
    ) -> None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO branch_history
                    (timestamp, branch_id, parent_branch_id, branch_name,
                     depth, ilf_score, status, merged_into, pruned_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        time.time(),
                        branch_id,
                        parent_branch_id,
                        branch_name,
                        depth,
                        ilf_score,
                        status,
                        merged_into,
                        pruned_at,
                    ),
                )
                conn.commit()

    # ------------------------------------------------------------------ #
    # Query Methods
    # ------------------------------------------------------------------ #

    def get_ilf_history(
        self, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Recupera la storia dell'ILF."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM ilf_history ORDER BY cycle DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
                return [dict(row) for row in cursor.fetchall()]

    def get_dna_versions(self, generation: Optional[int] = None) -> List[Dict[str, Any]]:
        """Recupera le versioni del DNA."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if generation is not None:
                    cursor.execute(
                        "SELECT * FROM dna_versions WHERE generation = ? ORDER BY timestamp DESC",
                        (generation,),
                    )
                else:
                    cursor.execute("SELECT * FROM dna_versions ORDER BY timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]

    def get_mutations(
        self, gene_name: Optional[str] = None, accepted: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Recupera le mutazioni con filtri."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                query = "SELECT * FROM mutations WHERE 1=1"
                params = []
                if gene_name:
                    query += " AND gene_name = ?"
                    params.append(gene_name)
                if accepted is not None:
                    query += " AND accepted = ?"
                    params.append(accepted)
                cursor.execute(query + " ORDER BY timestamp DESC", params)
                return [dict(row) for row in cursor.fetchall()]

    def get_cv_events(self, branch_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recupera eventi CV."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if branch_id:
                    cursor.execute(
                        "SELECT * FROM cv_events WHERE branch_id = ? ORDER BY timestamp DESC",
                        (branch_id,),
                    )
                else:
                    cursor.execute("SELECT * FROM cv_events ORDER BY timestamp DESC")
                return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """Restituisce statistiche aggregate."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Statistiche ILF
                cursor.execute("SELECT COUNT(*) FROM ilf_history")
                ilf_count = cursor.fetchone()[0]

                cursor.execute("SELECT AVG(value), MAX(value), MIN(value) FROM ilf_history")
                ilf_row = cursor.fetchone()
                ilf_avg, ilf_max, ilf_min = ilf_row if ilf_row else (0, 0, 0)

                # Statistiche DNA
                cursor.execute("SELECT COUNT(*) FROM dna_versions")
                dna_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM dna_versions WHERE accepted = 1")
                dna_accepted = cursor.fetchone()[0]

                # Statistiche mutazioni
                cursor.execute("SELECT COUNT(*) FROM mutations")
                mutation_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM mutations WHERE accepted = 1")
                mutation_accepted = cursor.fetchone()[0]

                # Statistiche CV
                cursor.execute("SELECT COUNT(*) FROM cv_events")
                cv_count = cursor.fetchone()[0]

                return {
                    "ilf_records": ilf_count,
                    "ilf_avg": ilf_avg or 0.0,
                    "ilf_max": ilf_max or 0.0,
                    "ilf_min": ilf_min or 0.0,
                    "dna_versions": dna_count,
                    "dna_accepted": dna_accepted,
                    "mutations_total": mutation_count,
                    "mutations_accepted": mutation_accepted,
                    "cv_events": cv_count,
                    "db_path": str(self.db_path),
                    "jsonl_path": str(self.jsonl_path),
                }

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _write_jsonl(self, event: Dict[str, Any]) -> None:
        """Scrive un evento nel file JSONL."""
        with self._lock:
            with open(self.jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def close(self) -> None:
        """Chiude le risorse."""
        pass  # SQLite connection auto-closes