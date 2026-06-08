from speace_core.cellular_brain.self_improvement.limitation_detector import (
    LimitationDetector,
    LimitationDiagnosis,
    LimitationSignal,
)
from speace_core.cellular_brain.self_improvement.architecture_rewriter import (
    ArchitectureRewriter,
    ArchitectureRewriteProposal,
    RewriteSimulationResult,
    SelfImprovementCycleResult,
)
from speace_core.cellular_brain.self_improvement.proposal_store import ProposalStore
from speace_core.cellular_brain.self_improvement.outcome_tracker import (
    OutcomeTracker,
    ProposalOutcome,
)
from speace_core.cellular_brain.self_improvement.proposal_learning_engine import (
    ProposalLearningEngine,
    ProposalLearningRecord,
)
from speace_core.cellular_brain.self_improvement.self_improvement_memory import (
    SelfImprovementMemory,
)
from speace_core.cellular_brain.self_improvement.self_improvement_loop import (
    SelfImprovementLoop,
)
# T169 — Phase 3 closed loop
from speace_core.cellular_brain.self_improvement.self_modification_cycle import (
    SelfModificationCycle,
    SelfModificationCycleResult,
)

__all__ = [
    "LimitationDetector",
    "LimitationDiagnosis",
    "LimitationSignal",
    "ArchitectureRewriter",
    "ArchitectureRewriteProposal",
    "RewriteSimulationResult",
    "SelfImprovementCycleResult",
    "ProposalStore",
    "OutcomeTracker",
    "ProposalOutcome",
    "ProposalLearningEngine",
    "ProposalLearningRecord",
    "SelfImprovementMemory",
    "SelfImprovementLoop",
    "SelfModificationCycle",
    "SelfModificationCycleResult",
]
