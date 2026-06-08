"""Cooperation Protocol — game-theoretic cooperation between SPEACE and other agents."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ProposalStatus(str, Enum):
    """Lifecycle states of a cooperation proposal."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXECUTED = "executed"
    DEFECTED = "defected"


@dataclass
class CooperationRecord:
    """A single cooperation interaction record."""

    agent_id: str
    timestamp: float
    offer: Any
    request: Any
    status: ProposalStatus
    actual_outcome: Optional[Any] = None


class CooperationProtocol:
    """Implements game-theoretic cooperation using social models and trust scores."""

    def __init__(self, social_model_engine: Any) -> None:
        self.social_model_engine = social_model_engine
        self.proposals: List[CooperationRecord] = []
        self.executed_cooperations: Dict[str, List[CooperationRecord]] = {}

    def propose_cooperation(self, agent_id: str, my_offer: Any, my_request: Any) -> str:
        """Create a new cooperation proposal and return its internal id."""
        record = CooperationRecord(
            agent_id=agent_id,
            timestamp=time.time(),
            offer=my_offer,
            request=my_request,
            status=ProposalStatus.PENDING,
        )
        self.proposals.append(record)
        if agent_id not in self.executed_cooperations:
            self.executed_cooperations[agent_id] = []
        self.executed_cooperations[agent_id].append(record)
        return f"{agent_id}_{record.timestamp}"

    def evaluate_cooperation_proposal(
        self, agent_id: str, offer: Any, request: Any
    ) -> Tuple[bool, float]:
        """Evaluate a proposal using trust and predicted benefit. Returns (accept, score)."""
        engine = self.social_model_engine
        if agent_id not in engine.agents:
            return False, 0.0

        agent = engine.agents[agent_id]
        trust = agent.trust_score

        # Predicted benefit: numeric surplus if both are numbers, otherwise neutral
        if isinstance(offer, (int, float)) and isinstance(request, (int, float)):
            denom = max(abs(offer), abs(request), 1.0)
            predicted_benefit = max(0.0, (offer - request) / denom)
        else:
            predicted_benefit = 0.5

        score = trust * 0.5 + predicted_benefit * 0.5
        accepted = score > 0.5
        return accepted, score

    def execute_cooperation(self, agent_id: str, agreed_action: str) -> Dict[str, Any]:
        """Record the execution of a cooperation agreement."""
        engine = self.social_model_engine
        if agent_id not in engine.agents:
            raise ValueError(f"Agent {agent_id} not registered")

        record = CooperationRecord(
            agent_id=agent_id,
            timestamp=time.time(),
            offer=agreed_action,
            request=agreed_action,
            status=ProposalStatus.EXECUTED,
        )
        self.proposals.append(record)
        if agent_id not in self.executed_cooperations:
            self.executed_cooperations[agent_id] = []
        self.executed_cooperations[agent_id].append(record)

        return {
            "agent_id": agent_id,
            "action": agreed_action,
            "status": "executed",
            "trust_at_execution": engine.agents[agent_id].trust_score,
        }

    def detect_defection(
        self, agent_id: str, expected_outcome: Any, actual_outcome: Any
    ) -> bool:
        """Flag a defection when the actual outcome diverges from the expected one."""
        is_defection = expected_outcome != actual_outcome
        if is_defection:
            record = CooperationRecord(
                agent_id=agent_id,
                timestamp=time.time(),
                offer=None,
                request=None,
                status=ProposalStatus.DEFECTED,
                actual_outcome=actual_outcome,
            )
            self.proposals.append(record)
            if agent_id not in self.executed_cooperations:
                self.executed_cooperations[agent_id] = []
            self.executed_cooperations[agent_id].append(record)
        return is_defection

    def get_cooperation_score(self, agent_id: str) -> float:
        """Return the historical cooperation rate for the agent [0-1]."""
        if agent_id not in self.executed_cooperations:
            return 0.0
        records = self.executed_cooperations[agent_id]
        if not records:
            return 0.0
        cooperated = sum(
            1 for r in records if r.status in (ProposalStatus.EXECUTED, ProposalStatus.ACCEPTED)
        )
        return cooperated / len(records)
