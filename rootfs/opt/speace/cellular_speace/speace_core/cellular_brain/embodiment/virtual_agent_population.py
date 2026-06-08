"""VirtualAgentPopulation — lightweight simulated agents for the cognitive nursery (T168).

Agents are driven by simplified BT/FSM with basic drives (approach food, avoid threat).
They provide social interaction targets inside the sandbox.
"""

import uuid
from typing import Any, Dict, List, Optional


class VirtualAgent:
    """A single lightweight agent inside the nursery."""

    def __init__(self, agent_id: str, behavior_profile: str = "curious") -> None:
        self.agent_id = agent_id
        self.behavior_profile = behavior_profile
        self.state: str = "idle"
        self.position: float = 0.0
        self.drive: str = "explore"
        self._tick_count: int = 0

    def tick(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self._tick_count += 1
        # Simplified behavior FSM
        if self.behavior_profile == "curious":
            if context.get("food_nearby", False):
                self.state = "approaching"
                self.position += 1.0
            elif context.get("threat_nearby", False):
                self.state = "fleeing"
                self.position -= 2.0
            else:
                self.state = "wandering"
                self.position += 0.5
        elif self.behavior_profile == "cautious":
            if context.get("threat_nearby", False):
                self.state = "fleeing"
                self.position -= 3.0
            elif context.get("food_nearby", False):
                self.state = "approaching"
                self.position += 0.5
            else:
                self.state = "idle"
        else:
            self.state = "idle"

        return {
            "agent_id": self.agent_id,
            "state": self.state,
            "position": self.position,
            "drive": self.drive,
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "behavior_profile": self.behavior_profile,
            "state": self.state,
            "position": self.position,
            "drive": self.drive,
            "tick_count": self._tick_count,
        }


class VirtualAgentPopulation:
    """Population manager for nursery agents."""

    def __init__(self) -> None:
        self._agents: Dict[str, VirtualAgent] = {}

    def spawn(self, behavior_profile: str = "curious") -> VirtualAgent:
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        agent = VirtualAgent(agent_id, behavior_profile)
        self._agents[agent_id] = agent
        return agent

    def tick_all(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [agent.tick(context) for agent in self._agents.values()]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "agent_count": len(self._agents),
            "agents": [a.snapshot() for a in self._agents.values()],
        }
