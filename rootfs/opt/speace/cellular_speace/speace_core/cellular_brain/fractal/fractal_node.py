from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
import uuid
import time


@dataclass
class FractalNodeConfig:
    """Configurazione per un nodo fractale."""

    node_type: str = "default"
    max_children: int = 4
    memory_capacity: int = 100
    evaluation_interval: float = 1.0  # secondi
    learning_rate: float = 0.1
    communication_enabled: bool = True
    autonomous: bool = True  # Può operare senza input esterno


@dataclass
class FractalNodeState:
    """Stato interno di un nodo fractale."""

    active: bool = True
    activation_level: float = 0.5
    energy_consumption: float = 0.0
    last_evaluation: float = field(default_factory=time.time)
    cycles_processed: int = 0
    children_count: int = 0


class FractalNode:
    """Nodo nell'architettura cognitiva frattale.

    Ogni nodo contiene:
    - memory: contenitore per memorie
    - goal: obiettivo corrente del nodo
    - evaluation: capacità di valutare situazioni
    - learning: meccanismo di apprendimento
    - communication: capacità di comunicare con altri nodi

    L'architettura è ricorsiva: ogni nodo può avere figli.
    """

    def __init__(
        self,
        node_id: Optional[str] = None,
        config: Optional[FractalNodeConfig] = None,
        parent: Optional["FractalNode"] = None,
    ):
        self.id = node_id or str(uuid.uuid4())[:8]
        self.config = config or FractalNodeConfig()
        self.parent = parent
        self.children: Dict[str, "FractalNode"] = {}

        # Componenti interni
        self._memory: Dict[str, Any] = {}
        self._goals: List[Dict[str, Any]] = []
        self._evaluation_score: float = 0.5
        self._learning_buffer: List[Dict[str, Any]] = []

        # Stato
        self._state = FractalNodeState()
        self._created_at = time.time()

        # Callbacks
        self._on_evaluate: Optional[Callable[["FractalNode"], None]] = None
        self._on_communicate: Optional[Callable[["FractalNode", Any], None]] = None

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def spawn_child(
        self,
        node_id: Optional[str] = None,
        config: Optional[FractalNodeConfig] = None,
    ) -> "FractalNode":
        """Crea un nodo figlio.

        Args:
            node_id: ID opzionale per il figlio
            config: Configurazione opzionale

        Returns:
            Il nodo figlio creato
        """
        if len(self.children) >= self.config.max_children:
            raise RuntimeError(
                f"Cannot spawn child: max children ({self.config.max_children}) reached"
            )

        child = FractalNode(
            node_id=node_id,
            config=config,
            parent=self,
        )

        self.children[child.id] = child
        self._state.children_count = len(self.children)

        return child

    def prune_child(self, child_id: str) -> bool:
        """Rimuove un figlio.

        Returns:
            True se rimosso, False se non trovato
        """
        if child_id in self.children:
            del self.children[child_id]
            self._state.children_count = len(self.children)
            return True
        return False

    def activate(self) -> None:
        """Attiva il nodo."""
        self._state.active = True
        self._state.activation_level = 0.5

    def deactivate(self) -> None:
        """Disattiva il nodo."""
        self._state.active = False

    # ------------------------------------------------------------------ #
    # Memory
    # ------------------------------------------------------------------ #

    def store_memory(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Memorizza un valore."""
        if len(self._memory) >= self.config.memory_capacity:
            # Rimuovi il più vecchio
            oldest_key = min(self._memory.keys(), key=lambda k: self._memory[k].get("_stored_at", 0))
            del self._memory[oldest_key]

        self._memory[key] = {
            "value": value,
            "metadata": metadata or {},
            "_stored_at": time.time(),
            "_access_count": 0,
        }

    def retrieve_memory(self, key: str, default: Any = None) -> Any:
        """Recupera un valore dalla memoria."""
        if key in self._memory:
            entry = self._memory[key]
            entry["_access_count"] += 1
            return entry["value"]
        return default

    def forget_memory(self, key: str) -> bool:
        """Dimentica un valore."""
        if key in self._memory:
            del self._memory[key]
            return True
        return False

    def get_all_memories(self) -> Dict[str, Any]:
        """Restituisce tutte le memorie."""
        return {k: v["value"] for k, v in self._memory.items()}

    # ------------------------------------------------------------------ #
    # Goals
    # ------------------------------------------------------------------ #

    def set_goal(
        self,
        goal_id: str,
        description: str,
        priority: float = 0.5,
        target_value: Any = None,
    ) -> None:
        """Imposta un obiettivo."""
        # Rimuovi goal esistente con stesso ID
        self._goals = [g for g in self._goals if g.get("id") != goal_id]

        self._goals.append({
            "id": goal_id,
            "description": description,
            "priority": priority,
            "target_value": target_value,
            "current_value": None,
            "progress": 0.0,
            "created_at": time.time(),
        })

        # Ordina per priorità
        self._goals.sort(key=lambda g: g.get("priority", 0.5), reverse=True)

    def update_goal_progress(self, goal_id: str, current_value: Any) -> None:
        """Aggiorna il progresso di un obiettivo."""
        for goal in self._goals:
            if goal.get("id") == goal_id:
                goal["current_value"] = current_value
                if goal.get("target_value") is not None:
                    # Calcola progresso
                    target = goal["target_value"]
                    if isinstance(target, (int, float)) and isinstance(current_value, (int, float)):
                        goal["progress"] = min(1.0, current_value / target)
                break

    def get_active_goal(self) -> Optional[Dict[str, Any]]:
        """Restituisce l'obiettivo attivo (priorità più alta)."""
        return self._goals[0] if self._goals else None

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    def evaluate(self, input_data: Any) -> float:
        """Valuta un input e restituisce un score.

        Questo è il punto di integrazione con l'ILF.
        """
        score = self._calculate_evaluation_score(input_data)
        self._evaluation_score = score
        self._state.last_evaluation = time.time()
        self._state.cycles_processed += 1

        if self._on_evaluate:
            self._on_evaluate(self)

        return score

    def _calculate_evaluation_score(self, input_data: Any) -> float:
        """Calcola lo score di valutazione.

        Implementazione base: basata su memoria e obiettivi.
        """
        score = 0.5

        # Boost se l'input corrisponde a memorie recenti
        if isinstance(input_data, str) and input_data in self._memory:
            score += 0.1

        # Boost se c'è un goal attivo
        active_goal = self.get_active_goal()
        if active_goal:
            score += active_goal.get("priority", 0.5) * 0.2

        # Boost per alto activation level
        score += self._state.activation_level * 0.1

        return min(1.0, max(0.0, score))

    def set_evaluation_callback(
        self, callback: Callable[["FractalNode"], None]
    ) -> None:
        """Imposta una callback chiamata dopo ogni valutazione."""
        self._on_evaluate = callback

    # ------------------------------------------------------------------ #
    # Learning
    # ------------------------------------------------------------------ #

    def learn(self, experience: Dict[str, Any]) -> None:
        """Apprende da un'esperienza."""
        self._learning_buffer.append({
            **experience,
            "_learned_at": time.time(),
        })

        # Processa il buffer
        if len(self._learning_buffer) >= 10:
            self._process_learning_buffer()

    def _process_learning_buffer(self) -> None:
        """Processa le esperienze accumulate."""
        # Implementazione base: semplice averaging
        if not self._learning_buffer:
            return

        # Estrai pattern
        avg_importance = sum(
            e.get("importance", 0.5) for e in self._learning_buffer
        ) / len(self._learning_buffer)

        # Consolida in memoria se importante
        if avg_importance > 0.6:
            key = f"learned_{int(time.time())}"
            self.store_memory(
                key,
                {"experiences": list(self._learning_buffer), "avg_importance": avg_importance},
                metadata={"type": "consolidated_learning"},
            )

        self._learning_buffer.clear()

    # ------------------------------------------------------------------ #
    # Communication
    # ------------------------------------------------------------------ #

    def communicate(
        self,
        message: Any,
        target: Optional["FractalNode"] = None,
    ) -> None:
        """Comunica con un altro nodo o broadcast."""
        if not self.config.communication_enabled:
            return

        if target:
            # Comunicazione diretta
            self._send_message(target, message)
        else:
            # Broadcast ai figli
            for child in self.children.values():
                self._send_message(child, message)

    def _send_message(self, recipient: "FractalNode", message: Any) -> None:
        """Invia un messaggio a un destinatario."""
        if self._on_communicate:
            self._on_communicate(self, message)

        # Il ricevente processa il messaggio
        if hasattr(recipient, "receive_message"):
            recipient.receive_message(self, message)

    def receive_message(self, sender: "FractalNode", message: Any) -> None:
        """Riceve un messaggio da un altro nodo."""
        # Processa il messaggio in base al tipo
        if isinstance(message, dict):
            msg_type = message.get("type", "generic")

            if msg_type == "goal_update":
                self.set_goal(
                    message.get("goal_id", ""),
                    message.get("description", ""),
                    message.get("priority", 0.5),
                )
            elif msg_type == "memory_request":
                key = message.get("key")
                if key and key in self._memory:
                    self.communicate(
                        {"type": "memory_response", "key": key, "value": self._memory[key]["value"]},
                        target=sender,
                    )

    # ------------------------------------------------------------------ #
    # State Access
    # ------------------------------------------------------------------ #

    def get_state(self) -> FractalNodeState:
        return self._state

    def get_statistics(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.config.node_type,
            "active": self._state.active,
            "activation_level": self._state.activation_level,
            "children": len(self.children),
            "memory_items": len(self._memory),
            "active_goals": len(self._goals),
            "evaluation_score": self._evaluation_score,
            "cycles_processed": self._state.cycles_processed,
            "age_seconds": time.time() - self._created_at,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "config": {
                "node_type": self.config.node_type,
                "max_children": self.config.max_children,
                "memory_capacity": self.config.memory_capacity,
                "learning_rate": self.config.learning_rate,
                "communication_enabled": self.config.communication_enabled,
            },
            "state": {
                "active": self._state.active,
                "activation_level": self._state.activation_level,
                "children_count": self._state.children_count,
                "cycles_processed": self._state.cycles_processed,
            },
            "memory_keys": list(self._memory.keys()),
            "goals": self._goals,
            "children_ids": list(self.children.keys()),
        }

    # ------------------------------------------------------------------ #
    # Recursive Operations
    # ------------------------------------------------------------------ #

    def find_node(self, node_id: str) -> Optional["FractalNode"]:
        """Trova un nodo ricorsivamente."""
        if self.id == node_id:
            return self

        for child in self.children.values():
            found = child.find_node(node_id)
            if found:
                return found

        return None

    def get_all_descendants(self) -> List["FractalNode"]:
        """Restituisce tutti i discendenti."""
        descendants = []
        for child in self.children.values():
            descendants.append(child)
            descendants.extend(child.get_all_descendants())
        return descendants

    def broadcast_to_all(self, operation: Callable[["FractalNode"], None]) -> None:
        """Applica un'operazione a tutti i nodi nel sottoalbero."""
        operation(self)
        for child in self.children.values():
            child.broadcast_to_all(operation)


class FractalCognitiveTree:
    """Albero cognitivo frattale.

    Gestisce la radice e fornisce operazioni globali.
    """

    def __init__(self, root_config: Optional[FractalNodeConfig] = None):
        self.root = FractalNode(config=root_config)

    def get_node(self, node_id: str) -> Optional[FractalNode]:
        return self.root.find_node(node_id)

    def add_node(
        self,
        parent_id: str,
        node_id: Optional[str] = None,
        config: Optional[FractalNodeConfig] = None,
    ) -> Optional[FractalNode]:
        """Aggiunge un nodo come figlio di parent_id."""
        parent = self.get_node(parent_id)
        if parent:
            return parent.spawn_child(node_id, config)
        return None

    def remove_node(self, node_id: str) -> bool:
        """Rimuove un nodo."""
        node = self.get_node(node_id)
        if node and node.parent:
            return node.parent.prune_child(node_id)
        return False

    def get_all_nodes(self) -> List[FractalNode]:
        """Restituisce tutti i nodi."""
        nodes = [self.root]
        nodes.extend(self.root.get_all_descendants())
        return nodes

    def get_statistics(self) -> Dict[str, Any]:
        all_nodes = self.get_all_nodes()
        return {
            "total_nodes": len(all_nodes),
            "root_id": self.root.id,
            "max_depth": self._calculate_max_depth(),
            "nodes_by_type": self._count_by_type(),
        }

    def _calculate_max_depth(self) -> int:
        def depth(node: FractalNode) -> int:
            if not node.children:
                return 1
            return 1 + max(depth(c) for c in node.children.values())
        return depth(self.root)

    def _count_by_type(self) -> Dict[str, int]:
        counts = {}
        for node in self.get_all_nodes():
            t = node.config.node_type
            counts[t] = counts.get(t, 0) + 1
        return counts