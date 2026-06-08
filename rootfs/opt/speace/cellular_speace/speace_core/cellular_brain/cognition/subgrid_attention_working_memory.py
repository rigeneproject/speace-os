"""Subgrid Attention & Working Memory (SAWM).

Decomposes a grid into meaningful sub-regions (objects, homogeneous patches,
repeating patterns), holds them in a small set of working-memory slots, and
recombines them after local transformations.
"""

from typing import Any, Dict, List, Optional, Tuple

from speace_core.cellular_brain.cognition.spatial_symbolic_reasoning_layer import (
    SpatialSymbolicReasoningLayer,
)

Grid = List[List[int]]


class MemorySlot:
    """One slot in working memory."""

    def __init__(self, subgrid: Grid, anchor: Tuple[int, int], slot_id: int) -> None:
        self.subgrid = subgrid
        self.anchor = anchor  # (x, y) top-left in the original grid
        self.slot_id = slot_id
        self.transformed: Optional[Grid] = None


class SubgridAttentionWorkingMemory:
    """Attentional decomposition and recombination for grid tasks."""

    def __init__(self, max_slots: int = 4) -> None:
        self.max_slots = max_slots
        self.slots: List[MemorySlot] = []
        self.spatial = SpatialSymbolicReasoningLayer()

    def reset(self) -> None:
        self.slots.clear()

    # ------------------------------------------------------------------ #
    # Decomposition strategies
    # ------------------------------------------------------------------ #

    def decompose_by_objects(self, grid: Grid) -> List[MemorySlot]:
        """Extract each connected non-background object as a slot."""
        scene = self.spatial.parse_grid(grid)
        slots: List[MemorySlot] = []
        for idx, obj in enumerate(scene.objects):
            if idx >= self.max_slots:
                break
            xs = [p[0] for p in obj.pixels]
            ys = [p[1] for p in obj.pixels]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            sub = [
                [grid[y][x] if (x, y) in obj.pixels else 0 for x in range(min_x, max_x + 1)]
                for y in range(min_y, max_y + 1)
            ]
            slots.append(MemorySlot(sub, anchor=(min_x, min_y), slot_id=idx))
        return slots

    def decompose_by_patches(self, grid: Grid, patch_size: int = 3, stride: Optional[int] = None) -> List[MemorySlot]:
        """Tile the grid into non-overlapping or strided patches."""
        if stride is None:
            stride = patch_size
        h, w = len(grid), len(grid[0])
        slots: List[MemorySlot] = []
        slot_id = 0
        for y in range(0, h, stride):
            for x in range(0, w, stride):
                if slot_id >= self.max_slots:
                    break
                sub = [
                    [grid[yy][xx] for xx in range(x, min(x + patch_size, w))]
                    for yy in range(y, min(y + patch_size, h))
                ]
                slots.append(MemorySlot(sub, anchor=(x, y), slot_id=slot_id))
                slot_id += 1
            if slot_id >= self.max_slots:
                break
        return slots

    def load_slots(self, slots: List[MemorySlot]) -> None:
        self.slots = slots[: self.max_slots]

    # ------------------------------------------------------------------ #
    # Attention shift
    # ------------------------------------------------------------------ #

    def attention_shift(self, slot_id: int, new_subgrid: Grid) -> None:
        """Replace the content of a slot (e.g. after local transformation)."""
        for slot in self.slots:
            if slot.slot_id == slot_id:
                slot.transformed = new_subgrid
                return

    # ------------------------------------------------------------------ #
    # Composition
    # ------------------------------------------------------------------ #

    def compose_output(self, target_size: Optional[Tuple[int, int]] = None) -> Optional[Grid]:
        """Reassemble slots into a single grid.

        If target_size is None, uses the bounding box of all anchors + subgrids.
        """
        if not self.slots:
            return None

        # Determine output dimensions
        if target_size is None:
            max_x = max(
                s.anchor[0] + (len(s.transformed or s.subgrid)[0] if s.subgrid else 0)
                for s in self.slots
            )
            max_y = max(
                s.anchor[1] + len(s.transformed or s.subgrid)
                for s in self.slots
            )
            target_h, target_w = max_y, max_x
        else:
            target_h, target_w = target_size

        out = [[0] * target_w for _ in range(target_h)]
        for slot in self.slots:
            sub = slot.transformed if slot.transformed is not None else slot.subgrid
            sw = len(sub[0]) if sub else 0
            sh = len(sub) if sub else 0
            ax, ay = slot.anchor
            for dy in range(sh):
                for dx in range(sw):
                    gx, gy = ax + dx, ay + dy
                    if 0 <= gx < target_w and 0 <= gy < target_h:
                        if sub[dy][dx] != 0:
                            out[gy][gx] = sub[dy][dx]
        return out
