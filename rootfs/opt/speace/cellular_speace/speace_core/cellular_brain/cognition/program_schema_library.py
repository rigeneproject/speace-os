"""Program Schema Library — reusable program templates for compositional generalization.

Clusters successful programs by transformation type, extracts abstract
schemas (parameterized templates), and enables zero-shot generalization
to semantically similar tasks.

Built on object-centric slot representations for maximum abstraction.
"""

from __future__ import annotations

import json
import time
import math
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from speace_core.cellular_brain.cognition.program_models import (
    GridTransformation,
    TransformationProgram,
)


# ------------------------------------------------------------------ #
# Program Schema — abstract parameterized program template
# ------------------------------------------------------------------ #


class ProgramSchema(BaseModel):
    """An abstract program schema with parameterized slots.

    A schema captures a transformation pattern that can be instantiated
    with different parameters for different tasks. E.g., "recolor the
    largest object and replicate it" becomes a schema with parameters
    {recolor_color, replicate_count, replicate_direction}.
    """

    schema_id: str
    name: str = ""
    transformation_type: str = "unknown"
    steps: List[GridTransformation] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    parameter_defaults: Dict[str, Any] = Field(default_factory=dict)
    task_signature: str = ""
    success_count: int = 0
    avg_pixel_score: float = 0.0
    created_at: float = Field(default_factory=time.time)
    last_used: float = Field(default_factory=time.time)

    def instantiate(self, param_overrides: Dict[str, Any]) -> TransformationProgram:
        steps: List[GridTransformation] = []
        for step in self.steps:
            merged_params = dict(self.parameter_defaults)
            merged_params.update(step.params)
            for k, v in param_overrides.items():
                if k in merged_params:
                    merged_params[k] = v
            steps.append(GridTransformation(name=step.name, params=merged_params))
        return TransformationProgram(steps=steps)


# ------------------------------------------------------------------ #
# Task Signature — lightweight task fingerprint for schema retrieval
# ------------------------------------------------------------------ #


def compute_task_signature(task_pairs: List[Dict]) -> str:
    """Compute a compact signature for a task based on input/output properties."""
    parts: List[str] = []
    h_in, w_in = len(task_pairs[0]["input"]), len(task_pairs[0]["input"][0])
    h_out, w_out = len(task_pairs[0]["output"]), len(task_pairs[0]["output"][0])
    parts.append(f"in_{h_in}x{w_in}")
    parts.append(f"out_{h_out}x{w_out}")
    # Color usage
    in_colors = set()
    out_colors = set()
    for pair in task_pairs[:3]:
        for row in pair["input"]:
            in_colors.update(row)
        for row in pair["output"]:
            out_colors.update(row)
    parts.append(f"cin_{len(in_colors)}")
    parts.append(f"cout_{len(out_colors)}")
    # Size change
    if h_out > h_in or w_out > w_in:
        parts.append("grow")
    elif h_out < h_in or w_out < w_in:
        parts.append("shrink")
    return "_".join(parts)


def compute_signature_similarity(sig_a: str, sig_b: str) -> float:
    """Compute a simple similarity score between two task signatures."""
    parts_a = set(sig_a.split("_")) - {""}
    parts_b = set(sig_b.split("_")) - {""}
    if not parts_a or not parts_b:
        return 0.0
    intersection = parts_a & parts_b
    union = parts_a | parts_b
    return len(intersection) / max(1, len(union))


# ------------------------------------------------------------------ #
# ProgramSchemaLibrary — manages reusable program schemas
# ------------------------------------------------------------------ #


