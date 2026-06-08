import pytest

from speace_core.cellular_brain.cognition.neural_symbolic_primitive_learner import (
    NSPLEngine,
    PatchMLP,
    _extract_patch,
)


class TestPatchMLP:
    def test_forward_shape(self):
        mlp = PatchMLP(input_dim=18, hidden_dim=8, output_dim=5)
        x = [0.1] * 18
        probs = mlp.forward(x)
        assert len(probs) == 5
        assert abs(sum(probs) - 1.0) < 1e-6

    def test_backward_changes_weights(self):
        mlp = PatchMLP(input_dim=18, hidden_dim=8, output_dim=5)
        x = [0.1] * 18
        w2_before = mlp.W2.copy()
        mlp.forward(x)
        mlp.backward(y_true=2, lr=0.1)
        assert not (mlp.W2 == w2_before).all()


class TestNSPLEngine:
    def test_build_training_data(self):
        registry = {
            "identity": lambda g, p: g,
            "invert": lambda g, p: [[9 - c if c != 0 else 0 for c in row] for row in g],
        }
        engine = NSPLEngine(registry, patch_size=3)
        tasks = [
            {
                "train": [
                    {
                        "input": [
                            [0, 0, 0],
                            [0, 1, 0],
                            [0, 0, 0],
                        ],
                        "output": [
                            [0, 0, 0],
                            [0, 1, 0],
                            [0, 0, 0],
                        ],
                    }
                ]
            }
        ]
        dataset = engine.build_training_data(tasks)
        assert len(dataset) > 0
        # At least one patch should match identity
        labels = [label for _, label in dataset]
        assert any(label == engine.name_to_idx["identity"] for label in labels)

    def test_train_and_predict(self):
        registry = {
            "identity": lambda g, p: g,
            "invert": lambda g, p: [[9 - c if c != 0 else 0 for c in row] for row in g],
        }
        engine = NSPLEngine(registry, patch_size=3, hidden_dim=16)
        # Synthetic training data: identity vs invert on simple 3x3 grids
        tasks = [
            {
                "train": [
                    {
                        "input": [[1, 1, 1], [1, 1, 1], [1, 1, 1]],
                        "output": [[1, 1, 1], [1, 1, 1], [1, 1, 1]],
                    },
                    {
                        "input": [[1, 1, 1], [1, 1, 1], [1, 1, 1]],
                        "output": [[8, 8, 8], [8, 8, 8], [8, 8, 8]],
                    },
                ]
            }
        ]
        dataset = engine.build_training_data(tasks)
        engine.train(dataset, epochs=20, lr=0.1)
        # Predict on a clear identity patch
        patch_in = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
        patch_out = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
        top = engine.predict_primitive(patch_in, patch_out, top_k=2)
        names = [n for n, _ in top]
        assert "identity" in names

    def test_predict_from_grids(self):
        registry = {
            "identity": lambda g, p: g,
        }
        engine = NSPLEngine(registry, patch_size=3)
        grid_in = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
        grid_out = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
        top = engine.predict_from_grids(grid_in, grid_out, top_k=1, sample_positions=3)
        assert len(top) > 0
        assert top[0][1] > 0

    def test_extract_patch_padding(self):
        grid = [[1, 2], [3, 4]]
        patch = _extract_patch(grid, 0, 0, size=3, pad=0)
        assert patch == [[0, 0, 0], [0, 1, 2], [0, 3, 4]]
