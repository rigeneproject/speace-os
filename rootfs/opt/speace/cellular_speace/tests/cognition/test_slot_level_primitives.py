"""Tests for slot-level ARC-AGI primitives."""
import pytest
from speace_core.cellular_brain.cognition.slot_level_primitives import (
    _slot_recolor_by_attr,
    _slot_replicate_by_count,
    _slot_move_to,
    _slot_remove_by_predicate,
    _slot_sort_by_attribute,
    _slot_interleave_by_color,
    SLOT_LEVEL_PRIMITIVES,
)


def test_registry_contains_all_primitives():
    assert len(SLOT_LEVEL_PRIMITIVES) == 6
    assert "slot_recolor_by_attr" in SLOT_LEVEL_PRIMITIVES
    assert "slot_replicate_by_count" in SLOT_LEVEL_PRIMITIVES
    assert "slot_move_to" in SLOT_LEVEL_PRIMITIVES
    assert "slot_remove_by_predicate" in SLOT_LEVEL_PRIMITIVES
    assert "slot_sort_by_attribute" in SLOT_LEVEL_PRIMITIVES
    assert "slot_interleave_by_color" in SLOT_LEVEL_PRIMITIVES


class TestSlotRecolorByAttr:
    def test_recolor_large_objects(self):
        grid = [
            [1, 1, 0],
            [0, 0, 2],
            [0, 0, 2],
        ]
        result = _slot_recolor_by_attr(grid, {"attribute": "area", "threshold": 1, "color_if_above": 3, "color_if_below": 0})
        assert result is not None
        # Object 1 has area 2 (pixels (0,0),(0,1)), should be recolored to 3
        assert result[0][0] == 3
        assert result[0][1] == 3

    def test_recolor_small_objects(self):
        grid = [
            [1, 0, 0],
            [0, 0, 0],
            [0, 0, 2],
        ]
        result = _slot_recolor_by_attr(grid, {"attribute": "area", "threshold": 1, "color_if_above": 0, "color_if_below": 4})
        assert result is not None
        assert result[0][0] == 4  # area 1, recolored

    def test_empty_grid_returns_none(self):
        assert _slot_recolor_by_attr([], {}) is None


class TestSlotReplicateByCount:
    def test_replicate_all_objects(self):
        grid = [
            [1, 0],
            [0, 0],
        ]
        result = _slot_replicate_by_count(grid, {"count": 1, "dx": 0, "dy": 1, "select_by": "all"})
        assert result is not None
        # Original + 1 copy
        assert result[0][0] == 1
        assert result[1][0] == 1

    def test_replicate_largest_only(self):
        grid = [
            [1, 1, 0],
            [0, 0, 2],
            [0, 0, 2],
        ]
        result = _slot_replicate_by_count(grid, {"count": 1, "dx": 2, "dy": 0, "select_by": "largest"})
        assert result is not None

    def test_empty_grid_returns_none(self):
        assert _slot_replicate_by_count([], {}) is None


class TestSlotMoveTo:
    def test_move_largest_object(self):
        grid = [
            [1, 1, 0],
            [0, 0, 0],
            [0, 0, 2],
        ]
        result = _slot_move_to(grid, {"select_by": "largest", "target_x": 0, "target_y": 0})
        assert result is not None

    def test_move_smallest_object(self):
        grid = [
            [1, 1, 0],
            [0, 0, 2],
        ]
        result = _slot_move_to(grid, {"select_by": "smallest", "target_x": 0, "target_y": 0})
        assert result is not None

    def test_empty_grid_returns_none(self):
        assert _slot_move_to([], {}) is None


class TestSlotRemoveByPredicate:
    def test_remove_small_objects(self):
        grid = [
            [0, 0, 0, 0],
            [0, 1, 1, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 2],
        ]
        result = _slot_remove_by_predicate(grid, {"attribute": "area", "comparison": "less_than", "value": 2})
        assert result is not None
        # Small object (area 1, color 2) should be removed; large object (area 2, color 1) stays
        assert result[1][1] == 1
        assert result[3][3] == 0  # removed

    def test_empty_grid_returns_none(self):
        assert _slot_remove_by_predicate([], {}) is None


class TestSlotSortByAttribute:
    def test_sort_by_area_descending(self):
        grid = [
            [1, 1, 0],
            [0, 0, 2],
            [0, 0, 2],
        ]
        result = _slot_sort_by_attribute(grid, {"attribute": "area", "reverse": True, "layout": "row"})
        # Should produce a layout without error
        assert result is not None

    def test_single_object_no_sort(self):
        grid = [
            [1, 0],
            [0, 0],
        ]
        result = _slot_sort_by_attribute(grid, {"attribute": "area", "reverse": True, "layout": "row"})
        assert result is None  # fewer than 2 slots


class TestSlotInterleaveByColor:
    def test_interleave_horizontal(self):
        grid = [
            [0, 0, 0],
            [1, 2, 0],
            [0, 0, 0],
        ]
        result = _slot_interleave_by_color(grid, {"direction": "horizontal"})
        assert result is not None

    def test_single_color_no_interleave(self):
        grid = [
            [1, 0],
            [1, 0],
        ]
        result = _slot_interleave_by_color(grid, {"direction": "horizontal"})
        assert result is None  # fewer than 2 distinct colored objects

    def test_empty_grid_returns_none(self):
        assert _slot_interleave_by_color([], {}) is None
