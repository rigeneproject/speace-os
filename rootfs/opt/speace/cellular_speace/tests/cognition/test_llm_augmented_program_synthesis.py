import pytest

from speace_core.cellular_brain.cognition.llm_augmented_program_synthesis import (
    LLMAugmentedProgramSynthesis,
)
from speace_core.cellular_brain.cognition.program_models import (
    GridTransformation,
    TransformationProgram,
)


class MockGovernance:
    pass


class MockBridge:
    def __init__(self, response: str = "", governance=None) -> None:
        self._response = response
        self.governance = governance

    async def generate(self, prompt: str, **kwargs):
        return {"text": self._response}


class TestLLMAugmentedProgramSynthesis:
    def test_build_arc_prompt(self):
        synth = LLMAugmentedProgramSynthesis(bridge=MockBridge())
        pairs = [
            {
                "input": [[1, 0], [0, 2]],
                "output": [[0, 2], [1, 0]],
            }
        ]
        prompt = synth.build_arc_prompt(pairs)
        assert "rotate_90" in prompt
        assert "1 0" in prompt

    def test_parse_llm_program_simple(self):
        synth = LLMAugmentedProgramSynthesis(bridge=MockBridge())
        text = "First rotate_90, then flip_horizontal and fill_holes"
        steps = synth.parse_llm_program(text)
        names = [s.name for s in steps]
        assert "rotate_90" in names
        assert "flip_horizontal" in names
        assert "fill_holes" in names

    def test_parse_llm_program_linguistic(self):
        synth = LLMAugmentedProgramSynthesis(bridge=MockBridge())
        text = "Rotate 90 degrees clockwise, then flip horizontal"
        steps = synth.parse_llm_program(text)
        names = [s.name for s in steps]
        assert "rotate_90" in names
        assert "flip_horizontal" in names

    def test_suggest_program_llm_mock(self):
        bridge = MockBridge(response="rotate_90, flip_horizontal")
        synth = LLMAugmentedProgramSynthesis(bridge=bridge, evaluation_mode=True)
        pairs = [
            {
                "input": [[0, 1], [2, 0]],
                "output": [[1, 0], [0, 2]],
            }
        ]
        cand = synth.suggest_program(pairs)
        # LLM produced some candidate; not guaranteed to match on this synthetic pair
        assert cand is not None
        assert isinstance(cand.program.steps, list)

    def test_fallback_when_no_evaluation_mode(self):
        bridge = MockBridge(response="rotate_90", governance=MockGovernance())
        synth = LLMAugmentedProgramSynthesis(bridge=bridge, evaluation_mode=False)
        pairs = [
            {
                "input": [[1, 0], [0, 1]],
                "output": [[1, 0], [0, 1]],
            }
        ]
        # Without evaluation_mode and with governance present, LLM is blocked
        cand = synth.suggest_program(pairs)
        assert cand is None
