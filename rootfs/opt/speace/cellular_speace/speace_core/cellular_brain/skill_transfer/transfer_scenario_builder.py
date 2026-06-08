import random
from typing import List

from speace_core.cellular_brain.skill_transfer.skill_transfer_models import (
    TransferScenario,
)


class TransferScenarioBuilder:
    """Builds simulated transfer scenarios."""

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def build_default_scenarios(self) -> List[TransferScenario]:
        domains = [
            ("observation", "prediction"),
            ("prediction", "causal_reasoning"),
            ("causal_reasoning", "planning"),
            ("planning", "action_simulation"),
            ("memory_consolidation", "memory_reuse"),
            ("error_correction", "regression_detection"),
            ("semantic_grounding", "safe_imitation"),
            ("safe_imitation", "policy_conflict_resolution"),
        ]
        scenarios: List[TransferScenario] = []
        for i, (src, tgt) in enumerate(domains):
            scenarios.append(
                TransferScenario(
                    scenario_id=f"scenario_{i}",
                    name=f"{src}_to_{tgt}",
                    description=f"Transfer from {src} to {tgt}",
                    source_domain=src,
                    target_domain=tgt,
                    novelty_score=self._rng.uniform(0.2, 0.8),
                    difficulty_score=self._rng.uniform(0.2, 0.8),
                    risk_score=self._rng.uniform(0.1, 0.5),
                    requires_external_action=False,
                    simulated_only=True,
                )
            )
        return scenarios

    def build_novel_scenario(self, source_domain: str, target_domain: str) -> TransferScenario:
        return TransferScenario(
            scenario_id=f"scenario_{source_domain}_{target_domain}_{self._rng.randint(0, 9999)}",
            name=f"{source_domain}_to_{target_domain}",
            description=f"Novel transfer from {source_domain} to {target_domain}",
            source_domain=source_domain,
            target_domain=target_domain,
            novelty_score=self._rng.uniform(0.5, 1.0),
            difficulty_score=self._rng.uniform(0.3, 0.9),
            risk_score=self._rng.uniform(0.1, 0.6),
            requires_external_action=False,
            simulated_only=True,
        )
