import math
from typing import Dict, Optional


class ActiveInferenceEngine:
    """
    Discrete-state active inference engine.

    Maintains beliefs over states, registers actions with outcome distributions,
    and selects actions that minimize expected free energy.
    """

    def __init__(self):
        self.priors: Dict[str, float] = {}
        self.beliefs: Dict[str, float] = {}
        self.actions: Dict[str, Dict[str, float]] = {}

    def register_state(self, state_id: str, prior_probability: float) -> None:
        """Register a state with a prior belief."""
        if prior_probability < 0 or prior_probability > 1:
            raise ValueError("prior_probability must be in [0, 1]")
        self.priors[state_id] = prior_probability
        self.beliefs[state_id] = prior_probability

    def register_action(
        self, action_id: str, outcome_distribution: Dict[str, float]
    ) -> None:
        """Register an action and its expected outcome distribution over states."""
        total = sum(outcome_distribution.values())
        if not math.isclose(total, 1.0, rel_tol=1e-6):
            raise ValueError("outcome_distribution probabilities must sum to 1.0")
        self.actions[action_id] = dict(outcome_distribution)

    def observe(self, state_id: str, likelihood: float) -> None:
        """
        Bayesian update of beliefs given a likelihood for a specific state.
        Assumes uninformative likelihood (1.0) for all other states.
        """
        if state_id not in self.beliefs:
            raise ValueError(f"State '{state_id}' not registered")
        if likelihood < 0:
            raise ValueError("likelihood must be non-negative")

        self.beliefs[state_id] *= likelihood
        self._normalize_beliefs()

    def expected_free_energy(self, action_id: str) -> float:
        """
        Compute the Expected Free Energy (EFE) for an action.

        EFE = Expected surprise (entropy of outcome distribution)
              - Epistemic value (KL divergence between outcome distribution
                and current beliefs)

        Minimizing EFE therefore minimises surprise while maximising
        information gain.
        """
        if action_id not in self.actions:
            raise ValueError(f"Action '{action_id}' not registered")

        self._normalize_beliefs()
        dist = self.actions[action_id]

        # Expected surprise = entropy of outcome distribution
        expected_surprise = 0.0
        for prob in dist.values():
            if prob > 0:
                expected_surprise -= prob * math.log(prob)

        # Epistemic value (information gain) = KL(P(s|a) || Q(s))
        epistemic_value = 0.0
        for state_id, prob in dist.items():
            q = self.beliefs.get(state_id, 1e-12)
            if prob > 0 and q > 0:
                epistemic_value += prob * math.log(prob / q)
            elif prob > 0:
                # belief is zero but outcome prob is non-zero -> large info gain
                epistemic_value += prob * 20.0

        return expected_surprise - epistemic_value

    def select_action(self) -> Optional[str]:
        """Select the action with the lowest expected free energy."""
        if not self.actions:
            return None

        self._normalize_beliefs()
        best_action = None
        best_efe = float("inf")
        for action_id in self.actions:
            efe = self.expected_free_energy(action_id)
            if efe < best_efe:
                best_efe = efe
                best_action = action_id
        return best_action

    def step(self) -> Optional[str]:
        """
        Update beliefs to the expected outcome distribution of the best action
        and return that action.
        """
        action_id = self.select_action()
        if action_id is not None:
            dist = self.actions[action_id]
            for state_id in self.beliefs:
                self.beliefs[state_id] = dist.get(state_id, 0.0)
            self._normalize_beliefs()
        return action_id

    def _normalize_beliefs(self) -> None:
        total = sum(self.beliefs.values())
        if total == 0:
            # Reset to priors if everything collapses
            self.beliefs = dict(self.priors)
            total = sum(self.beliefs.values())
        if total > 0:
            for state_id in self.beliefs:
                self.beliefs[state_id] /= total
