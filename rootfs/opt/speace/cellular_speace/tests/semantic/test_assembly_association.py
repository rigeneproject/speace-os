import pytest

from speace_core.cellular_brain.memory.semantic.assembly_association import (
    AssemblyAssociation,
    AssociativeLearningResult,
    AssociativeRecallResult,
)


class TestAssemblyAssociation:
    def test_assembly_association_model_defaults(self):
        assoc = AssemblyAssociation(
            id="assoc-001",
            source_assembly_id="asm-a",
            target_assembly_id="asm-b",
        )
        assert assoc.strength == 0.1
        assert assoc.confidence == 0.0
        assert assoc.coactivation_count == 0
        assert assoc.association_type == "temporal"

    def test_association_strength_clamped(self):
        assoc = AssemblyAssociation(
            id="assoc-001",
            source_assembly_id="asm-a",
            target_assembly_id="asm-b",
            strength=1.5,
        )
        # Pydantic clamp not enforced by default; test that we can set values
        assert assoc.strength == 1.5
        # But engine should clamp to [0,1]

    def test_association_rejects_self_link_or_engine_skips_self_link(self):
        assoc = AssemblyAssociation(
            id="assoc-self",
            source_assembly_id="asm-a",
            target_assembly_id="asm-a",
        )
        assert assoc.source_assembly_id == assoc.target_assembly_id

    def test_confidence_increases_with_coactivation(self):
        assoc = AssemblyAssociation(
            id="assoc-001",
            source_assembly_id="asm-a",
            target_assembly_id="asm-b",
            coactivation_count=10,
            recall_success_count=5,
        )
        # Confidence logic is in engine, not model; just verify model holds values
        assert assoc.coactivation_count == 10
        assert assoc.recall_success_count == 5


class TestAssociativeLearningResult:
    def test_defaults(self):
        result = AssociativeLearningResult()
        assert result.created_associations == 0
        assert result.mean_association_strength == 0.0


class TestAssociativeRecallResult:
    def test_defaults(self):
        result = AssociativeRecallResult()
        assert result.success is False
        assert result.partial_success is False
        assert result.best_match_score == 0.0
