import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.organism.organism_models import OrganismBusMessage


class OrganismBus:
    """T59 — Bus organismico interno per messaggi tra sottosistemi."""

    def __init__(self, max_queue_depth: int = 1000, seed: int = 42):
        self.max_queue_depth = max_queue_depth
        self._messages: List[OrganismBusMessage] = []
        self._acks: Dict[str, List[str]] = {}
        self._dropped_count = 0
        self._processed_count = 0
        self._seed = seed
        random.seed(seed)

    def publish(self, message: OrganismBusMessage) -> bool:
        if len(self._messages) >= self.max_queue_depth:
            # Non droppare messaggi safety-relevant
            if not message.safety_relevant:
                self._dropped_count += 1
                return False
            # Se safety-relevant, droppare il messaggio a più bassa priorità non safety
            non_safety = [m for m in self._messages if not m.safety_relevant]
            if non_safety:
                to_drop = min(non_safety, key=lambda m: m.priority)
                self._messages.remove(to_drop)
                self._dropped_count += 1
            else:
                self._dropped_count += 1
                return False

        if not message.timestamp:
            message.timestamp = datetime.now(timezone.utc).isoformat()
        self._messages.append(message)
        self._processed_count += 1
        return True

    def broadcast(self, message: OrganismBusMessage) -> bool:
        # Broadcast = publish senza target specifico
        message.target = None
        return self.publish(message)

    def poll(self, target_subsystem: str) -> List[OrganismBusMessage]:
        matched: List[OrganismBusMessage] = []
        remaining: List[OrganismBusMessage] = []
        for msg in self._messages:
            if msg.target == target_subsystem or (msg.target is None and msg.source != target_subsystem):
                matched.append(msg)
            else:
                remaining.append(msg)
        self._messages = remaining
        return matched

    def acknowledge(self, message_id: str, subsystem: str) -> bool:
        if message_id not in self._acks:
            self._acks[message_id] = []
        if subsystem not in self._acks[message_id]:
            self._acks[message_id].append(subsystem)
            return True
        return False

    def drop_expired_messages(self, current_tick: int) -> int:
        expired: List[OrganismBusMessage] = []
        remaining: List[OrganismBusMessage] = []
        for msg in self._messages:
            if msg.ttl_ticks <= 0 and not msg.safety_relevant:
                expired.append(msg)
            else:
                remaining.append(msg)
        self._messages = remaining
        self._dropped_count += len(expired)
        return len(expired)

    def get_queue_depth(self) -> int:
        return len(self._messages)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "queue_depth": self.get_queue_depth(),
            "processed_count": self._processed_count,
            "dropped_count": self._dropped_count,
            "acknowledged_messages": len(self._acks),
        }
