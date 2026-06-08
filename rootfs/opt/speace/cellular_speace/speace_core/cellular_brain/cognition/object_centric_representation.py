"""Object-Centric Representation — slot-based scene abstraction for SPEACE.

Moves beyond raw pixel grids to object-level slot representations,
enabling slot-level reasoning, abstraction, and composition.

Integrates with:
  - SpatialSymbolicReasoningLayer (object extraction)
  - FewShotProgramInductionEngine (slot-level primitives)
  - ARC-AGI Adapter (scene-level evaluation)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

# ------------------------------------------------------------------ #
# ObjectSlot — a single object with identity, mask, attributes
# ------------------------------------------------------------------ #


class ObjectSlot(BaseModel):
    """A single object slot with persistent identity and attributes.

    Each slot represents one entity in a scene, with full mask,
    bounding box, and derived properties for downstream reasoning.
    """

    slot_id: str
    task_id: str = ""
    color: int = 0
    pixels: List[Tuple[int, int]] = Field(default_factory=list)
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)
    area: int = 0
    centroid: Tuple[float, float] = (0.0, 0.0)
    normalized_shape: Tuple[int, ...] = ()
    confidence: float = 1.0
    parent_slot_id: Optional[str] = None
    child_slot_ids: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)

    def compute_attributes(self) -> None:
        self.area = len(self.pixels)
        if self.pixels:
            ys = [p[0] for p in self.pixels]
            xs = [p[1] for p in self.pixels]
            min_y, max_y = min(ys), max(ys)
            min_x, max_x = min(xs), max(xs)
            self.bbox = (min_y, min_x, max_y - min_y + 1, max_x - min_x + 1)
            cy = sum(ys) / self.area
            cx = sum(xs) / self.area
            self.centroid = (cy, cx)
        h, w = self.bbox[2], self.bbox[3]
        sym = "tall" if h > w else ("wide" if w > h else "square")
        ratio = round(h / w, 2) if w > 0 else 0.0
        self.attributes.update({
            "height": h,
            "width": w,
            "area": self.area,
            "aspect_ratio": ratio,
            "shape_category": sym,
            "density": self.area / max(1, h * w),
            "color_name": str(self.color),
            "centroid_x": int(self.centroid[1]),
            "centroid_y": int(self.centroid[0]),
        })

    @property
    def position_key(self) -> str:
        return f"{int(self.centroid[0])}_{int(self.centroid[1])}"


# ------------------------------------------------------------------ #
# ObjectCentricScene — a grid represented as a collection of slots
# ------------------------------------------------------------------ #


class ObjectCentricScene(BaseModel):
    """A full scene represented by object slots instead of raw grid."""

    scene_id: str = ""
    width: int = 0
    height: int = 0
    slots: List[ObjectSlot] = Field(default_factory=list)
    background_color: int = 0
    relations: Dict[str, List[str]] = Field(default_factory=dict)

    def get_slot(self, slot_id: str) -> Optional[ObjectSlot]:
        for s in self.slots:
            if s.slot_id == slot_id:
                return s
        return None

    def get_slots_by_color(self, color: int) -> List[ObjectSlot]:
        return [s for s in self.slots if s.color == color]

    def get_slots_by_attribute(self, key: str, value: Any) -> List[ObjectSlot]:
        return [s for s in self.slots if s.attributes.get(key) == value]

    def slot_count(self) -> int:
        return len(self.slots)

    def reconstruct_grid(self) -> List[List[int]]:
        grid = [[self.background_color] * self.width for _ in range(self.height)]
        for slot in self.slots:
            for y, x in slot.pixels:
                if 0 <= y < self.height and 0 <= x < self.width:
                    grid[y][x] = slot.color
        return grid

    def get_slot_mask(self, slot_id: str) -> List[List[int]]:
        mask = [[0] * self.width for _ in range(self.height)]
        slot = self.get_slot(slot_id)
        if slot:
            for y, x in slot.pixels:
                if 0 <= y < self.height and 0 <= x < self.width:
                    mask[y][x] = 1
        return mask

    def sort_slots(self, key: str = "area", reverse: bool = True) -> None:
        if key == "centroid_y":
            self.slots.sort(key=lambda s: s.centroid[0], reverse=reverse)
        elif key == "centroid_x":
            self.slots.sort(key=lambda s: s.centroid[1], reverse=reverse)
        elif key == "color":
            self.slots.sort(key=lambda s: s.color, reverse=reverse)
        elif key == "height":
            self.slots.sort(key=lambda s: s.attributes.get("height", 0), reverse=reverse)
        else:
            self.slots.sort(key=lambda s: s.area, reverse=reverse)


# ------------------------------------------------------------------ #
# ObjectCentricEncoder — builds ObjectCentricScene from GridScene
# ------------------------------------------------------------------ #


class ObjectCentricEncoder:
    """Encodes raw grids / GridScenes into slot-based ObjectCentricScenes.

    Integrates with SpatialSymbolicReasoningLayer for object extraction
    and adds slot-level identity tracking across frames.
    """

    def __init__(self, connectivity: int = 4):
        self._connectivity = connectivity
        self._slot_counter: int = 0

    def encode(
        self,
        grid: List[List[int]],
        scene_id: str = "",
        background: Optional[int] = None,
        existing_slots: Optional[List[ObjectSlot]] = None,
    ) -> ObjectCentricScene:
        if not grid or not grid[0]:
            return ObjectCentricScene(scene_id=scene_id, width=0, height=0)
        h, w = len(grid), len(grid[0])
        bg = background if background is not None else self._infer_background(grid)
        objects = self._extract_objects(grid, bg)
        slots: List[ObjectSlot] = []
        for obj_data in objects:
            color, pixels = obj_data
            self._slot_counter += 1
            slot = ObjectSlot(
                slot_id=f"slot_{self._slot_counter}_{scene_id}",
                task_id=scene_id,
                color=color,
                pixels=pixels,
            )
            slot.compute_attributes()
            if existing_slots:
                match = self._match_slot(slot, existing_slots)
                if match is not None:
                    slot.slot_id = match.slot_id
            slots.append(slot)
        scene = ObjectCentricScene(
            scene_id=scene_id,
            width=w,
            height=h,
            slots=slots,
            background_color=bg,
        )
        self._compute_hierarchy(scene)
        self._compute_relations(scene)
        return scene

    def encode_multiple(
        self,
        grids: List[List[List[int]]],
        base_scene_id: str = "",
        background: Optional[int] = None,
    ) -> List[ObjectCentricScene]:
        scenes: List[ObjectCentricScene] = []
        all_slots: List[ObjectSlot] = []
        for i, grid in enumerate(grids):
            sid = f"{base_scene_id}_{i}" if base_scene_id else f"scene_{i}"
            scene = self.encode(grid, scene_id=sid, background=background, existing_slots=all_slots)
            scenes.append(scene)
        return scenes

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _infer_background(self, grid: List[List[int]]) -> int:
        from collections import Counter
        flat = [c for row in grid for c in row]
        if not flat:
            return 0
        counts = Counter(flat)
        most_common = counts.most_common()
        if not most_common:
            return 0
        top_val, top_count = most_common[0]
        if len(most_common) > 1 and most_common[1][1] == top_count:
            if 0 in counts:
                return 0
        return top_val

    def _extract_objects(self, grid: List[List[int]], background: int) -> List[Tuple[int, List[Tuple[int, int]]]]:
        h, w = len(grid), len(grid[0])
        visited = [[False] * w for _ in range(h)]
        objects: List[Tuple[int, List[Tuple[int, int]]]] = []
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)] if self._connectivity == 4 else [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
        for y in range(h):
            for x in range(w):
                if visited[y][x] or grid[y][x] == background:
                    continue
                color = grid[y][x]
                stack = [(y, x)]
                cells: List[Tuple[int, int]] = []
                while stack:
                    cy, cx = stack.pop()
                    if visited[cy][cx] or grid[cy][cx] != color:
                        continue
                    visited[cy][cx] = True
                    cells.append((cy, cx))
                    for dy, dx in dirs:
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and not visited[ny][nx] and grid[ny][nx] == color:
                            stack.append((ny, nx))
                if cells:
                    objects.append((color, cells))
        return objects

    def _match_slot(self, slot: ObjectSlot, existing: List[ObjectSlot]) -> Optional[ObjectSlot]:
        for ex in existing:
            if ex.color == slot.color:
                intersection = len(set(slot.pixels) & set(ex.pixels))
                if intersection > 0:
                    return ex
                cy_dist = abs(slot.centroid[0] - ex.centroid[0])
                if cy_dist < 3:
                    return ex
        return None

    def _compute_hierarchy(self, scene: ObjectCentricScene) -> None:
        for parent in scene.slots:
            for child in scene.slots:
                if parent.slot_id == child.slot_id:
                    continue
                py_min, px_min, py_max, px_max = parent.bbox
                cy_min, cx_min, cy_max, cx_max = child.bbox
                if py_min <= cy_min and px_min <= cx_min and py_max >= cy_max and px_max >= cx_max:
                    if child.area < parent.area:
                        child.parent_slot_id = parent.slot_id
                        if parent.slot_id not in parent.child_slot_ids:
                            parent.child_slot_ids.append(child.slot_id)

    def _compute_relations(self, scene: ObjectCentricScene) -> None:
        relations: Dict[str, List[str]] = {}
        for i, a in enumerate(scene.slots):
            rels: List[str] = []
            for j, b in enumerate(scene.slots):
                if i == j:
                    continue
                if a.centroid[0] < b.centroid[0] - 1:
                    rels.append(f"above_{b.slot_id}")
                if a.centroid[0] > b.centroid[0] + 1:
                    rels.append(f"below_{b.slot_id}")
                if a.centroid[1] < b.centroid[1] - 1:
                    rels.append(f"left_of_{b.slot_id}")
                if a.centroid[1] > b.centroid[1] + 1:
                    rels.append(f"right_of_{b.slot_id}")
                if abs(a.centroid[0] - b.centroid[0]) < 2 and abs(a.centroid[1] - b.centroid[1]) < 2:
                    rels.append(f"touching_{b.slot_id}")
            relations[a.slot_id] = rels
        scene.relations = relations


# ------------------------------------------------------------------ #
# SlotLevelDiff — what changed per-slot across frames
# ------------------------------------------------------------------ #


class SlotChange(BaseModel):
    slot_id: str
    change_type: str = "unchanged"
    prev_color: int = 0
    new_color: int = 0
    prev_centroid: Tuple[float, float] = (0.0, 0.0)
    new_centroid: Tuple[float, float] = (0.0, 0.0)
    dx: float = 0.0
    dy: float = 0.0
    prev_area: int = 0
    new_area: int = 0
    attributes_changed: Dict[str, Tuple[Any, Any]] = Field(default_factory=dict)


class SlotLevelDiff(BaseModel):
    """Per-slot differences between two ObjectCentricScenes."""

    before: ObjectCentricScene
    after: ObjectCentricScene
    slot_changes: List[SlotChange] = Field(default_factory=list)
    created_slots: List[str] = Field(default_factory=list)
    deleted_slots: List[str] = Field(default_factory=list)

    def compute(self) -> None:
        changes: Dict[str, SlotChange] = {}
        for b_slot in self.before.slots:
            change = SlotChange(slot_id=b_slot.slot_id)
            matched = False
            for a_slot in self.after.slots:
                if a_slot.slot_id == b_slot.slot_id or a_slot.slot_id == "":
                    continue
                inter = len(set(b_slot.pixels) & set(a_slot.pixels))
                if inter > 0 or (abs(b_slot.centroid[0] - a_slot.centroid[0]) < 3 and abs(b_slot.centroid[1] - a_slot.centroid[1]) < 3 and b_slot.color == a_slot.color):
                    matched = True
                    change.new_color = a_slot.color
                    change.new_centroid = a_slot.centroid
                    change.new_area = a_slot.area
                    change.dx = a_slot.centroid[1] - b_slot.centroid[1]
                    change.dy = a_slot.centroid[0] - b_slot.centroid[0]
                    if b_slot.color != a_slot.color:
                        change.change_type = "recolored"
                    elif abs(change.dx) > 1 or abs(change.dy) > 1:
                        change.change_type = "moved"
                    elif b_slot.area != a_slot.area:
                        change.change_type = "resized"
                    else:
                        change.change_type = "unchanged"
                    changes[a_slot.slot_id] = change
                    break
            if not matched:
                change.change_type = "deleted"
                changes[b_slot.slot_id] = change
                self.deleted_slots.append(b_slot.slot_id)
        for a_slot in self.after.slots:
            if a_slot.slot_id not in changes:
                self.created_slots.append(a_slot.slot_id)
                changes[a_slot.slot_id] = SlotChange(
                    slot_id=a_slot.slot_id,
                    change_type="created",
                    new_color=a_slot.color,
                    new_centroid=a_slot.centroid,
                    new_area=a_slot.area,
                )
        self.slot_changes = list(changes.values())

    def has_any_change(self) -> bool:
        return bool(self.created_slots or self.deleted_slots or any(
            c.change_type != "unchanged" for c in self.slot_changes
        ))

    def get_movement_vector(self) -> Optional[Tuple[float, float]]:
        moved = [c for c in self.slot_changes if c.change_type == "moved"]
        if not moved:
            return None
        avg_dx = sum(c.dx for c in moved) / len(moved)
        avg_dy = sum(c.dy for c in moved) / len(moved)
        return (avg_dx, avg_dy)

    def get_recoloring_map(self) -> Dict[int, int]:
        mapping: Dict[int, int] = {}
        for c in self.slot_changes:
            if c.change_type == "recolored":
                mapping[c.prev_color] = c.new_color
        return mapping


# ------------------------------------------------------------------ #
# SceneGraph — relational graph over slots
# ------------------------------------------------------------------ #


class SceneGraphNode(BaseModel):
    slot_id: str
    color: int
    centroid: Tuple[float, float]
    area: int
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SceneGraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "touching"


class SceneGraph(BaseModel):
    nodes: Dict[str, SceneGraphNode] = Field(default_factory=dict)
    edges: List[SceneGraphEdge] = Field(default_factory=list)

    @classmethod
    def from_scene(cls, scene: ObjectCentricScene) -> SceneGraph:
        graph = SceneGraph()
        for slot in scene.slots:
            graph.nodes[slot.slot_id] = SceneGraphNode(
                slot_id=slot.slot_id,
                color=slot.color,
                centroid=slot.centroid,
                area=slot.area,
                attributes=dict(slot.attributes),
            )
        for sid, rels in scene.relations.items():
            for rel in rels:
                parts = rel.split("_", 1)
                if len(parts) == 2:
                    rel_type, target = parts[0], parts[1]
                    if target in graph.nodes:
                        graph.edges.append(SceneGraphEdge(
                            source=sid, target=target, relation=rel_type
                        ))
        return graph
