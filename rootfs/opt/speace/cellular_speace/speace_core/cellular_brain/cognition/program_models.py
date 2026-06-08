"""Shared program-induction models.

Extracted to avoid circular imports between the symbolic engine and
meta-learning / neural-symbolic modules.
"""

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

Grid = List[List[int]]
PrimitiveFn = Callable[[Grid, Dict[str, Any]], Optional[Grid]]

_PRIMITIVE_REGISTRY: Dict[str, PrimitiveFn] = {}


class GridTransformation(BaseModel):
    name: str
    params: Dict[str, Any] = Field(default_factory=dict)

    def apply(self, grid: Grid) -> Optional[Grid]:
        fn = _PRIMITIVE_REGISTRY.get(self.name)
        if fn is None:
            return None
        return fn(grid, self.params)


class TransformationProgram(BaseModel):
    steps: List[GridTransformation] = Field(default_factory=list)

    def apply(self, grid: Grid) -> Optional[Grid]:
        current = grid
        for step in self.steps:
            result = step.apply(current)
            if result is None:
                return None
            current = result
        return current

    @property
    def complexity_score(self) -> int:
        return len(self.steps)


class ProgramCandidate(BaseModel):
    program: TransformationProgram
    train_matches: int = 0
    confidence: float = 0.0
