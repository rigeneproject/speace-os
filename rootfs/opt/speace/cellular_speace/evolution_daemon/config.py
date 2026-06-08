"""DaemonConfig — runtime configuration for the evolution daemon.

All defaults are tuned for the 120-minute /loop session: ~12 cycles at
300 s each. Ports follow user choice (5692 + 5697 with auto-fallback to
5693/5698 if busy).
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field
from typing import List


@dataclass
class DaemonConfig:
    """Static configuration for the evolution daemon.

    Attributes are read-only after construction; pass a new instance to
    reconfigure.
    """

    # ------------------------------------------------------------------ #
    # Filesystem / data roots
    # ------------------------------------------------------------------ #
    repo_root: pathlib.Path = field(
        default_factory=lambda: pathlib.Path(__file__).resolve().parent.parent
    )
    data_root: pathlib.Path = field(init=False)

    # ------------------------------------------------------------------ #
    # Web dashboard ports
    # ------------------------------------------------------------------ #
    main_port: int = 5692
    neuron_port: int = 5697
    port_candidates: List[int] = field(
        default_factory=lambda: [5692, 5693, 5694, 5695]
    )
    neuron_port_candidates: List[int] = field(
        default_factory=lambda: [5697, 5698, 5699, 5700]
    )

    # ------------------------------------------------------------------ #
    # Loop scheduling
    # ------------------------------------------------------------------ #
    cycle_interval_sec: float = 300.0
    runtime_tick_interval: float = 1.0
    benchmark_timeout_sec: float = 60.0
    arc_timeout_sec: float = 120.0
    arc_task_limit: int = 5

    # ------------------------------------------------------------------ #
    # Genome / runtime paths
    # ------------------------------------------------------------------ #
    genome_path: pathlib.Path = field(init=False)

    # ------------------------------------------------------------------ #
    # Knowledge graph + plan
    # ------------------------------------------------------------------ #
    knowledge_graph_path: pathlib.Path = field(init=False)
    engineering_plan_path: pathlib.Path = field(init=False)
    daemon_state_path: pathlib.Path = field(init=False)
    daemon_tasks_path: pathlib.Path = field(init=False)

    # ------------------------------------------------------------------ #
    # Governance
    # ------------------------------------------------------------------ #
    auto_apply_mutations: bool = False
    auto_apply_dna: bool = False
    auto_fix_errors: bool = False  # log + proposal only

    def __post_init__(self) -> None:
        self.data_root = self.repo_root / "data"
        self.genome_path = (
            self.repo_root / "speace_core" / "dna" / "genome" / "default_genome.yaml"
        )
        self.knowledge_graph_path = self.data_root / "knowledge_graph.jsonl"
        self.engineering_plan_path = self.data_root / "engineering_plan.json"
        self.daemon_state_path = self.data_root / "daemon_state.json"
        self.daemon_tasks_path = self.data_root / "daemon_tasks.jsonl"

    # ------------------------------------------------------------------ #
    # Convenience
    # ------------------------------------------------------------------ #
    def ensure_dirs(self) -> None:
        """Create all data subdirectories the daemon writes to."""
        for sub in [
            "self_improvement",
            "evolution_daemon",
            "runtime",
            "benchmark",
            "knowledge_graph",
        ]:
            (self.data_root / sub).mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "DaemonConfig":
        """Build a config honouring ``SPEACE_*`` env vars where set."""
        cfg = cls()
        if v := os.environ.get("SPEACE_CYCLE_INTERVAL_SEC"):
            cfg.cycle_interval_sec = float(v)
        if v := os.environ.get("SPEACE_MAIN_PORT"):
            cfg.main_port = int(v)
        if v := os.environ.get("SPEACE_NEURON_PORT"):
            cfg.neuron_port = int(v)
        return cfg
