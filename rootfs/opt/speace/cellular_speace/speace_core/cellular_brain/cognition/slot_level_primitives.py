"""Slot-level ARC-AGI primitives — operate on object-centric representations.

These primitives extract objects from the grid, perform slot-level
transformations, and reconstruct the output grid. They enable
abstraction (object slots), induction (slot-level rules), and
compositional generalization (slot operations compose freely).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from speace_core.cellular_brain.cognition.object_centric_representation import (
    ObjectCentricEncoder,
    ObjectCentricScene,
    ObjectSlot,
    SlotLevelDiff,
)

Grid = List[List[int]]

_encoder = ObjectCentricEncoder(connectivity=4)


def _slot_recolor_by_attr(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Recolor objects based on an attribute threshold.

    ``params.attribute``: attribute key (e.g. "area", "aspect_ratio")
    ``params.threshold``: numeric threshold
    ``params.color_if_above``: color to apply when attribute > threshold
    ``params.color_if_below``: color to apply when attribute <= threshold
    ``params.comparison``: "above" or "below"
    """
    if not grid:
        return None
    attr: str = params.get("attribute", "area")
    threshold: float = params.get("threshold", 5)
    color_above: int = params.get("color_if_above", 0)
    color_below: int = params.get("color_if_below", 0)
    comparison: str = params.get("comparison", "above")
    scene = _encoder.encode(grid)
    out = [row[:] for row in grid]
    for slot in scene.slots:
        val = slot.attributes.get(attr, 0)
        if val is None:
            continue
        apply_color = color_above if (comparison == "above" and val > threshold) or (comparison == "below" and val < threshold) else color_below
        if apply_color == 0:
            continue
        for y, x in slot.pixels:
            out[y][x] = apply_color
    return out


