"""CognitiveMutationSandbox — T132: safe sandbox for skill mutations.

Rules:
- Only parameter-level mutations allowed
- No code execution from mutated templates
- All outputs are validated before returning
- Dangerous patterns are rejected
"""

import copy
import random
from typing import Any, Dict, List, Optional, Set


class CognitiveMutationSandbox:
    """Mutates cognitive skills safely and validates outputs."""

    _DANGEROUS_PATTERNS: Set[str] = {
        "__import__", "eval(", "exec(", "compile(", "os.system",
        "subprocess.call", "subprocess.Popen", "shell=True",
        "import os", "import subprocess", "import sys",
    }

    def __init__(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            random.seed(seed)

    # ------------------------------------------------------------------ #
    # Mutation operators
    # ------------------------------------------------------------------ #

    def mutate_params(
        self,
        params: Dict[str, Any],
        mutation_rate: float = 0.2,
        perturbation: float = 0.1,
    ) -> Dict[str, Any]:
        """Apply Gaussian perturbation to numeric params with given probability."""
        new_params = copy.deepcopy(params)
        for key, value in new_params.items():
            if isinstance(value, (int, float)):
                if random.random() < mutation_rate:
                    delta = random.gauss(0.0, perturbation)
                    new_params[key] = max(0.0, min(1.0, float(value) + delta))
        return new_params

    def mutate_template(
        self,
        template: str,
        replacement_pool: Optional[List[str]] = None,
    ) -> str:
        """Replace a random phrase in the template from a safe pool."""
        if replacement_pool is None:
            return template
        if not template or random.random() < 0.5:
            return template
        # Simple word-level replacement
        words = template.split()
        if len(words) < 2:
            return template
        idx = random.randrange(len(words))
        replacement = random.choice(replacement_pool)
        words[idx] = replacement
        return " ".join(words)

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate_mutation(self, skill_variant: Dict[str, Any]) -> bool:
        """Return False if mutation contains dangerous patterns."""
        template = str(skill_variant.get("template", ""))
        text = template.lower()
        for pattern in self._DANGEROUS_PATTERNS:
            if pattern.lower() in text:
                return False
        # Validate params are plain JSON-serializable types
        params = skill_variant.get("params", {})
        for k, v in params.items():
            if not isinstance(v, (int, float, str, bool, type(None))):
                return False
        return True

    def run_sandbox(
        self,
        skill_variant: Dict[str, Any],
        input_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a skill variant in sandbox and return metrics.

        This is a simulation — real execution would call the actual skill runner.
        """
        if not self.validate_mutation(skill_variant):
            return {
                "success": False,
                "latency_ms": 0.0,
                "stability_delta": -1.0,
                "coherence_delta": -1.0,
                "confidence_delta": -1.0,
                "error": "validation_failed",
            }

        # Simulate execution
        params = skill_variant.get("params", {})
        success_bias = params.get("success_bias", 0.5)
        stability_boost = params.get("stability_boost", 0.0)
        coherence_boost = params.get("coherence_boost", 0.0)
        confidence_boost = params.get("confidence_boost", 0.0)

        success = random.random() < success_bias
        latency = random.uniform(50.0, 500.0)

        return {
            "success": success,
            "latency_ms": latency,
            "stability_delta": stability_boost if success else -0.1,
            "coherence_delta": coherence_boost if success else -0.1,
            "confidence_delta": confidence_boost if success else -0.1,
        }
