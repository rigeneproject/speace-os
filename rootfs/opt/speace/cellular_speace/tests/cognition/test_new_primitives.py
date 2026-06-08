from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
    _complete_pattern_horizontal,
    _morph_diagonal_bands,
    _interleave_adjacent_objects,
)


def _g(rows):
    return [list(r) for r in rows]


# ---- complete_pattern_horizontal ----


def test_complete_pattern_horizontal_extend():
    grid = _g([
        [1, 2, 1, 2],
        [3, 4, 3, 4],
    ])
    result = _complete_pattern_horizontal(grid, {"target_w": 6})
    assert result is not None
    assert len(result[0]) == 6
    assert result[0] == [1, 2, 1, 2, 1, 2]
    assert result[1] == [3, 4, 3, 4, 3, 4]


def test_complete_pattern_horizontal_same_size():
    grid = _g([[1, 2], [3, 4]])
    result = _complete_pattern_horizontal(grid, {"target_w": 2})
    assert result is None


def test_complete_pattern_horizontal_no_period():
    grid = _g([[1, 2, 3], [4, 5, 6]])
    result = _complete_pattern_horizontal(grid, {"target_w": 6})
    assert result is not None
    assert len(result[0]) == 6
    # No period found, uses full width as period
    assert result[0] == [1, 2, 3, 1, 2, 3]


def test_complete_pattern_horizontal_crop():
    grid = _g([
        [1, 2, 1, 2, 1, 2],
        [3, 4, 3, 4, 3, 4],
    ])
    result = _complete_pattern_horizontal(grid, {"target_w": 4})
    assert result is not None
    assert len(result[0]) == 4
    assert result[0] == [1, 2, 1, 2]


def test_complete_pattern_horizontal_empty():
    assert _complete_pattern_horizontal([], {}) is None


# ---- morph_diagonal_bands ----


def test_morph_diagonal_bands_color_alternate():
    grid = _g([
        [1, 2],
        [2, 1],
    ])
    result = _morph_diagonal_bands(grid, {"operation": "color_alternate", "color_a": 1, "color_b": 2})
    assert result is not None
    assert result[0][0] == 2
    assert result[0][1] == 1
    assert result[1][0] == 1
    assert result[1][1] == 2


def test_morph_diagonal_bands_shift_down():
    grid = _g([
        [1, 2],
        [3, 4],
    ])
    result = _morph_diagonal_bands(grid, {"operation": "shift_down", "rows": 1})
    assert result is not None
    assert result[0] == [0, 0]
    assert result[1] == [1, 2]


def test_morph_diagonal_bands_shift_up():
    grid = _g([
        [1, 2],
        [3, 4],
    ])
    result = _morph_diagonal_bands(grid, {"operation": "shift_up", "rows": 1})
    assert result is not None
    assert result[0] == [3, 4]
    assert result[1] == [0, 0]


def test_morph_diagonal_bands_empty():
    assert _morph_diagonal_bands([], {}) is None


def test_morph_diagonal_bands_color_alternate_explicit():
    grid = _g([
        [5, 0, 5],
        [0, 5, 0],
        [5, 0, 5],
    ])
    result = _morph_diagonal_bands(grid, {"operation": "color_alternate", "color_a": 5, "color_b": 1})
    assert result is not None
    assert result[0][0] == 1
    assert result[1][1] == 1
    assert result[2][2] == 1


# ---- interleave_adjacent_objects ----


def test_interleave_adjacent_objects_horizontal():
    grid = _g([
        [1, 0, 2],
        [1, 0, 2],
    ])
    result = _interleave_adjacent_objects(grid, {"direction": "horizontal"})
    assert result is not None


def test_interleave_adjacent_objects_single_object():
    grid = _g([
        [1, 1],
        [1, 1],
    ])
    result = _interleave_adjacent_objects(grid, {"direction": "horizontal"})
    assert result is None


def test_interleave_adjacent_objects_empty():
    assert _interleave_adjacent_objects([], {}) is None


def test_interleave_adjacent_objects_two_objects():
    grid = _g([
        [1, 0, 2],
        [1, 0, 2],
        [1, 0, 2],
    ])
    result = _interleave_adjacent_objects(grid, {"direction": "horizontal"})
    assert result is not None
    assert len(result) == 3
    assert len(result[0]) == 3