def _slot_replicate_by_count(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Replicate each object a number of times in a direction.

    ``params.count``: replication count per object (default 1)
    ``params.dx``, ``params.dy``: per-copy offset
    ``params.select_by``: "all", "largest", "smallest", or attribute:value
    """
    if not grid:
        return None
    count: int = params.get("count", 1)
    dx: int = params.get("dx", 1)
    dy: int = params.get("dy", 0)
    select_by: str = params.get("select_by", "all")
    scene = _encoder.encode(grid)
    h, w = len(grid), len(grid[0])

    selected: List[ObjectSlot] = list(scene.slots)
    if select_by == "largest":
        selected = [max(scene.slots, key=lambda s: s.area)] if scene.slots else []
    elif select_by == "smallest":
        selected = [min(scene.slots, key=lambda s: s.area)] if scene.slots else []

    if not selected:
        return None

    out = [[0] * w for _ in range(h)]
    bg = scene.background_color

    def draw_pixels(slot: ObjectSlot, offset_y: int, offset_x: int) -> None:
        for py, px in slot.pixels:
            ny, nx = py + offset_y, px + offset_x
            if 0 <= ny < h and 0 <= nx < w:
                out[ny][nx] = slot.color

    for slot in scene.slots:
        draw_pixels(slot, 0, 0)
    for slot in selected:
        for c in range(1, count + 1):
            draw_pixels(slot, dy * c, dx * c)
    return out


def _slot_move_to(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Move a specific object (largest/smallest/by attribute) to target position.

    ``params.select_by``: "largest", "smallest", or "first"
    ``params.target_x``, ``params.target_y``: target centroid position
    """
    if not grid:
        return None
    select_by: str = params.get("select_by", "largest")
    target_x: int = params.get("target_x", 0)
    target_y: int = params.get("target_y", 0)
    scene = _encoder.encode(grid)
    if not scene.slots:
        return None

    selected: Optional[ObjectSlot] = None
    if select_by == "largest":
        selected = max(scene.slots, key=lambda s: s.area)
    elif select_by == "smallest":
        selected = min(scene.slots, key=lambda s: s.area)
    elif select_by == "first":
        selected = scene.slots[0]

    if selected is None:
        return None

    h, w = len(grid), len(grid[0])
    out = [[scene.background_color] * w for _ in range(h)]
    dx = int(target_x - selected.centroid[1])
    dy = int(target_y - selected.centroid[0])

    for slot in scene.slots:
        for y, x in slot.pixels:
            out[y][x] = slot.color

    for y, x in selected.pixels:
        out[y][x] = scene.background_color
        ny, nx = y + dy, x + dx
        if 0 <= ny < h and 0 <= nx < w:
            out[ny][nx] = selected.color
    return out


def _slot_remove_by_predicate(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Remove objects matching a predicate.

    ``params.attribute``: attribute key (e.g. "area", "color")
    ``params.comparison``: "less_than", "greater_than", "equals"
    ``params.value``: comparison value
    """
    if not grid:
        return None
    attr: str = params.get("attribute", "area")
    comp: str = params.get("comparison", "less_than")
    value: Any = params.get("value", 3)
    scene = _encoder.encode(grid)
    h, w = len(grid), len(grid[0])
    out = [[scene.background_color] * w for _ in range(h)]
    bg = scene.background_color

    for slot in scene.slots:
        val = slot.attributes.get(attr, 0)
        if val is None:
            continue
        keep = False
        if comp == "less_than" and val < value:
            keep = False
        elif comp == "greater_than" and val > value:
            keep = False
        elif comp == "equals" and val == value:
            keep = False
        else:
            keep = True
        if keep:
            for y, x in slot.pixels:
                out[y][x] = slot.color
    return out


def _slot_sort_by_attribute(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Reorder objects in the grid sorted by an attribute.

    ``params.attribute``: sorting key (e.g. "area", "color", "centroid_y")
    ``params.reverse``: ascending (False) or descending (True)
    ``params.layout``: "row" or "column" arrangement
    """
    if not grid:
        return None
    attr: str = params.get("attribute", "area")
    reverse: bool = params.get("reverse", True)
    layout: str = params.get("layout", "row")
    scene = _encoder.encode(grid)
    h, w = len(grid), len(grid[0])
    if len(scene.slots) < 2:
        return None
    scene.sort_slots(key=attr, reverse=reverse)
    out = [[scene.background_color] * w for _ in range(h)]
    if layout == "row":
        x_offset = 0
        for slot in scene.slots:
            dys = [p[0] - int(slot.centroid[0]) for p in slot.pixels]
            dxs = [p[1] - int(slot.centroid[1]) for p in slot.pixels]
            for i, (py, px) in enumerate(slot.pixels):
                ny = h // 2 + dys[i]
                nx = x_offset + dxs[i]
                if 0 <= ny < h and 0 <= nx < w:
                    out[ny][nx] = slot.color
            x_offset += max(p[1] for p in slot.pixels) - min(p[1] for p in slot.pixels) + 1
            if x_offset >= w:
                break
    return out


def _slot_interleave_by_color(grid: Grid, params: Dict[str, Any]) -> Optional[Grid]:
    """Interleave rows/columns of different-colored objects.

    ``params.direction``: "horizontal" or "vertical"
    Sorts objects by color, then interleaves their pixel columns/rows.
    """
    if not grid:
        return None
    direction: str = params.get("direction", "horizontal")
    scene = _encoder.encode(grid)
    h, w = len(grid), len(grid[0])
    scene.sort_slots(key="color", reverse=False)
    if len(scene.slots) < 2:
        return None
    out = [[scene.background_color] * w for _ in range(h)]
    if direction == "horizontal":
        col_groups: Dict[int, List[Tuple[int, int, int]]] = {}
        for slot in scene.slots:
            for y, x in slot.pixels:
                col_groups.setdefault(x, []).append((y, slot.color))
        interleaved: List[int] = []
        for col in sorted(col_groups.keys()):
            interleaved.append(col)
        for ci, col in enumerate(interleaved):
            target_col = ci
            if target_col < w:
                for y, color in col_groups[col]:
                    if 0 <= target_col < w:
                        out[y][target_col] = color
    return out


# Registry of slot-level primitives (appended to _PRIMITIVE_REGISTRY)
SLOT_LEVEL_PRIMITIVES: Dict[str, Any] = {
    "slot_recolor_by_attr": _slot_recolor_by_attr,
    "slot_replicate_by_count": _slot_replicate_by_count,
    "slot_move_to": _slot_move_to,
    "slot_remove_by_predicate": _slot_remove_by_predicate,
    "slot_sort_by_attribute": _slot_sort_by_attribute,
    "slot_interleave_by_color": _slot_interleave_by_color,
}
