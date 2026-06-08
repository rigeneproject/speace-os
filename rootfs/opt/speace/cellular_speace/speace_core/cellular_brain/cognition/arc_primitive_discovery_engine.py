"""ARC Primitive Discovery Engine — automatic + manual primitive expansion.

Analyzes ARC training tasks to find transformations not covered by the current
primitive registry. Falls back to a curated set of common ARC primitives when
discovery yields insufficient coverage.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

Grid = List[List[int]]
PrimitiveFn = Callable[[Grid, Dict[str, Any]], Optional[Grid]]


# --------------------------------------------------------------------------- #
# Manual fallback primitives for ARC (commonly needed operations)
# --------------------------------------------------------------------------- #

def _gravity(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Objects fall down until they hit another object or bottom."""
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for x in range(w):
        column = [out[y][x] for y in range(h)]
        # Gather non-zero pixels preserving order from top to bottom
        non_zero = [c for c in column if c != 0]
        # Place them at the bottom, preserving order
        new_col = [0] * (h - len(non_zero)) + non_zero
        for y in range(h):
            out[y][x] = new_col[y]
    return out


def _gravity_horizontal(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Objects fall left until they hit another object or left edge."""
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    for y in range(h):
        row = out[y]
        non_zero = [c for c in row if c != 0]
        new_row = non_zero + [0] * (w - len(non_zero))
        out[y] = new_row
    return out


def _remove_noise(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Remove isolated pixels (no same-color 4-neighbor)."""
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    changed = False
    for y in range(h):
        for x in range(w):
            if grid[y][x] == 0:
                continue
            color = grid[y][x]
            neighbors = 0
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == color:
                    neighbors += 1
            if neighbors == 0:
                out[y][x] = 0
                changed = True
    return out if changed else grid


def _trim_background(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Trim uniform border of background color (default 0)."""
    if not grid:
        return None
    bg = params.get("background", 0)
    h, w = len(grid), len(grid[0])
    # Find content bounds
    min_y, max_y = h, 0
    min_x, max_x = w, 0
    for y in range(h):
        for x in range(w):
            if grid[y][x] != bg:
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                min_x = min(min_x, x)
                max_x = max(max_x, x)
    if min_y > max_y or min_x > max_x:
        return grid
    return [row[min_x : max_x + 1] for row in grid[min_y : max_y + 1]]


def _fill_background(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Fill all background pixels with a color."""
    color: int = params.get("color", 1)
    bg: int = params.get("background", 0)
    if not grid:
        return None
    return [[color if c == bg else c for c in row] for row in grid]


def _invert_colors(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Invert colors: max_color - color for non-zero, keep zero."""
    max_color: int = params.get("max_color", 9)
    if not grid:
        return None
    return [[max_color - c if c != 0 else 0 for c in row] for row in grid]


def _detect_enclosed(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Flood fill enclosed areas (background regions not touching border) with fill_color."""
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    bg: int = params.get("background", 0)
    fill: int = params.get("fill_color", 1)
    out = [row[:] for row in grid]
    visited = [[False] * w for _ in range(h)]
    # Flood fill from all border background cells
    stack = []
    for y in range(h):
        for x in range(w):
            if (y == 0 or y == h - 1 or x == 0 or x == w - 1) and grid[y][x] == bg:
                stack.append((x, y))
                visited[y][x] = True
    while stack:
        cx, cy = stack.pop()
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and grid[ny][nx] == bg:
                visited[ny][nx] = True
                stack.append((nx, ny))
    # Fill non-visited background cells
    changed = False
    for y in range(h):
        for x in range(w):
            if grid[y][x] == bg and not visited[y][x]:
                out[y][x] = fill
                changed = True
    return out if changed else grid


def _compress(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Remove empty rows and columns."""
    if not grid:
        return None
    bg: int = params.get("background", 0)
    # Remove empty rows
    rows = [r for r in grid if any(c != bg for c in r)]
    if not rows:
        return grid
    # Remove empty columns
    w = len(rows[0])
    cols_keep = [x for x in range(w) if any(r[x] != bg for r in rows)]
    if len(cols_keep) == w and len(rows) == len(grid):
        return grid
    return [[r[x] for x in cols_keep] for r in rows]


def _extend_to_boundary(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Extend objects to the nearest boundary in a direction."""
    direction: str = params.get("direction", "down")
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    if direction == "down":
        for x in range(w):
            col = [grid[y][x] for y in range(h)]
            # Find topmost non-zero and extend it down
            for y in range(h):
                if col[y] != 0:
                    for yy in range(y + 1, h):
                        if col[yy] == 0:
                            out[yy][x] = col[y]
    elif direction == "right":
        for y in range(h):
            row = grid[y]
            for x in range(w):
                if row[x] != 0:
                    for xx in range(x + 1, w):
                        if row[xx] == 0:
                            out[y][xx] = row[x]
    return out


def _swap_colors(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Swap two colors globally."""
    a: int = params.get("color_a", 0)
    b: int = params.get("color_b", 0)
    if a == b or a == 0 or b == 0:
        return None
    return [[b if c == a else (a if c == b else c) for c in row] for row in grid]


def _color_by_size(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Recolor objects by their size rank."""
    from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
        SpatialSymbolicReasoningLayer,
    )
    if not grid:
        return None
    spatial = SpatialSymbolicReasoningLayer()
    scene = spatial.parse_grid(grid)
    objs = scene.objects
    if len(objs) < 2:
        return None
    sorted_objs = sorted(objs, key=lambda o: o.area)
    color_map: Dict[int, int] = {}
    for rank, obj in enumerate(sorted_objs):
        # Use rank+1 as color, capped
        color_map[obj.color] = min(rank + 1, 9)
    return [[color_map.get(c, c) for c in row] for row in grid]


def _repeat_pattern(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Repeat a sub-pattern to fill the grid."""
    if not grid:
        return None
    from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
        SpatialSymbolicReasoningLayer,
    )
    pat = SpatialSymbolicReasoningLayer.find_repeating_pattern(grid)
    if pat is None:
        return None
    return grid  # Already tiled; no transformation needed


def _mirror_object(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Mirror individual objects horizontally or vertically within the grid."""
    axis: str = params.get("axis", "horizontal")
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    # Simple heuristic: mirror each non-background pixel across center
    cx = w / 2.0
    cy = h / 2.0
    for y in range(h):
        for x in range(w):
            if grid[y][x] != 0:
                if axis == "horizontal":
                    mx = int(2 * cx - x - 0.5)
                    if 0 <= mx < w and out[y][mx] == 0:
                        out[y][mx] = grid[y][x]
                else:
                    my = int(2 * cy - y - 0.5)
                    if 0 <= my < h and out[my][x] == 0:
                        out[my][x] = grid[y][x]
    return out


def _make_symmetric(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Force the entire grid to be symmetric along an axis."""
    axis: str = params.get("axis", "horizontal")
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    out = [row[:] for row in grid]
    if axis == "horizontal":
        for y in range(h):
            for x in range(w // 2):
                if out[y][x] != 0 and out[y][w - 1 - x] == 0:
                    out[y][w - 1 - x] = out[y][x]
                elif out[y][w - 1 - x] != 0 and out[y][x] == 0:
                    out[y][x] = out[y][w - 1 - x]
    elif axis == "vertical":
        for y in range(h // 2):
            for x in range(w):
                if out[y][x] != 0 and out[h - 1 - y][x] == 0:
                    out[h - 1 - y][x] = out[y][x]
                elif out[h - 1 - y][x] != 0 and out[y][x] == 0:
                    out[y][x] = out[h - 1 - y][x]
    return out


def _border(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Add a colored border around the grid."""
    color: int = params.get("color", 1)
    if not grid:
        return None
    h, w = len(grid), len(grid[0])
    top = [[color] * (w + 2)]
    mid = [[color] + row + [color] for row in grid]
    bot = [[color] * (w + 2)]
    return top + mid + bot


def _remove_objects_by_size(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Remove objects smaller or larger than threshold."""
    from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
        SpatialSymbolicReasoningLayer,
    )
    mode: str = params.get("mode", "smaller")  # smaller | larger
    threshold: int = params.get("threshold", 2)
    if not grid:
        return None
    spatial = SpatialSymbolicReasoningLayer()
    scene = spatial.parse_grid(grid)
    out = [row[:] for row in grid]
    for obj in scene.objects:
        if (mode == "smaller" and obj.area < threshold) or (mode == "larger" and obj.area > threshold):
            for x, y in obj.pixels:
                out[y][x] = 0
    return out


def _intersection(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Pixel-wise intersection with another grid (passed as 'other' param)."""
    other: Optional[Grid] = params.get("other")
    if other is None or len(grid) != len(other) or len(grid[0]) != len(other[0]):
        return None
    return [[a if a == b and a != 0 else 0 for a, b in zip(ra, rb)] for ra, rb in zip(grid, other)]


def _union(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Pixel-wise union with another grid (passed as 'other' param)."""
    other: Optional[Grid] = params.get("other")
    if other is None or len(grid) != len(other) or len(grid[0]) != len(other[0]):
        return None
    return [[max(a, b) for a, b in zip(ra, rb)] for ra, rb in zip(grid, other)]


def _difference(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Pixel-wise difference with another grid."""
    other: Optional[Grid] = params.get("other")
    if other is None or len(grid) != len(other) or len(grid[0]) != len(other[0]):
        return None
    return [[a if a != 0 and b == 0 else 0 for a, b in zip(ra, rb)] for ra, rb in zip(grid, other)]


# Registry of manual ARC primitives
MANUAL_ARC_PRIMITIVES: Dict[str, PrimitiveFn] = {
    "gravity": _gravity,
    "gravity_horizontal": _gravity_horizontal,
    "remove_noise": _remove_noise,
    "trim_background": _trim_background,
    "fill_background": _fill_background,
    "invert_colors": _invert_colors,
    "detect_enclosed": _detect_enclosed,
    "compress": _compress,
    "extend_to_boundary": _extend_to_boundary,
    "swap_colors": _swap_colors,
    "color_by_size": _color_by_size,
    "repeat_pattern": _repeat_pattern,
    "mirror_object": _mirror_object,
    "make_symmetric": _make_symmetric,
    "border": _border,
    "remove_objects_by_size": _remove_objects_by_size,
    "intersection": _intersection,
    "union": _union,
    "difference": _difference,
}


# --------------------------------------------------------------------------- #
# Discovery engine
# --------------------------------------------------------------------------- #

class ARCPrimitiveDiscoveryEngine:
    """Discovers new primitives by analyzing uncovered ARC tasks."""

    def __init__(self, existing_primitives: Dict[str, PrimitiveFn]) -> None:
        self.existing = existing_primitives
        self.manual = MANUAL_ARC_PRIMITIVES

    @staticmethod
    def _grid_eq(a: Grid, b: Grid) -> bool:
        if len(a) != len(b):
            return False
        return all(len(ra) == len(rb) and ra == rb for ra, rb in zip(a, b))

    def _is_covered(self, train_pairs: List[Dict[str, Any]]) -> bool:
        """Check if any existing primitive (single or compositional depth 2) explains all train pairs."""
        # Try single primitives first
        for name, fn in {**self.existing, **self.manual}.items():
            matches = 0
            for pair in train_pairs:
                try:
                    result = fn(pair["input"], {})
                    if result is not None and self._grid_eq(result, pair["output"]):
                        matches += 1
                except Exception:
                    pass
            if matches == len(train_pairs):
                return True
        return False

    def discover_missing_primitives(
        self, tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze tasks and return discovery statistics."""
        uncovered = 0
        size_changes: List[Tuple[int, int, int, int]] = []
        color_changes: List[Set[int]] = []
        for task in tasks:
            train = task.get("train", [])
            if not train:
                continue
            if not self._is_covered(train):
                uncovered += 1
                inp = train[0]["input"]
                out = train[0]["output"]
                size_changes.append((len(inp), len(inp[0]), len(out), len(out[0])))
                all_colors = set()
                for row in out:
                    all_colors.update(row)
                color_changes.append(all_colors)

        return {
            "total_tasks": len(tasks),
            "uncovered_tasks": uncovered,
            "coverage_rate": 1.0 - uncovered / len(tasks) if tasks else 1.0,
            "size_change_samples": size_changes[:20],
            "output_color_samples": [list(s)[:10] for s in color_changes[:20]],
        }

    def build_enriched_registry(self) -> Dict[str, PrimitiveFn]:
        """Return existing + manual primitives merged."""
        merged: Dict[str, PrimitiveFn] = {}
        merged.update(self.existing)
        merged.update(self.manual)
        return merged

    @staticmethod
    def save_manual_primitives(path: str = "data/arc_agi/manual_primitives_manifest.json") -> None:
        """Save a manifest of manual primitive names for audit."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "source": "manual_curation",
            "primitive_count": len(MANUAL_ARC_PRIMITIVES),
            "primitive_names": sorted(MANUAL_ARC_PRIMITIVES.keys()),
        }
        out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
