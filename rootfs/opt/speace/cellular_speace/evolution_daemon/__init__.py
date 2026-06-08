"""SPEACE Evolution Daemon — auto-improvement loop T-series oriented to AGI.

Provides a continuous 14-task cycle that:
  1. starts the brain+organism runtime,
  2. runs neurofunctional / ARC-AGI benchmarks,
  3. analyses cognition, proposes refactors (no auto-apply per T104 governance),
  4. diagnoses compartments,
  5. tracks neuron/synapse counts and activation,
  6. detects errors and emits log+proposal,
  7. maintains a Knowledge Graph and a regenerate-able Engineering Plan,
  8. performs regression review,
  9. loops.

The daemon is *advisory* — it never modifies SPEACE source code or runtime
state without human approval. Proposals are stored under
``data/self_improvement/proposals.jsonl`` for review.
"""

from evolution_daemon.config import DaemonConfig
from evolution_daemon.daemon import EvolutionDaemon

__all__ = ["DaemonConfig", "EvolutionDaemon"]
__version__ = "0.1.0"
