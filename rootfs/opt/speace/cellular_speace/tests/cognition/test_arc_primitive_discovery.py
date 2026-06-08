import json
import pytest

from speace_core.cellular_brain.cognition.arc_primitive_discovery_engine import (
    ARCPrimitiveDiscoveryEngine,
    MANUAL_ARC_PRIMITIVES,
)


class TestARCPrimitiveDiscoveryEngine:
    def test_manual_primitive_registry_length(self):
        assert len(MANUAL_ARC_PRIMITIVES) >= 15

    def test_gravity_primitive(self):
        fn = MANUAL_ARC_PRIMITIVES["gravity"]
        grid = [
            [1, 0, 2],
            [0, 0, 0],
            [0, 0, 0],
        ]
        out = fn(grid, {})
        assert out is not None
        assert out[2] == [1, 0, 2]

    def test_remove_noise_primitive(self):
        fn = MANUAL_ARC_PRIMITIVES["remove_noise"]
        grid = [
            [0, 1, 0],
            [0, 0, 0],
            [0, 2, 0],
        ]
        out = fn(grid, {})
        # isolated pixels removed
        assert out == [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

    def test_trim_background(self):
        fn = MANUAL_ARC_PRIMITIVES["trim_background"]
        grid = [
            [0, 0, 0, 0],
            [0, 1, 2, 0],
            [0, 0, 0, 0],
        ]
        out = fn(grid, {})
        assert out == [[1, 2]]

    def test_fill_background(self):
        fn = MANUAL_ARC_PRIMITIVES["fill_background"]
        grid = [
            [0, 1],
            [2, 0],
        ]
        out = fn(grid, {"color": 9, "background": 0})
        assert out == [[9, 1], [2, 9]]

    def test_invert_colors(self):
        fn = MANUAL_ARC_PRIMITIVES["invert_colors"]
        grid = [
            [1, 2],
            [0, 3],
        ]
        out = fn(grid, {"max_color": 9})
        assert out == [[8, 7], [0, 6]]

    def test_detect_enclosed(self):
        fn = MANUAL_ARC_PRIMITIVES["detect_enclosed"]
        grid = [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
        ]
        out = fn(grid, {"fill_color": 2})
        assert out[1][1] == 2

    def test_compress(self):
        fn = MANUAL_ARC_PRIMITIVES["compress"]
        grid = [
            [0, 0, 0],
            [0, 1, 0],
            [0, 0, 0],
        ]
        out = fn(grid, {})
        assert out == [[1]]

    def test_swap_colors(self):
        fn = MANUAL_ARC_PRIMITIVES["swap_colors"]
        grid = [
            [1, 2],
            [2, 1],
        ]
        out = fn(grid, {"color_a": 1, "color_b": 2})
        assert out == [[2, 1], [1, 2]]

    def test_make_symmetric(self):
        fn = MANUAL_ARC_PRIMITIVES["make_symmetric"]
        grid = [
            [1, 0, 0],
            [0, 0, 0],
        ]
        out = fn(grid, {"axis": "horizontal"})
        assert out[0][2] == 1

    def test_border(self):
        fn = MANUAL_ARC_PRIMITIVES["border"]
        grid = [[1, 2]]
        out = fn(grid, {"color": 9})
        assert len(out) == 3
        assert out[0] == [9, 9, 9, 9]

    def test_discovery_build_enriched_registry(self):
        existing = {"rotate_90": lambda g, p: None}
        engine = ARCPrimitiveDiscoveryEngine(existing_primitives=existing)
        merged = engine.build_enriched_registry()
        assert "rotate_90" in merged
        assert "gravity" in merged
        assert len(merged) > len(MANUAL_ARC_PRIMITIVES)

    def test_discovery_save_manifest(self, tmp_path):
        p = tmp_path / "manifest.json"
        ARCPrimitiveDiscoveryEngine.save_manual_primitives(str(p))
        data = json.loads(p.read_text())
        assert data["source"] == "manual_curation"
        assert len(data["primitive_names"]) >= 15
