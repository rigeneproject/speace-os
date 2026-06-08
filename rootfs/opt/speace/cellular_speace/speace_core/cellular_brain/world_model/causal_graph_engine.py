import random
from typing import Any, Dict, List, Optional, Set, Tuple

from speace_core.cellular_brain.world_model.world_model_models import (
    CausalLink,
    WorldEntity,
    WorldModelSnapshot,
    WorldScenario,
    WorldZone,
    CausalSimulationResult,
)


class CausalGraphEngine:
    """Builds internal causal graphs, detects chains and contradictions. Purely simulative."""

    def __init__(self, seed: int = 42):
        self._seed = seed
        self._rng = random.Random(seed)

    def build_causal_graph(self, snapshot: WorldModelSnapshot) -> List[CausalLink]:
        links: List[CausalLink] = []
        entities = snapshot.entities
        for i, src in enumerate(entities):
            for tgt in entities[i + 1 :]:
                if src.entity_type == tgt.entity_type and self._rng.random() < 0.3:
                    continue
                strength = self._rng.uniform(0.1, 0.9)
                links.append(
                    CausalLink(
                        link_id=f"link_{src.entity_id}_{tgt.entity_id}",
                        source_entity_id=src.entity_id,
                        target_entity_id=tgt.entity_id,
                        relation_type="influences",
                        strength=strength,
                        confidence=0.7,
                        delay_ticks=self._rng.randint(0, 3),
                    )
                )
        return links

    def evaluate_causal_links(self, snapshot: WorldModelSnapshot) -> List[CausalLink]:
        return snapshot.causal_links or self.build_causal_graph(snapshot)

    def detect_causal_chains(self, links: List[CausalLink]) -> List[List[str]]:
        """Find multi-step causal chains (A -> B -> C)."""
        adjacency: Dict[str, List[str]] = {}
        for link in links:
            adjacency.setdefault(link.source_entity_id, []).append(link.target_entity_id)

        chains: List[List[str]] = []
        visited_paths: Set[Tuple[str, ...]] = set()

        def dfs(node: str, path: List[str]):
            if len(path) >= 3:
                chain_tuple = tuple(path)
                if chain_tuple not in visited_paths:
                    visited_paths.add(chain_tuple)
                    chains.append(list(path))
                return
            for nxt in adjacency.get(node, []):
                if nxt not in path:
                    dfs(nxt, path + [nxt])

        for start in adjacency:
            dfs(start, [start])
        return chains

    def detect_contradictions(self, snapshot: WorldModelSnapshot) -> List[Dict[str, Any]]:
        contradictions: List[Dict[str, Any]] = []
        state_map: Dict[str, Dict[str, Any]] = {}
        for e in snapshot.entities:
            state_map[e.entity_id] = e.state

        for i, e1 in enumerate(snapshot.entities):
            for e2 in snapshot.entities[i + 1 :]:
                for key in set(e1.state.keys()) & set(e2.state.keys()):
                    v1 = e1.state[key]
                    v2 = e2.state[key]
                    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                        if abs(v1 - v2) > 0.5:
                            contradictions.append({
                                "entity_a": e1.entity_id,
                                "entity_b": e2.entity_id,
                                "key": key,
                                "value_a": v1,
                                "value_b": v2,
                            })
                    elif v1 != v2 and key != "name":
                        contradictions.append({
                            "entity_a": e1.entity_id,
                            "entity_b": e2.entity_id,
                            "key": key,
                            "value_a": v1,
                            "value_b": v2,
                        })
        return contradictions

    def simulate_causal_step(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
        tick: int,
    ) -> WorldModelSnapshot:
        """Advance one tick in causal simulation. Read-only transformation."""
        new_entities = []
        for e in snapshot.entities:
            new_state = dict(e.state)
            for p in scenario.perturbations:
                if p.get("target_entity_id") == e.entity_id:
                    if p.get("type") == "safety_hazard":
                        new_state["safety_pressure"] = new_state.get("safety_pressure", 0.0) + p.get("delta_safety", 0.0)
                if p.get("type") == "state_conflict" and p.get("entity_a") == e.entity_id:
                    new_state[p.get("conflict_key", "status")] = p.get("value_a", "active")
                if p.get("type") == "injected_uncertainty":
                    new_state["uncertainty"] = new_state.get("uncertainty", 0.0) + p.get("level", 0.0) * 0.1
            new_entities.append(
                WorldEntity(
                    entity_id=e.entity_id,
                    entity_type=e.entity_type,
                    name=e.name,
                    state=new_state,
                    confidence=e.confidence * 0.95,
                    uncertainty=min(1.0, e.uncertainty + 0.02),
                    safety_relevance=e.safety_relevance,
                    metadata=e.metadata,
                )
            )
        new_zones = []
        for z in snapshot.zones:
            new_zone = WorldZone(
                zone_id=z.zone_id,
                name=z.name,
                entities=list(z.entities),
                environmental_pressure=z.environmental_pressure,
                infrastructure_pressure=z.infrastructure_pressure,
                energy_pressure=z.energy_pressure,
                safety_pressure=z.safety_pressure,
                uncertainty_score=z.uncertainty_score,
                metadata=z.metadata,
            )
            for p in scenario.perturbations:
                if p.get("target_zone_id") == z.zone_id:
                    if p.get("type") == "pressure_spike":
                        new_zone.infrastructure_pressure = min(1.0, new_zone.infrastructure_pressure + p.get("delta_infrastructure", 0.0))
                        new_zone.energy_pressure = min(1.0, new_zone.energy_pressure + p.get("delta_energy", 0.0))
                    elif p.get("type") == "energy_scarcity":
                        new_zone.energy_pressure = min(1.0, new_zone.energy_pressure - p.get("delta_energy", 0.0))
            new_zones.append(new_zone)

        return WorldModelSnapshot(
            snapshot_id=f"{snapshot.snapshot_id}_tick{tick}",
            timestamp=snapshot.timestamp,
            entities=new_entities,
            zones=new_zones,
            constraints=snapshot.constraints,
            causal_links=snapshot.causal_links,
            global_uncertainty_score=snapshot.global_uncertainty_score,
            global_coherence_score=snapshot.global_coherence_score,
            global_risk_score=snapshot.global_risk_score,
            metadata={**snapshot.metadata, "simulated_tick": tick},
        )

    def run_causal_simulation(
        self,
        snapshot: WorldModelSnapshot,
        scenario: WorldScenario,
    ) -> CausalSimulationResult:
        current = snapshot
        chains: List[List[str]] = []
        contradictions: List[Dict[str, Any]] = []
        violations = 0
        max_risk = snapshot.global_risk_score
        min_coherence = snapshot.global_coherence_score
        max_energy_pressure = max((z.energy_pressure for z in snapshot.zones), default=0.0)
        max_safety_pressure = max((z.safety_pressure for z in snapshot.zones), default=0.0)

        for tick in range(1, scenario.horizon_ticks + 1):
            current = self.simulate_causal_step(current, scenario, tick)
            links = self.evaluate_causal_links(current)
            tick_chains = self.detect_causal_chains(links)
            chains.extend(tick_chains)
            tick_contradictions = self.detect_contradictions(current)
            contradictions.extend(tick_contradictions)
            for c in current.constraints:
                if c.hard_constraint and c.severity > 0.8:
                    violations += 1
            max_risk = max(max_risk, current.global_risk_score)
            min_coherence = min(min_coherence, current.global_coherence_score)
            max_energy_pressure = max(max_energy_pressure, max((z.energy_pressure for z in current.zones), default=0.0))
            max_safety_pressure = max(max_safety_pressure, max((z.safety_pressure for z in current.zones), default=0.0))

        safe_to_publish = True
        if max_risk > 0.7 or violations > 0:
            safe_to_publish = False

        return CausalSimulationResult(
            scenario_id=scenario.scenario_id,
            ticks_simulated=scenario.horizon_ticks,
            causal_chains_detected=len(chains),
            contradictions_detected=len(contradictions),
            constraint_violations_detected=violations,
            predicted_risk_score=max_risk,
            predicted_coherence_score=min_coherence,
            predicted_energy_pressure=max_energy_pressure,
            predicted_safety_pressure=max_safety_pressure,
            safe_to_publish_read_only=safe_to_publish,
            metadata={"chains": [[c[0], c[-1], len(c)] for c in chains], "contradiction_count": len(contradictions)},
        )
