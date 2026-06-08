"""Object-Centric Induction Bridge — connects OCR to FSPI.

Generates slot-level transformation hypotheses from scene-graph
differences, feeds them as primitive candidates to the FSPI engine,
and re-ranks FSPI candidates using object-centric confidence scoring.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from speace_core.cellular_brain.cognition.object_centric_representation import (
    ObjectCentricEncoder,
    ObjectCentricScene,
    ObjectSlot,
    SlotLevelDiff,
)
from speace_core.cellular_brain.cognition.program_models import (
    GridTransformation,
    ProgramCandidate,
    TransformationProgram,
    _PRIMITIVE_REGISTRY,
)

logger = logging.getLogger(__name__)
Grid = List[List[int]]


class ObjectCentricInductionBridge:
    """Bridge between Object-Centric Representation and FSPI.

    Responsibilities:
    1. Generate slot-level transformation hypotheses from scene diffs.
    2. Convert scene-graph differences into primitive candidate programs.
    3. Re-rank FSPI candidates using object-level confidence scoring.
    4. Provide slot-aware pixel scoring for more semantic accuracy.
    """

    def __init__(self, connectivity: int = 4) -> None:
        self._encoder = ObjectCentricEncoder(connectivity=connectivity)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_hypotheses(
        self,
        train_pairs: List[Dict[str, Any]],
    ) -> List[GridTransformation]:
        """Generate slot-level transformation hypotheses from training pairs.

        Analyzes scene-graph differences between input and output for
        each pair, and proposes slot-level primitives that could explain
        the transformation.
        """
        if not train_pairs:
            return []

        hypotheses: List[GridTransformation] = []
        seen: set = set()

        for pair in train_pairs:
            inp, out = pair["input"], pair["output"]
            scene_in = self._encoder.encode(inp)
            scene_out = self._encoder.encode(out)
            diff = SlotLevelDiff(before=scene_in, after=scene_out)
            diff.compute()

            # 1. Color change hypothesis
            recolor_map = diff.get_recoloring_map()
            if recolor_map:
                for old_c, new_c in recolor_map.items():
                    hyp = GridTransformation(
                        name="color_map",
                        params={"mapping": {str(old_c): new_c}},
                    )
                    key = f"color_map_{old_c}_{new_c}"
                    if key not in seen:
                        seen.add(key)
                        hypotheses.append(hyp)

            # 2. Object count change → replicate or remove
            added = len(diff.created_slots)
            removed = len(diff.deleted_slots)

            if added > 0 and removed == 0:
                hyp = GridTransformation(
                    name="slot_replicate_by_count",
                    params={"count": added, "dx": 1, "dy": 0},
                )
                key = f"replicate_{added}"
                if key not in seen:
                    seen.add(key)
                    hypotheses.append(hyp)

            if removed > 0 and added == 0:
                hyp = GridTransformation(
                    name="slot_remove_by_predicate",
                    params={"attribute": "area", "comparison": "less_than", "value": 3},
                )
                key = "remove_small"
                if key not in seen:
                    seen.add(key)
                    hypotheses.append(hyp)

            # 3. Slot count unchanged → attribute-based transformation
            unchanged = [c for c in diff.slot_changes if c.change_type == "unchanged"]
            if len(unchanged) == len(scene_in.slots) and len(scene_in.slots) > 0:
                areas_in = [s.area for s in scene_in.slots]
                areas_out = [s.area for s in scene_out.slots]
                colors_in = [s.color for s in scene_in.slots]
                colors_out = [s.color for s in scene_out.slots]

                if colors_in != colors_out and areas_in == areas_out:
                    hyp = GridTransformation(
                        name="slot_recolor_by_attr",
                        params={"attribute": "area", "threshold": max(areas_in) / 2,
                                "color_if_above": max(set(colors_out), key=colors_out.count),
                                "color_if_below": min(set(colors_out), key=colors_out.count)},
                    )
                    key = "recolor_by_area"
                    if key not in seen:
                        seen.add(key)
                        hypotheses.append(hyp)

                # Position-based: check centroid shifts
                centroids_in = [s.centroid for s in scene_in.slots]
                centroids_out = [s.centroid for s in scene_out.slots]
                if centroids_in != centroids_out:
                    dx = int(centroids_out[0][1] - centroids_in[0][1]) if centroids_in and centroids_out else 0
                    dy = int(centroids_out[0][0] - centroids_in[0][0]) if centroids_in and centroids_out else 0
                    if dx != 0 or dy != 0:
                        hyp = GridTransformation(
                            name="translate",
                            params={"dx": dx, "dy": dy},
                        )
                        key = f"translate_{dx}_{dy}"
                        if key not in seen:
                            seen.add(key)
                            hypotheses.append(hyp)

            # 4. Object count halved → remove by predicate
            if len(scene_out.slots) == len(scene_in.slots) / 2 and len(scene_in.slots) > 0:
                hyp = GridTransformation(
                    name="slot_remove_by_predicate",
                    params={"attribute": "area", "comparison": "less_than", "value": 5},
                )
                key = "remove_half"
                if key not in seen:
                    seen.add(key)
                    hypotheses.append(hyp)

        return hypotheses

    def score_with_slots(
        self,
        program: TransformationProgram,
        train_pairs: List[Dict[str, Any]],
    ) -> float:
        """Score a program using object-centric pixel accuracy.

        Compares input/output at the slot level rather than raw pixels.
        A program scores higher if it preserves object identities and
        correctly transforms each slot.
        """
        if not train_pairs:
            return 0.0

        total_score = 0.0
        for pair in train_pairs:
            inp, expected = pair["input"], pair["output"]
            result = program.apply(inp)
            if result is None:
                continue

            scene_expected = self._encoder.encode(expected)
            scene_result = self._encoder.encode(result)

            # Slot-level match: count how many result slots match expected slots
            expected_slots = {s.slot_id: s for s in scene_expected.slots}
            matched = 0
            for r_slot in scene_result.slots:
                best_overlap = 0
                for e_slot in scene_expected.slots:
                    intersection = len(set(r_slot.pixels) & set(e_slot.pixels))
                    if intersection > best_overlap:
                        best_overlap = intersection
                if best_overlap >= max(1, r_slot.area * 0.5):
                    matched += 1

            slot_acc = matched / max(1, len(scene_expected.slots))

            # Pixel-level accuracy as complement
            h, w = len(expected), len(expected[0])
            correct = 0
            total = h * w
            for y in range(h):
                for x in range(w):
                    if y < len(result) and x < len(result[0]) and result[y][x] == expected[y][x]:
                        correct += 1
            pixel_acc = correct / max(1, total)

            total_score += 0.6 * slot_acc + 0.4 * pixel_acc

        return total_score / len(train_pairs)

    def rerank_with_slots(
        self,
        candidates: List[ProgramCandidate],
        train_pairs: List[Dict[str, Any]],
    ) -> List[ProgramCandidate]:
        """Re-rank candidates using slot-level confidence scoring."""
        if not candidates:
            return candidates

        scored: List[Tuple[float, ProgramCandidate]] = []
        for cand in candidates:
            slot_score = self.score_with_slots(cand.program, train_pairs)
            combined = 0.3 * cand.confidence + 0.7 * slot_score
            scored.append((combined, cand))

        scored.sort(key=lambda x: -x[0])
        return [ProgramCandidate(program=c.program, train_matches=c.train_matches, confidence=s)
                for s, c in scored]
