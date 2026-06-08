"""Social Model Engine — Theory of Mind and agent modelling for SPEACE."""

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AgentType(str, Enum):
    """Enumeration of known agent types."""

    HUMAN = "human"
    SPEACE_CLONE = "speace_clone"
    SERVICE = "service"
    UNKNOWN = "unknown"


@dataclass
class InteractionRecord:
    """A single observed interaction with an agent."""

    action: str
    outcome: Any
    timestamp: float = 0.0


@dataclass
class AgentModel:
    """Internal representation of another agent."""

    agent_id: str
    agent_type: AgentType
    beliefs: Dict[str, Any] = field(default_factory=dict)
    goals: List[str] = field(default_factory=list)
    predicted_actions: Dict[str, float] = field(default_factory=dict)
    trust_score: float = 0.5
    interaction_history: List[InteractionRecord] = field(default_factory=list)
    nested_beliefs: Dict[str, float] = field(default_factory=dict)
    nested_belief_confidence: float = 0.0


class SocialModelEngine:
    """Maintains predictive models of other agents and nested (theory-of-mind) beliefs."""

    def __init__(self) -> None:
        self.agents: Dict[str, AgentModel] = {}

    def register_agent(
        self,
        agent_id: str,
        agent_type: str | AgentType,
        initial_beliefs: Optional[Dict[str, Any]] = None,
        initial_goals: Optional[List[str]] = None,
    ) -> None:
        """Register a new agent in the social model."""
        if isinstance(agent_type, str):
            agent_type = AgentType(agent_type)
        self.agents[agent_id] = AgentModel(
            agent_id=agent_id,
            agent_type=agent_type,
            beliefs=initial_beliefs or {},
            goals=initial_goals or [],
        )

    def observe_action(self, agent_id: str, action: str, outcome: Any) -> None:
        """Update the agent model after observing an action and its outcome."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
        agent = self.agents[agent_id]
        record = InteractionRecord(action=action, outcome=outcome, timestamp=time.time())
        agent.interaction_history.append(record)

        # Laplace-smoothed frequency update for predicted_actions
        action_counts: Dict[str, float] = {
            a: p * max(1, len(agent.interaction_history) - 1) for a, p in agent.predicted_actions.items()
        }
        action_counts[action] = action_counts.get(action, 0) + 1
        total = sum(action_counts.values())
        agent.predicted_actions = {a: c / total for a, c in action_counts.items()}

    def predict_next_action(self, agent_id: str) -> Tuple[str, float]:
        """Return the most likely next action and confidence for the given agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
        agent = self.agents[agent_id]
        if not agent.predicted_actions:
            return ("unknown", 0.0)
        best_action = max(agent.predicted_actions, key=agent.predicted_actions.get)  # type: ignore[arg-type]
        confidence = agent.predicted_actions[best_action]
        return (best_action, confidence)

    def infer_goal(self, agent_id: str) -> Optional[str]:
        """Infer the agent's most likely goal from observed action outcomes."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
        agent = self.agents[agent_id]
        if not agent.interaction_history or not agent.goals:
            return None

        goal_scores: Dict[str, float] = {goal: 0.0 for goal in agent.goals}
        for record in agent.interaction_history:
            outcome_str = json.dumps(record.outcome) if not isinstance(record.outcome, str) else record.outcome
            for goal in agent.goals:
                if goal in outcome_str:
                    goal_scores[goal] += 1.0

        best_goal = max(goal_scores, key=goal_scores.get)  # type: ignore[arg-type]
        if goal_scores[best_goal] == 0:
            return None
        return best_goal

    def update_trust(self, agent_id: str, interaction_outcome: str) -> None:
        """Increase or decrease trust based on cooperation vs defection."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
        agent = self.agents[agent_id]
        if interaction_outcome == "cooperation":
            agent.trust_score = min(1.0, agent.trust_score + 0.1)
        elif interaction_outcome == "defection":
            agent.trust_score = max(0.0, agent.trust_score - 0.2)

    def get_agent_summary(self, agent_id: str) -> str:
        """Return a human-readable summary of the agent model."""
        if agent_id not in self.agents:
            return f"No model for agent {agent_id}"
        agent = self.agents[agent_id]
        lines = [
            f"Agent {agent.agent_id} ({agent.agent_type.value})",
            f"  Trust: {agent.trust_score:.2f}",
            f"  Goals: {', '.join(agent.goals) or 'None'}",
            f"  Beliefs: {json.dumps(agent.beliefs)}",
            f"  Predicted actions: {json.dumps(agent.predicted_actions)}",
            f"  Interaction count: {len(agent.interaction_history)}",
        ]
        return "\n".join(lines)

    def get_all_agent_summaries(self) -> Dict[str, str]:
        """Return summaries for all known agents."""
        return {agent_id: self.get_agent_summary(agent_id) for agent_id in self.agents}

    def set_nested_belief(
        self,
        my_belief_about_agent: str,
        agent_belief_about_world: str,
        confidence: float,
    ) -> None:
        """Store a theory-of-mind belief: 'I believe that <agent> believes <X>' with confidence."""
        if my_belief_about_agent not in self.agents:
            raise ValueError(f"Agent {my_belief_about_agent} not registered")
        agent = self.agents[my_belief_about_agent]
        agent.nested_beliefs[agent_belief_about_world] = confidence
        if agent.nested_beliefs:
            agent.nested_belief_confidence = sum(agent.nested_beliefs.values()) / len(
                agent.nested_beliefs
            )

    def get_theory_of_mind(self, agent_id: str) -> Dict[str, Any]:
        """Return the nested belief structure for the given agent."""
        if agent_id not in self.agents:
            raise ValueError(f"Agent {agent_id} not registered")
        agent = self.agents[agent_id]
        return {
            "agent_id": agent.agent_id,
            "nested_beliefs": agent.nested_beliefs.copy(),
            "overall_confidence": agent.nested_belief_confidence,
        }
