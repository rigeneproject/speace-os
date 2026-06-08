from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class SemanticAssembly(BaseModel):
    """Decoded neural assembly representing token comprehension."""

    tokens: List[str] = Field(default_factory=list)
    activation_vector: List[float] = Field(default_factory=list)
    dominant_concept: str = ""
    coherence: float = 0.0


class DigitalWernickeArea:
    """Language comprehension area modelled after Wernicke's area.

    Receives symbolic tokens, decodes them into semantic assemblies, and
    maintains a running activation map for downstream cortical areas.
    """

    def __init__(
        self,
        vocab: Optional[Dict[str, List[float]]] = None,
        coherence_threshold: float = 0.3,
        decay_rate: float = 0.05,
    ):
        self.vocab = vocab or {}
        self.coherence_threshold = coherence_threshold
        self.decay_rate = decay_rate
        self._token_buffer: List[str] = []
        self._semantic_map: Dict[str, float] = {}
        self._assembly_history: List[SemanticAssembly] = []

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def receive_tokens(self, tokens: List[str]) -> None:
        """Ingest a stream of symbolic tokens into the comprehension buffer."""
        self._token_buffer.extend(tokens)
        for token in tokens:
            # If token is in vocabulary, boost its semantic activation
            if token in self.vocab:
                vector = self.vocab[token]
                self._semantic_map[token] = max(
                    self._semantic_map.get(token, 0.0),
                    sum(vector) / len(vector) if vector else 0.0,
                )
            else:
                # Unknown token gets a small novelty activation
                self._semantic_map[token] = self._semantic_map.get(token, 0.0) + 0.1

    def decode_to_assembly(self) -> SemanticAssembly:
        """Convert the current token buffer into a semantic assembly.

        Computes a simple activation vector by averaging known embeddings
        and derives a dominant concept from the most active token.
        """
        if not self._token_buffer:
            return SemanticAssembly()

        known_tokens = [t for t in self._token_buffer if t in self.vocab]
        unknown_tokens = [t for t in self._token_buffer if t not in self.vocab]

        if known_tokens:
            # Average embedding vectors
            dim = len(next(iter(self.vocab.values())))
            accum = [0.0] * dim
            for t in known_tokens:
                vec = self.vocab[t]
                for i, v in enumerate(vec):
                    accum[i] += v
            activation_vector = [v / len(known_tokens) for v in accum]
            coherence = sum(activation_vector) / len(activation_vector) if activation_vector else 0.0
        else:
            activation_vector = [0.1] * max(1, len(self.vocab) and len(next(iter(self.vocab.values()))) or 1)
            coherence = 0.0

        dominant = ""
        if known_tokens:
            dominant = max(
                known_tokens,
                key=lambda t: sum(self.vocab[t]) / len(self.vocab[t]),
            )
        elif unknown_tokens:
            dominant = unknown_tokens[0]

        assembly = SemanticAssembly(
            tokens=list(self._token_buffer),
            activation_vector=activation_vector,
            dominant_concept=dominant,
            coherence=coherence,
        )
        self._assembly_history.append(assembly)
        return assembly

    def get_semantic_activation(self) -> Dict[str, float]:
        """Return the current semantic activation map, applying decay."""
        for key in list(self._semantic_map.keys()):
            self._semantic_map[key] = max(0.0, self._semantic_map[key] - self.decay_rate)
            if self._semantic_map[key] <= 0.0:
                del self._semantic_map[key]
        return dict(self._semantic_map)

    def clear_buffer(self) -> None:
        """Empty the token buffer but retain the semantic map."""
        self._token_buffer = []

    def reset(self) -> None:
        """Reset all comprehension state."""
        self._token_buffer = []
        self._semantic_map = {}
        self._assembly_history = []

    @property
    def token_buffer(self) -> List[str]:
        return list(self._token_buffer)

    @property
    def assembly_history(self) -> List[SemanticAssembly]:
        return list(self._assembly_history)

    def known_tokens(self) -> Set[str]:
        """Return the set of tokens recognized in the current vocabulary."""
        return set(self.vocab.keys())