class ProgramSchemaLibrary:
    """Library of reusable program schemas for compositional generalization.

    Features:
    - Extracts schemas from successful programs (cluster by similarity)
    - Retrieves schemas by task signature match
    - Tracks schema usage and success statistics
    - Persists to JSON
    - Enables zero-shot generalization: schema can suggest programs
      for tasks never seen before
    """

    def __init__(self, data_dir: str = "data/schema_library"):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file_path = self._data_dir / "schemas.json"
        self._schemas: Dict[str, ProgramSchema] = {}
        self._lock = Lock()
        self._load()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def add_from_program(
        self,
        program: TransformationProgram,
        task_pairs: List[Dict],
        pixel_score: float = 1.0,
    ) -> Optional[str]:
        """Extract and store a schema from a successful program."""
        if not program.steps:
            return None
        signature = compute_task_signature(task_pairs)
        schema_id = self._make_schema_id(program, signature)

        with self._lock:
            existing = self._schemas.get(schema_id)
            if existing is not None:
                existing.success_count += 1
                existing.avg_pixel_score = (existing.avg_pixel_score * (existing.success_count - 1) + pixel_score) / existing.success_count
                existing.last_used = time.time()
                self._save()
                return schema_id

            params: Dict[str, Any] = {}
            defaults: Dict[str, Any] = {}
            for step in program.steps:
                for k, v in step.params.items():
                    params[k] = type(v).__name__
                    defaults[k] = v

            schema = ProgramSchema(
                schema_id=schema_id,
                name=self._infer_name(program),
                transformation_type=self._infer_type(program),
                steps=[s.model_copy() for s in program.steps],
                parameters=params,
                parameter_defaults=defaults,
                task_signature=signature,
                success_count=1,
                avg_pixel_score=pixel_score,
            )
            self._schemas[schema_id] = schema
            self._save()
            return schema_id

    def get_schemas_for_task(
        self,
        task_pairs: List[Dict],
        min_similarity: float = 0.3,
        top_k: int = 3,
    ) -> List[ProgramSchema]:
        """Retrieve schemas relevant to a task by signature similarity."""
        signature = compute_task_signature(task_pairs)
        scored: List[Tuple[float, ProgramSchema]] = []
        with self._lock:
            for schema in self._schemas.values():
                sim = compute_signature_similarity(signature, schema.task_signature)
                if sim >= min_similarity:
                    scored.append((sim, schema))
        scored.sort(key=lambda x: (-x[0], -x[1].success_count))
        return [s for _, s in scored[:top_k]]

    def suggest_programs(
        self,
        task_pairs: List[Dict],
        top_k: int = 3,
    ) -> List[TransformationProgram]:
        """Suggest candidate programs for a task based on schema library."""
        schemas = self.get_schemas_for_task(task_pairs, top_k=top_k)
        programs: List[TransformationProgram] = []
        for schema in schemas:
            program = schema.instantiate({})
            programs.append(program)
        return programs

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            types: Dict[str, int] = {}
            for s in self._schemas.values():
                types[s.transformation_type] = types.get(s.transformation_type, 0) + 1
            return {
                "total_schemas": len(self._schemas),
                "transformation_types": types,
                "total_successes": sum(s.success_count for s in self._schemas.values()),
            }

    def clear(self) -> None:
        with self._lock:
            self._schemas.clear()
            self._save()

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _make_schema_id(self, program: TransformationProgram, signature: str) -> str:
        names = [s.name for s in program.steps]
        return f"schema_{'_'.join(names)}_{signature[:30]}"

    def _infer_name(self, program: TransformationProgram) -> str:
        names = [s.name for s in program.steps]
        return " + ".join(names[:3])

    def _infer_type(self, program: TransformationProgram) -> str:
        names = [s.name for s in program.steps]
        if any("rotate" in n for n in names):
            return "rotation"
        if any("flip" in n or "symmetry" in n or "mirror" in n for n in names):
            return "symmetry"
        if any("translate" in n or "move" in n for n in names):
            return "translation"
        if any("color_map" in n or "recolor" in n or "swap" in n for n in names):
            return "recoloring"
        if any("tile" in n or "kronecker" in n or "fractal" in n for n in names):
            return "tiling"
        if any("fill" in n or "border" in n or "outline" in n for n in names):
            return "filling"
        if any("gravity" in n or "compress" in n or "trim" in n for n in names):
            return "layout"
        if any("slot" in n for n in names):
            return "object_centric"
        return "composite"

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def _save(self) -> None:
        data = {sid: s.model_dump() for sid, s in self._schemas.items()}
        with open(self._file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _load(self) -> None:
        if not self._file_path.exists():
            return
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for sid, sdata in data.items():
                self._schemas[sid] = ProgramSchema.model_validate(sdata)
        except Exception:
            self._schemas.clear()
