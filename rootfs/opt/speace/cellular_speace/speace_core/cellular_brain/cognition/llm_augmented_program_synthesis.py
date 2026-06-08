"""LLM-Augmented Program Synthesis (LLM-APS).

When the symbolic engine produces zero candidates, this module asks the
LinguisticCorticalBridge (local LLM) for a textual description of the
transformation, parses it into primitives, and validates the result.

Governance:
- All LLM proposals are simulate-only and require human approval unless
  evaluation_mode=True.
"""

import asyncio
import inspect
from typing import Any, Dict, List, Optional

from speace_core.cellular_brain.cognition.program_models import (
    GridTransformation,
    TransformationProgram,
    ProgramCandidate,
    _PRIMITIVE_REGISTRY,
)

Grid = List[List[int]]


class LLMAugmentedProgramSynthesis:
    """Uses the LinguisticCorticalBridge to suggest transformations when
    pure symbolic search fails."""

    def __init__(
        self,
        bridge: Any,
        primitive_registry: Optional[Dict[str, Any]] = None,
        meta_composer: Optional[Any] = None,
        evaluation_mode: bool = False,
    ) -> None:
        self.bridge = bridge
        self.primitive_registry = primitive_registry or _PRIMITIVE_REGISTRY
        self.meta_composer = meta_composer
        self.evaluation_mode = evaluation_mode

    # ------------------------------------------------------------------ #
    # Prompt building
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fmt_grid(grid: Grid) -> str:
        return "\n".join(" ".join(str(c) for c in row) for row in grid)

    def build_arc_prompt(self, train_pairs: List[Dict[str, Any]], top_k: int = 2) -> str:
        """Build a textual ARC-style prompt for the LLM."""
        lines = [
            "You are an expert in grid transformations (ARC-AGI).",
            "Given the input/output examples below, describe the transformation",
            "as a short sequence of primitive operations.",
            "Available primitives include: rotate_90, rotate_180, flip_horizontal,",
            "flip_vertical, color_map, translate, symmetry_complete, crop, pad,",
            "fill_holes, outline, copy_object, parametric_color_shift,",
            "parametric_object_replicate, gravity, remove_noise, trim_background,",
            "fill_background, invert_colors, detect_enclosed, compress,",
            "extend_to_boundary, swap_colors, make_symmetric, border.",
            "",
            "Respond ONLY with a comma-separated list of primitive names.",
            "Example: rotate_90, flip_horizontal",
            "",
        ]
        for idx, pair in enumerate(train_pairs[:top_k]):
            lines.append(f"Example {idx + 1}:")
            lines.append("Input:")
            lines.append(self._fmt_grid(pair["input"]))
            lines.append("Output:")
            lines.append(self._fmt_grid(pair["output"]))
            lines.append("")
        lines.append("Transformation:")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Parsing
    # ------------------------------------------------------------------ #

    def parse_llm_program(self, text: str) -> List[GridTransformation]:
        """Extract primitive names from LLM text and map to transformations."""
        text = text.lower()
        transformations: List[GridTransformation] = []
        # Simple token-based extraction: look for known primitive names
        known = sorted(self.primitive_registry.keys(), key=len, reverse=True)
        for name in known:
            if name in text:
                transformations.append(GridTransformation(name=name))
                # Avoid double-counting substrings by removing the matched part
                text = text.replace(name, "", 1)
        # Also handle simple linguistic patterns
        if "rotate 90" in text or "rotate clockwise" in text:
            transformations.append(GridTransformation(name="rotate_90"))
        if "rotate 180" in text:
            transformations.append(GridTransformation(name="rotate_180"))
        if "flip horizontal" in text or "mirror horizontally" in text:
            transformations.append(GridTransformation(name="flip_horizontal"))
        if "flip vertical" in text or "mirror vertically" in text:
            transformations.append(GridTransformation(name="flip_vertical"))
        if "fill holes" in text:
            transformations.append(GridTransformation(name="fill_holes"))
        if "outline" in text:
            transformations.append(GridTransformation(name="outline"))
        return transformations

    # ------------------------------------------------------------------ #
    # Synthesis
    # ------------------------------------------------------------------ #

    def suggest_program(
        self, train_pairs: List[Dict[str, Any]]
    ) -> Optional[ProgramCandidate]:
        """Return a single candidate program via LLM or fallback."""
        if not train_pairs:
            return None

        # Try LLM if available and not in restricted mode
        llm_candidate = self._try_llm(train_pairs)
        if llm_candidate is not None:
            return llm_candidate

        # Fallback: rule-based guided by meta-learning composer
        return self._fallback_rule_based(train_pairs)

    def _try_llm(self, train_pairs: List[Dict[str, Any]]) -> Optional[ProgramCandidate]:
        if not self.evaluation_mode and getattr(self.bridge, "governance", None):
            # In normal mode, LLM proposals require human approval;
            # skip automatically in this low-level module and let the
            # orchestrator handle governance.
            return None

        prompt = self.build_arc_prompt(train_pairs)
        try:
            if inspect.iscoroutinefunction(self.bridge.generate):
                # Run async call synchronously
                result = asyncio.run(self.bridge.generate(prompt, temperature=0.3, max_tokens=128))
            else:
                result = self.bridge.generate(prompt, temperature=0.3, max_tokens=128)
            text = result.get("text", "")
            steps = self.parse_llm_program(text)
            if not steps:
                return None
            prog = TransformationProgram(steps=steps)
            # Validate on all train pairs
            matches = 0
            for pair in train_pairs:
                out = prog.apply(pair["input"])
                if out is not None and out == pair["output"]:
                    matches += 1
            return ProgramCandidate(program=prog, train_matches=matches, confidence=0.7)
        except Exception:
            return None

    def _fallback_rule_based(
        self, train_pairs: List[Dict[str, Any]]
    ) -> Optional[ProgramCandidate]:
        if self.meta_composer is None:
            return None
        # Use guided search with a broad primitive set
        from speace_core.cellular_brain.cognition.few_shot_program_induction_engine import (
            FewShotProgramInductionEngine,
        )
        primitives = [
            GridTransformation(name=n)
            for n in list(self.primitive_registry.keys())[:15]
        ]
        engine = FewShotProgramInductionEngine()
        cands = self.meta_composer.guided_search(
            train_pairs, primitives, engine, max_depth=2, max_candidates=20
        )
        return cands[0] if cands else None
