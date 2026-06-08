"""CognitiveSkillRegistry — T132: registry of evolvable cognitive skills.

Skills are immutable templates that can be cloned, mutated in sandbox,
and evaluated for fitness. Only approved variants are promoted.

T132 Enhanced:
- Typed computational graph (SkillGraph) where scripts/skills/algorithms
  are functional neurons with strict input/output schemas.
- Structural plasticity: add/remove nodes and edges, rewire graph.
- Validation system: cycle detection, orphaned nodes, schema compatibility.
- Execution contracts per neuron.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field, ValidationError


class ExecutionContract(BaseModel):
    """Execution contract for a functional neuron (script, skill, algorithm)."""

    language: str = "python"
    entrypoint: str = ""
    timeout_ms: int = 1000
    sandboxed: bool = True
    required_resources: List[str] = Field(default_factory=list)
    side_effects: List[str] = Field(default_factory=list)


class FunctionalNode(BaseModel):
    """A functional neuron in the typed computational graph."""

    node_id: str
    node_type: str  # e.g. thought, metacognitive, language, perception, action, memory, integration
    name: str
    description: str = ""
    input_schema: Dict[str, str] = Field(default_factory=dict)
    output_schema: Dict[str, str] = Field(default_factory=dict)
    contract: ExecutionContract = Field(default_factory=ExecutionContract)
    code_ref: str = ""  # reference to template, script path, or skill_id
    params: Dict[str, Any] = Field(default_factory=dict)
    position: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])


class GraphEdge(BaseModel):
    """Typed connection between functional neurons."""

    edge_id: str
    source_id: str
    target_id: str
    edge_type: str = "data"  # data, control, feedback, latent
    weight: float = 1.0
    latency_ms: int = 0


class SkillGraph(BaseModel):
    """Typed computational graph representing a cognitive skill as a neural circuit."""

    graph_id: str
    nodes: Dict[str, FunctionalNode] = Field(default_factory=dict)
    edges: List[GraphEdge] = Field(default_factory=list)
    version: str = "1.0.0"
    plasticity_score: float = 0.0


class SkillValidationReport(BaseModel):
    """Result of validating a skill graph."""

    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0
    cycles_detected: bool = False
    orphaned_nodes: List[str] = Field(default_factory=list)
    schema_mismatches: List[str] = Field(default_factory=list)


class CognitiveSkill(BaseModel):
    skill_id: str
    skill_type: str  # "thought", "metacognitive", "language"
    name: str
    version: str = "1.0.0"
    params: Dict[str, Any] = Field(default_factory=dict)
    template: str = ""  # e.g. reasoning template, narrative template
    fitness_score: float = 0.0
    origin: str = "human"  # human | evolved | hybrid
    parent_id: str = ""
    created_at: float = 0.0
    approved: bool = False
    graph: Optional[SkillGraph] = None
    interface_hash: str = ""  # hash of the overall execution contract


class CognitiveSkillRegistry:
    """Manages skill templates and their evolved variants.

    T132 enhancements:
    - Each skill may carry a typed computational graph (SkillGraph).
    - Structural plasticity allows mutating the graph topology.
    - Validation checks topological integrity and schema compatibility.
    """

    def __init__(self, data_root: str = "data/cognitive_evolution") -> None:
        self._data_root = Path(data_root)
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, CognitiveSkill] = {}
        self._load()

    # ------------------------------------------------------------------ #
    # CRUD
    # ------------------------------------------------------------------ #

    def register(self, skill: CognitiveSkill) -> None:
        self._skills[skill.skill_id] = skill
        self._persist()

    def get(self, skill_id: str) -> Optional[CognitiveSkill]:
        return self._skills.get(skill_id)

    def list_skills(
        self,
        skill_type: Optional[str] = None,
        approved_only: bool = False,
    ) -> List[CognitiveSkill]:
        results = list(self._skills.values())
        if skill_type:
            results = [s for s in results if s.skill_type == skill_type]
        if approved_only:
            results = [s for s in results if s.approved]
        return results

    def clone_for_sandbox(
        self,
        parent_id: str,
        mutation: Dict[str, Any],
    ) -> Optional[CognitiveSkill]:
        """Create a sandbox clone of an approved skill with a mutation."""
        parent = self._skills.get(parent_id)
        if parent is None or not parent.approved:
            return None
        new_params = dict(parent.params)
        new_params.update(mutation.get("params", {}))
        new_graph = None
        if parent.graph is not None:
            graph_dict = parent.graph.model_dump(mode="json")
            new_graph = SkillGraph(**graph_dict)
        return CognitiveSkill(
            skill_id=f"SB-{uuid.uuid4().hex[:12]}",
            skill_type=parent.skill_type,
            name=f"{parent.name}_variant",
            version=parent.version,
            params=new_params,
            template=mutation.get("template", parent.template),
            origin="evolved",
            parent_id=parent_id,
            created_at=time.time(),
            approved=False,
            graph=new_graph,
        )

    def approve_variant(self, skill_id: str) -> bool:
        skill = self._skills.get(skill_id)
        if skill is None:
            return False
        skill.approved = True
        self._persist()
        return True

    # ------------------------------------------------------------------ #
    # Graph access
    # ------------------------------------------------------------------ #

    def get_graph(self, skill_id: str) -> Optional[SkillGraph]:
        skill = self._skills.get(skill_id)
        if skill is None:
            return None
        return skill.graph

    def get_functional_neurons(self, skill_id: str) -> List[FunctionalNode]:
        graph = self.get_graph(skill_id)
        if graph is None:
            return []
        return list(graph.nodes.values())

    def get_execution_contracts(self, skill_id: str) -> List[ExecutionContract]:
        return [n.contract for n in self.get_functional_neurons(skill_id)]

    # ------------------------------------------------------------------ #
    # Structural plasticity (graph mutation)
    # ------------------------------------------------------------------ #

    def add_graph_node(self, skill_id: str, node: FunctionalNode) -> bool:
        skill = self._skills.get(skill_id)
        if skill is None or skill.graph is None:
            return False
        skill.graph.nodes[node.node_id] = node
        skill.graph.plasticity_score += 1.0
        self._persist()
        return True

    def remove_graph_node(self, skill_id: str, node_id: str) -> bool:
        skill = self._skills.get(skill_id)
        if skill is None or skill.graph is None:
            return False
        if node_id not in skill.graph.nodes:
            return False
        del skill.graph.nodes[node_id]
        skill.graph.edges = [
            e for e in skill.graph.edges if e.source_id != node_id and e.target_id != node_id
        ]
        skill.graph.plasticity_score += 1.0
        self._persist()
        return True

    def add_graph_edge(self, skill_id: str, edge: GraphEdge) -> bool:
        skill = self._skills.get(skill_id)
        if skill is None or skill.graph is None:
            return False
        if edge.source_id not in skill.graph.nodes or edge.target_id not in skill.graph.nodes:
            return False
        skill.graph.edges.append(edge)
        skill.graph.plasticity_score += 0.5
        self._persist()
        return True

    def remove_graph_edge(self, skill_id: str, edge_id: str) -> bool:
        skill = self._skills.get(skill_id)
        if skill is None or skill.graph is None:
            return False
        original_len = len(skill.graph.edges)
        skill.graph.edges = [e for e in skill.graph.edges if e.edge_id != edge_id]
        if len(skill.graph.edges) < original_len:
            skill.graph.plasticity_score += 0.5
            self._persist()
            return True
        return False

    def mutate_graph(
        self,
        skill_id: str,
        mutation: Dict[str, Any],
    ) -> Optional[CognitiveSkill]:
        """Apply a structural mutation to a skill graph and return a sandbox clone.

        mutation keys:
        - add_nodes: List[FunctionalNode]
        - remove_nodes: List[str]
        - add_edges: List[GraphEdge]
        - remove_edges: List[str]
        - rewire: List[Dict[str, str]]  # [{"edge_id": "...", "new_target_id": "..."}]
        """
        parent = self._skills.get(skill_id)
        if parent is None or not parent.approved:
            return None
        if parent.graph is None:
            return None

        graph_dict = parent.graph.model_dump(mode="json")
        new_graph = SkillGraph(**graph_dict)

        for node in mutation.get("add_nodes", []):
            if isinstance(node, dict):
                node = FunctionalNode(**node)
            new_graph.nodes[node.node_id] = node
            new_graph.plasticity_score += 1.0

        for node_id in mutation.get("remove_nodes", []):
            if node_id in new_graph.nodes:
                del new_graph.nodes[node_id]
                new_graph.edges = [
                    e for e in new_graph.edges if e.source_id != node_id and e.target_id != node_id
                ]
                new_graph.plasticity_score += 1.0

        for edge in mutation.get("add_edges", []):
            if isinstance(edge, dict):
                edge = GraphEdge(**edge)
            if edge.source_id in new_graph.nodes and edge.target_id in new_graph.nodes:
                new_graph.edges.append(edge)
                new_graph.plasticity_score += 0.5

        for edge_id in mutation.get("remove_edges", []):
            original_len = len(new_graph.edges)
            new_graph.edges = [e for e in new_graph.edges if e.edge_id != edge_id]
            if len(new_graph.edges) < original_len:
                new_graph.plasticity_score += 0.5

        for rewire in mutation.get("rewire", []):
            edge_id = rewire.get("edge_id")
            new_target = rewire.get("new_target_id")
            for e in new_graph.edges:
                if e.edge_id == edge_id and new_target in new_graph.nodes:
                    e.target_id = new_target
                    new_graph.plasticity_score += 0.5
                    break

        return CognitiveSkill(
            skill_id=f"SB-{uuid.uuid4().hex[:12]}",
            skill_type=parent.skill_type,
            name=f"{parent.name}_graph_variant",
            version=parent.version,
            params=dict(parent.params),
            template=parent.template,
            origin="evolved",
            parent_id=skill_id,
            created_at=time.time(),
            approved=False,
            graph=new_graph,
        )

    # ------------------------------------------------------------------ #
    # Validation system
    # ------------------------------------------------------------------ #

    def validate_skill(self, skill_id: str) -> SkillValidationReport:
        skill = self._skills.get(skill_id)
        if skill is None:
            return SkillValidationReport(valid=False, errors=["Skill not found"])
        if skill.graph is None:
            return SkillValidationReport(
                valid=True,
                warnings=["Skill has no computational graph"],
                node_count=0,
                edge_count=0,
            )
        return self._validate_graph(skill.graph)

    @staticmethod
    def _validate_graph(graph: SkillGraph) -> SkillValidationReport:
        errors: List[str] = []
        warnings: List[str] = []
        node_count = len(graph.nodes)
        edge_count = len(graph.edges)

        if node_count == 0:
            return SkillValidationReport(
                valid=False,
                errors=["Graph has no nodes"],
                node_count=0,
                edge_count=edge_count,
            )

        # Build adjacency list for data/control edges
        adjacency: Dict[str, List[str]] = {n: [] for n in graph.nodes}
        incoming: Dict[str, List[str]] = {n: [] for n in graph.nodes}
        for edge in graph.edges:
            if edge.source_id in adjacency and edge.target_id in adjacency:
                if edge.edge_type in ("data", "control"):
                    adjacency[edge.source_id].append(edge.target_id)
                    incoming[edge.target_id].append(edge.source_id)

        # Cycle detection (DFS)
        cycles_detected = False
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def _dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)
            for neighbour in adjacency.get(node_id, []):
                if neighbour not in visited:
                    if _dfs(neighbour):
                        return True
                elif neighbour in rec_stack:
                    return True
            rec_stack.remove(node_id)
            return False

        for node_id in graph.nodes:
            if node_id not in visited:
                if _dfs(node_id):
                    cycles_detected = True
                    errors.append("Cycle detected in graph")
                    break

        # Orphaned nodes
        orphaned: List[str] = []
        input_types = {"perception", "input", "sensor"}
        output_types = {"action", "output", "actuator"}
        for node_id, node in graph.nodes.items():
            has_incoming = len(incoming.get(node_id, [])) > 0
            has_outgoing = len(adjacency.get(node_id, [])) > 0
            if not has_incoming and node.node_type not in input_types:
                orphaned.append(node_id)
            if not has_outgoing and node.node_type not in output_types:
                orphaned.append(node_id)
        if orphaned:
            warnings.append(f"Orphaned nodes: {list(set(orphaned))}")

        # Schema compatibility
        schema_mismatches: List[str] = []
        for edge in graph.edges:
            if edge.edge_type != "data":
                continue
            source = graph.nodes.get(edge.source_id)
            target = graph.nodes.get(edge.target_id)
            if source is None or target is None:
                continue
            out_keys = set(source.output_schema.keys())
            in_keys = set(target.input_schema.keys())
            if "*" in out_keys or "*" in in_keys:
                continue
            if not out_keys & in_keys:
                schema_mismatches.append(
                    f"Edge {edge.edge_id}: {edge.source_id} -> {edge.target_id} has no matching schema keys"
                )
        if schema_mismatches:
            warnings.extend(schema_mismatches)

        valid = not errors
        return SkillValidationReport(
            valid=valid,
            errors=errors,
            warnings=warnings,
            node_count=node_count,
            edge_count=edge_count,
            cycles_detected=cycles_detected,
            orphaned_nodes=list(set(orphaned)),
            schema_mismatches=schema_mismatches,
        )

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _persist(self) -> None:
        try:
            data = [s.model_dump(mode="json") for s in self._skills.values()]
            path = self._data_root / "skills.json"
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load(self) -> None:
        path = self._data_root / "skills.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for item in data:
                try:
                    skill = CognitiveSkill(**item)
                    self._skills[skill.skill_id] = skill
                except ValidationError:
                    continue
        except (json.JSONDecodeError, TypeError):
            pass
