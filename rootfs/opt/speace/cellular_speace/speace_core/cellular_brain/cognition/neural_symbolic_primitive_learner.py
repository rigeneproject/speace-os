"""Neural-Symbolic Primitive Learner (NSPL).

A tiny numpy-based MLP that learns to classify local 3×3 patch transformations.
Provides a soft prior for the symbolic program-induction engine by predicting
which primitive likely generated a local input→output patch.
"""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

Grid = List[List[int]]
PrimitiveFn = Callable[[Grid, Dict[str, Any]], Optional[Grid]]


def _extract_patch(grid: Grid, y: int, x: int, size: int = 3, pad: int = 0) -> Grid:
    """Extract a size×size patch centered at (y, x) with constant padding."""
    half = size // 2
    out: Grid = []
    h, w = len(grid), len(grid[0])
    for dy in range(-half, half + 1):
        row: List[int] = []
        for dx in range(-half, half + 1):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w:
                row.append(grid[ny][nx])
            else:
                row.append(pad)
        out.append(row)
    return out


def _flatten_patch(patch: Grid) -> np.ndarray:
    return np.array([c for row in patch for c in row], dtype=float) / 9.0


class PatchMLP:
    """Minimal MLP: input -> hidden (ReLU) -> softmax.

    Weights stored as numpy arrays; updates via vanilla SGD.
    """

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        # Xavier-like init
        self.W1 = rng.standard_normal((input_dim, hidden_dim)).astype(float) * math.sqrt(2.0 / input_dim)
        self.b1 = np.zeros(hidden_dim, dtype=float)
        self.W2 = rng.standard_normal((hidden_dim, output_dim)).astype(float) * math.sqrt(2.0 / hidden_dim)
        self.b2 = np.zeros(output_dim, dtype=float)
        self._cache: Optional[Tuple[np.ndarray, np.ndarray]] = None

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Return softmax probabilities."""
        z1 = x @ self.W1 + self.b1
        a1 = np.maximum(z1, 0)  # ReLU
        z2 = a1 @ self.W2 + self.b2
        # stable softmax
        e = np.exp(z2 - np.max(z2))
        probs = e / np.sum(e)
        self._cache = (x, a1)
        return probs

    def backward(self, y_true: int, lr: float = 0.01) -> None:
        """Single-example SGD update (y_true is class index)."""
        if self._cache is None:
            raise RuntimeError("forward must be called before backward")
        x, a1 = self._cache
        # Recompute z2 for gradient
        z2 = a1 @ self.W2 + self.b2
        e = np.exp(z2 - np.max(z2))
        probs = e / np.sum(e)

        dz2 = probs.copy()
        dz2[y_true] -= 1.0

        dW2 = np.outer(a1, dz2)
        db2 = dz2
        da1 = self.W2 @ dz2
        dz1 = da1 * (a1 > 0).astype(float)
        dW1 = np.outer(x, dz1)
        db1 = dz1

        self.W2 -= lr * dW2
        self.b2 -= lr * db2
        self.W1 -= lr * dW1
        self.b1 -= lr * db1


class NSPLEngine:
    """Neural-Symbolic Primitive Learner.

    Trains a small MLP on local 3×3 patches to predict which primitive
    transformed the patch.  Used by the symbolic engine as an informed
    hypothesis generator.
    """

    def __init__(
        self,
        primitive_registry: Dict[str, PrimitiveFn],
        patch_size: int = 3,
        hidden_dim: int = 32,
        seed: int = 42,
    ) -> None:
        self.primitive_registry = primitive_registry
        self.patch_size = patch_size
        self.patch_pixels = patch_size * patch_size
        # Class 0 reserved for "unknown"
        self.primitive_names = ["unknown"] + sorted(p for p in primitive_registry.keys())
        self.name_to_idx = {name: i for i, name in enumerate(self.primitive_names)}
        input_dim = self.patch_pixels * 2  # concatenated in + out
        self.mlp = PatchMLP(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            output_dim=len(self.primitive_names),
            seed=seed,
        )
        self._trained = False

    # ------------------------------------------------------------------ #
    # Training data generation
    # ------------------------------------------------------------------ #

    def _try_primitive_on_patch(
        self, patch_in: Grid, patch_out: Grid, name: str, fn: PrimitiveFn
    ) -> bool:
        try:
            result = fn(patch_in, {})
            if result is None:
                return False
            return result == patch_out
        except Exception:
            return False

    def build_training_data(
        self, tasks: List[Dict[str, Any]], max_pairs: int = 200
    ) -> List[Tuple[np.ndarray, int]]:
        """Generate (feature_vector, label_index) tuples from ARC tasks."""
        dataset: List[Tuple[np.ndarray, int]] = []
        pair_count = 0
        for task in tasks:
            if pair_count >= max_pairs:
                break
            for pair in task.get("train", []):
                if pair_count >= max_pairs:
                    break
                inp = pair["input"]
                out = pair["output"]
                if not inp or not out:
                    continue
                h = min(len(inp), len(out))
                w = min(len(inp[0]), len(out[0])) if h > 0 else 0
                if h == 0 or w == 0:
                    continue
                for y in range(h):
                    for x in range(w):
                        p_in = _extract_patch(inp, y, x, self.patch_size)
                        p_out = _extract_patch(out, y, x, self.patch_size)
                        # Try every primitive; pick first that matches
                        label = self.name_to_idx["unknown"]
                        for name, fn in self.primitive_registry.items():
                            if self._try_primitive_on_patch(p_in, p_out, name, fn):
                                label = self.name_to_idx[name]
                                break
                        feat = np.concatenate([_flatten_patch(p_in), _flatten_patch(p_out)])
                        dataset.append((feat, label))
                pair_count += 1
        return dataset

    def train(self, dataset: List[Tuple[np.ndarray, int]], epochs: int = 5, lr: float = 0.05) -> None:
        """Train the MLP with vanilla SGD on local patches."""
        if not dataset:
            return
        rng = np.random.default_rng(42)
        for _ in range(epochs):
            rng.shuffle(dataset)
            for feat, label in dataset:
                self.mlp.forward(feat)
                self.mlp.backward(label, lr=lr)
        self._trained = True

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #

    def predict_primitive(
        self, patch_in: Grid, patch_out: Grid, top_k: int = 3
    ) -> List[Tuple[str, float]]:
        """Return top-k (primitive_name, confidence) for a local patch pair."""
        feat = np.concatenate([_flatten_patch(patch_in), _flatten_patch(patch_out)])
        probs = self.mlp.forward(feat)
        # Sort by descending probability
        idxs = np.argsort(-probs)
        return [(self.primitive_names[i], float(probs[i])) for i in idxs[:top_k]]

    def predict_from_grids(
        self,
        grid_in: Grid,
        grid_out: Grid,
        top_k: int = 3,
        sample_positions: int = 5,
    ) -> List[Tuple[str, float]]:
        """Aggregate patch predictions across random positions into a global vote."""
        h = min(len(grid_in), len(grid_out))
        w = min(len(grid_in[0]), len(grid_out[0])) if h > 0 else 0
        if h == 0 or w == 0:
            return []
        rng = np.random.default_rng(123)
        scores: Dict[str, float] = {}
        positions = [
            (rng.integers(0, h), rng.integers(0, w)) for _ in range(sample_positions)
        ]
        for y, x in positions:
            p_in = _extract_patch(grid_in, y, x, self.patch_size)
            p_out = _extract_patch(grid_out, y, x, self.patch_size)
            for name, conf in self.predict_primitive(p_in, p_out, top_k=top_k):
                scores[name] = scores.get(name, 0.0) + conf
        # Normalize
        total = sum(scores.values())
        if total > 0:
            for k in scores:
                scores[k] /= total
        return sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]

    # ------------------------------------------------------------------ #
    # Checkpointing
    # ------------------------------------------------------------------ #

    def save(self, path: str) -> None:
        """Persist weights and metadata to disk."""
        import json
        meta = {
            "primitive_names": self.primitive_names,
            "patch_size": self.patch_size,
            "trained": self._trained,
        }
        np.savez(
            path,
            W1=self.mlp.W1,
            b1=self.mlp.b1,
            W2=self.mlp.W2,
            b2=self.mlp.b2,
            meta=json.dumps(meta),
        )

    def load(self, path: str) -> None:
        """Restore weights and metadata from disk."""
        import json
        data = np.load(path, allow_pickle=False)
        self.mlp.W1 = data["W1"]
        self.mlp.b1 = data["b1"]
        self.mlp.W2 = data["W2"]
        self.mlp.b2 = data["b2"]
        meta = json.loads(str(data["meta"]))
        self.primitive_names = meta["primitive_names"]
        self.name_to_idx = {name: i for i, name in enumerate(self.primitive_names)}
        self.patch_size = meta["patch_size"]
        self._trained = meta["trained"]
