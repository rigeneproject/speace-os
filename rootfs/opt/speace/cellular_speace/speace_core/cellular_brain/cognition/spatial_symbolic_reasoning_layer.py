"""Spatial Symbolic Reasoning Layer — object-centric representation of 2D grids.

Extracts objects, computes spatial relations, diffs scenes, and performs
analogical matching. Used by the Few-Shot Program Induction Engine for
ARC-AGI style tasks.
"""

from __future__ import annotations

import logging
import uuid
from collections import deque
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SpatialRelation(str, Enum):
    ABOVE = "above"
    BELOW = "below"
    LEFT_OF = "left_of"
    RIGHT_OF = "right_of"
    INSIDE = "inside"
    ENCLOSING = "enclosing"
    TOUCHING = "touching"
    SAME_ROW = "same_row"
    SAME_COL = "same_col"
    SYMMETRIC_TO = "symmetric_to"
    ALIGNED_WITH = "aligned_with"
    PART_OF = "part_of"


class GridObject(BaseModel):
    object_id: str = Field(default_factory=lambda: f"obj_{uuid.uuid4().hex[:8]}")
    color: int
    pixels: List[Tuple[int, int]] = Field(default_factory=list)
    bbox: Tuple[int, int, int, int] = Field(default_factory=lambda: (0, 0, 0, 0))
    normalized_shape: List[Tuple[int, int]] = Field(default_factory=list)
    area: int = 0
    centroid: Tuple[float, float] = (0.0, 0.0)

    def compute_attributes(self) -> None:
        if not self.pixels:
            return
        xs = [x for x, y in self.pixels]
        ys = [y for x, y in self.pixels]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        self.bbox = (min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)
        self.area = len(self.pixels)
        self.centroid = (sum(xs) / len(xs), sum(ys) / len(ys))
        self.normalized_shape = sorted(
            [(x - min_x, y - min_y) for x, y in self.pixels]
        )


class GridScene(BaseModel):
    grid: List[List[int]] = Field(default_factory=list)
    objects: List[GridObject] = Field(default_factory=list)
    height: int = 0
    width: int = 0

    @classmethod
    def from_grid(cls, grid: List[List[int]]) -> "GridScene":
        if not grid:
            return cls(grid=[], objects=[], height=0, width=0)
        height = len(grid)
        width = len(grid[0])
        return cls(grid=grid, objects=[], height=height, width=width)


class GridDiff(BaseModel):
    deleted: List[GridObject] = Field(default_factory=list)
    created: List[GridObject] = Field(default_factory=list)
    moved: List[Dict[str, Any]] = Field(default_factory=list)
    recolored: List[Dict[str, Any]] = Field(default_factory=list)
    canvas_change: Dict[str, Any] = Field(default_factory=dict)


