"""Conflict Resolution Engine — detects and mediates inter-agent conflicts."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ConflictRecord:
    """A single detected conflict between two agents."""

    agent1_id: str
    agent2_id: str
    conflict_type: str
    details: str


class ConflictResolutionEngine:
    """Detects conflicts between agents and proposes compromises or escalates threats."""

    def __init__(self, social_model_engine: Any) -> None:
        self.social_model_engine = social_model_engine
        self.conflicts: List[ConflictRecord] = []
        self.threat_levels: Dict[str, int] = {}

    def detect_conflict(
        self, agent1_id: str, agent2_id: str
    ) -> Optional[ConflictRecord]:
        """Find goals or beliefs that are mutually incompatible between two agents."""
        engine = self.social_model_engine
        if agent1_id not in engine.agents or agent2_id not in engine.agents:
            return None

        agent1 = engine.agents[agent1_id]
        agent2 = engine.agents[agent2_id]
        conflict_details: List[str] = []

        # Goal incompatibility: one agent wants X, the other wants not_X
        for g1 in agent1.goals:
            for g2 in agent2.goals:
                if g1.startswith("not_") and g1[4:] == g2:
                    conflict_details.append(f"Goal conflict: {g1} vs {g2}")
                elif g2.startswith("not_") and g2[4:] == g1:
                    conflict_details.append(f"Goal conflict: {g1} vs {g2}")

        # Belief incompatibility: same key, different values
        for key in set(agent1.beliefs.keys()) & set(agent2.beliefs.keys()):
            if agent1.beliefs[key] != agent2.beliefs[key]:
                conflict_details.append(
                    f"Belief conflict on {key}: {agent1.beliefs[key]} vs {agent2.beliefs[key]}"
                )

        if conflict_details:
            record = ConflictRecord(
                agent1_id=agent1_id,
                agent2_id=agent2_id,
                conflict_type="goal_belief_mismatch",
                details="; ".join(conflict_details),
            )
            self.conflicts.append(record)
            return record
        return None

    def mediate(self, agent1_id: str, agent2_id: str) -> Optional[Dict[str, Any]]:
        """Propose a compromise based on shared beliefs and common goals."""
        engine = self.social_model_engine
        if agent1_id not in engine.agents or agent2_id not in engine.agents:
            return None

        agent1 = engine.agents[agent1_id]
        agent2 = engine.agents[agent2_id]

        shared_beliefs: Dict[str, Any] = {}
        for key in set(agent1.beliefs.keys()) & set(agent2.beliefs.keys()):
            if agent1.beliefs[key] == agent2.beliefs[key]:
                shared_beliefs[key] = agent1.beliefs[key]

        common_goals = list(set(agent1.goals) & set(agent2.goals))

        conflicting_goals: List[tuple] = []
        for g1 in agent1.goals:
            for g2 in agent2.goals:
                if g1.startswith("not_") and g1[4:] == g2:
                    conflicting_goals.append((g1, g2))
                elif g2.startswith("not_") and g2[4:] == g1:
                    conflicting_goals.append((g1, g2))

        return {
            "shared_beliefs": shared_beliefs,
            "common_goals": common_goals,
            "suggested_compromise": (
                f"Both agents should focus on common goals: {common_goals}"
                if common_goals
                else "No common goals found; consider negotiation"
            ),
            "conflicting_goals_to_abandon": conflicting_goals,
        }

    def escalate(self, agent_id: str) -> int:
        """Raise the threat level for an adversarial agent. Returns new level."""
        self.threat_levels[agent_id] = self.threat_levels.get(agent_id, 0) + 1
        return self.threat_levels[agent_id]