class SpatialSymbolicReasoningLayer:
    """Parses 2D grids into objects, relations, and diffs."""

    def __init__(self, connectivity: int = 4) -> None:
        self.connectivity = connectivity
        self._directions = (
            [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if connectivity == 4
            else [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
        )

    # ------------------------------------------------------------------ #
    # Parsing
    # ------------------------------------------------------------------ #

    def parse_grid(self, grid: List[List[int]]) -> GridScene:
        scene = GridScene.from_grid(grid)
        scene.objects = self.extract_objects(scene)
        return scene

    def extract_objects(self, scene: GridScene) -> List[GridObject]:
        if not scene.grid:
            return []
        visited = set()
        objects: List[GridObject] = []
        h, w = scene.height, scene.width
        for y in range(h):
            for x in range(w):
                if (x, y) in visited or scene.grid[y][x] == 0:
                    continue
                color = scene.grid[y][x]
                pixels: List[Tuple[int, int]] = []
                queue = deque([(x, y)])
                visited.add((x, y))
                while queue:
                    cx, cy = queue.popleft()
                    pixels.append((cx, cy))
                    for dx, dy in self._directions:
                        nx, ny = cx + dx, cy + dy
                        if (
                            0 <= nx < w
                            and 0 <= ny < h
                            and (nx, ny) not in visited
                            and scene.grid[ny][nx] == color
                        ):
                            visited.add((nx, ny))
                            queue.append((nx, ny))
                obj = GridObject(color=color, pixels=pixels)
                obj.compute_attributes()
                objects.append(obj)
        return objects

    # ------------------------------------------------------------------ #
    # Relations
    # ------------------------------------------------------------------ #

    def compute_relations(self, scene: GridScene) -> Dict[str, List[str]]:
        rels: Dict[str, List[str]] = {}
        objs = scene.objects
        for i, a in enumerate(objs):
            a_id = a.object_id
            rels.setdefault(a_id, [])
            for j, b in enumerate(objs):
                if i == j:
                    continue
                for r in self._relations_between(a, b, scene.width, scene.height):
                    rels[a_id].append(f"{r}:{b.object_id}")
        return rels

    @staticmethod
    def _relations_between(a: GridObject, b: GridObject, scene_width: int = 0, scene_height: int = 0) -> List[SpatialRelation]:
        results: List[SpatialRelation] = []
        ax1, ay1, aw, ah = a.bbox
        ax2, ay2 = ax1 + aw, ay1 + ah
        bx1, by1, bw, bh = b.bbox
        bx2, by2 = bx1 + bw, by1 + bh
        # touching
        if not (ax2 < bx1 or bx2 < ax1 or ay2 < by1 or by2 < ay1):
            results.append(SpatialRelation.TOUCHING)
        # inside / enclosing
        if ax1 >= bx1 and ay1 >= by1 and ax2 <= bx2 and ay2 <= by2 and (aw, ah) != (bw, bh):
            results.append(SpatialRelation.INSIDE)
        if bx1 >= ax1 and by1 >= ay1 and bx2 <= ax2 and by2 <= ay2 and (aw, ah) != (bw, bh):
            results.append(SpatialRelation.ENCLOSING)
        # above / below
        if ay2 <= by1:
            results.append(SpatialRelation.ABOVE)
        if by2 <= ay1:
            results.append(SpatialRelation.BELOW)
        # left / right
        if ax2 <= bx1:
            results.append(SpatialRelation.LEFT_OF)
        if bx2 <= ax1:
            results.append(SpatialRelation.RIGHT_OF)
        # same row / col (centroids)
        if abs(a.centroid[1] - b.centroid[1]) < 1.0:
            results.append(SpatialRelation.SAME_ROW)
        if abs(a.centroid[0] - b.centroid[0]) < 1.0:
            results.append(SpatialRelation.SAME_COL)
        # symmetric_to (mirror across scene center)
        if scene_width > 0 and scene_height > 0:
            cx = scene_width / 2.0
            cy = scene_height / 2.0
            a_mirror_x = 2 * cx - a.centroid[0]
            a_mirror_y = 2 * cy - a.centroid[1]
            if abs(a_mirror_x - b.centroid[0]) < 1.0 and abs(a_mirror_y - b.centroid[1]) < 1.0:
                if a.normalized_shape == b.normalized_shape:
                    results.append(SpatialRelation.SYMMETRIC_TO)
        # aligned_with (same row or same col and close)
        if (SpatialRelation.SAME_ROW in results or SpatialRelation.SAME_COL in results) and SpatialRelation.TOUCHING in results:
            results.append(SpatialRelation.ALIGNED_WITH)
        # part_of (pixel subset)
        if a.area < b.area and all(pa in b.pixels for pa in a.pixels):
            results.append(SpatialRelation.PART_OF)
        if b.area < a.area and all(pb in a.pixels for pb in b.pixels):
            results.append(SpatialRelation.PART_OF)
        return results

    # ------------------------------------------------------------------ #
    # Diff
    # ------------------------------------------------------------------ #

    def diff_scenes(self, before: GridScene, after: GridScene) -> GridDiff:
        diff = GridDiff()
        matched_before = set()
        matched_after = set()
        # greedy matching by normalized shape + color
        for i, a in enumerate(before.objects):
            best_j: Optional[int] = None
            best_score = -1.0
            for j, b in enumerate(after.objects):
                if j in matched_after:
                    continue
                if a.color != b.color:
                    continue
                if a.normalized_shape == b.normalized_shape:
                    score = 2.0
                elif len(a.pixels) == len(b.pixels):
                    score = 1.0
                else:
                    score = -abs(len(a.pixels) - len(b.pixels))
                if score > best_score:
                    best_score = score
                    best_j = j
            if best_j is not None and best_score >= 1.0:
                matched_before.add(i)
                matched_after.add(best_j)
                b = after.objects[best_j]
                dx = round(b.centroid[0] - a.centroid[0])
                dy = round(b.centroid[1] - a.centroid[1])
                if dx != 0 or dy != 0:
                    diff.moved.append(
                        {
                            "object_id": a.object_id,
                            "from": a.centroid,
                            "to": b.centroid,
                            "vector": (dx, dy),
                        }
                    )
                if a.color != b.color:
                    diff.recolored.append(
                        {
                            "object_id": a.object_id,
                            "old_color": a.color,
                            "new_color": b.color,
                        }
                    )
        # Detect recoloring among unmatched objects with same shape/position
        for i, a in enumerate(before.objects):
            if i in matched_before:
                continue
            for j, b in enumerate(after.objects):
                if j in matched_after:
                    continue
                if a.bbox == b.bbox and a.normalized_shape == b.normalized_shape and a.color != b.color:
                    matched_before.add(i)
                    matched_after.add(j)
                    diff.recolored.append(
                        {
                            "object_id": a.object_id,
                            "old_color": a.color,
                            "new_color": b.color,
                        }
                    )
                    break
        # Detect moved+recolored among unmatched objects with same shape
        for i, a in enumerate(before.objects):
            if i in matched_before:
                continue
            for j, b in enumerate(after.objects):
                if j in matched_after:
                    continue
                if a.normalized_shape == b.normalized_shape and a.color != b.color:
                    matched_before.add(i)
                    matched_after.add(j)
                    dx = round(b.centroid[0] - a.centroid[0])
                    dy = round(b.centroid[1] - a.centroid[1])
                    if dx != 0 or dy != 0:
                        diff.moved.append(
                            {
                                "object_id": a.object_id,
                                "from": a.centroid,
                                "to": b.centroid,
                                "vector": (dx, dy),
                            }
                        )
                    diff.recolored.append(
                        {
                            "object_id": a.object_id,
                            "old_color": a.color,
                            "new_color": b.color,
                        }
                    )
                    break
        for i, a in enumerate(before.objects):
            if i not in matched_before:
                diff.deleted.append(a)
        for j, b in enumerate(after.objects):
            if j not in matched_after:
                diff.created.append(b)
        # canvas change
        if before.height != after.height or before.width != after.width:
            diff.canvas_change = {
                "before": (before.width, before.height),
                "after": (after.width, after.height),
            }
        return diff

    # ------------------------------------------------------------------ #
    # Advanced symmetry detection
    # ------------------------------------------------------------------ #

    @staticmethod
    def check_grid_symmetry(grid: List[List[int]], symmetry_type: str) -> bool:
        """Check if the whole grid exhibits a symmetry."""
        if not grid:
            return False
        h, w = len(grid), len(grid[0])
        if symmetry_type == "horizontal":
            return all(grid[y] == grid[h - 1 - y] for y in range(h))
        if symmetry_type == "vertical":
            return all(grid[y][x] == grid[y][w - 1 - x] for y in range(h) for x in range(w))
        if symmetry_type == "diagonal_main":
            return all(grid[y][x] == grid[x][y] for y in range(h) for x in range(w) if x < h and y < w)
        if symmetry_type == "diagonal_anti":
            return all(grid[y][x] == grid[h - 1 - x][w - 1 - y] for y in range(h) for x in range(w) if h - 1 - x < h and w - 1 - y < w)
        if symmetry_type == "rotational_180":
            return all(grid[y][x] == grid[h - 1 - y][w - 1 - x] for y in range(h) for x in range(w))
        return False

    # ------------------------------------------------------------------ #
    # Repeating pattern detection
    # ------------------------------------------------------------------ #

    @staticmethod
    def find_repeating_pattern(grid: List[List[int]]) -> Optional[Dict[str, Any]]:
        """Detect tiling / repeating subgrid patterns."""
        if not grid:
            return None
        h, w = len(grid), len(grid[0])
        for ph in range(1, h // 2 + 1):
            for pw in range(1, w // 2 + 1):
                if h % ph != 0 or w % pw != 0:
                    continue
                tile = [row[:pw] for row in grid[:ph]]
                match = True
                for ty in range(0, h, ph):
                    for tx in range(0, w, pw):
                        for dy in range(ph):
                            for dx in range(pw):
                                if grid[ty + dy][tx + dx] != tile[dy][dx]:
                                    match = False
                                    break
                            if not match:
                                break
                        if not match:
                            break
                    if not match:
                        break
                if match:
                    return {"tile_height": ph, "tile_width": pw, "tile": tile, "repetitions": (h // ph) * (w // pw)}
        return None

    # ------------------------------------------------------------------ #
    # Hierarchical object extraction
    # ------------------------------------------------------------------ #

    def extract_hierarchical_objects(self, scene: GridScene) -> List[Dict[str, Any]]:
        """Detect nested objects (objects contained within other objects)."""
        hierarchies: List[Dict[str, Any]] = []
        objs = scene.objects
        for i, outer in enumerate(objs):
            children: List[str] = []
            for j, inner in enumerate(objs):
                if i == j:
                    continue
                if inner.area < outer.area:
                    if all(p in outer.pixels for p in inner.pixels):
                        children.append(inner.object_id)
            if children:
                hierarchies.append({"parent_id": outer.object_id, "child_ids": children, "parent_color": outer.color})
        return hierarchies

    # ------------------------------------------------------------------ #
    # Analogical matching
    # ------------------------------------------------------------------ #

    def analogical_match(
        self, source_scene: GridScene, target_scene: GridScene
    ) -> List[Dict[str, Any]]:
        mappings: List[Dict[str, Any]] = []
        used_target = set()
        for s_obj in source_scene.objects:
            best_t: Optional[GridObject] = None
            best_score = -1.0
            for t_obj in target_scene.objects:
                if t_obj.object_id in used_target:
                    continue
                if s_obj.color != t_obj.color:
                    continue
                score = 0.0
                if s_obj.normalized_shape == t_obj.normalized_shape:
                    score += 10.0
                score -= abs(s_obj.area - t_obj.area) * 0.1
                if score > best_score:
                    best_score = score
                    best_t = t_obj
            if best_t is not None and best_score >= 5.0:
                used_target.add(best_t.object_id)
                mappings.append(
                    {
                        "source_id": s_obj.object_id,
                        "target_id": best_t.object_id,
                        "score": best_score,
                        "source": s_obj,
                        "target": best_t,
                    }
                )
        return mappings
