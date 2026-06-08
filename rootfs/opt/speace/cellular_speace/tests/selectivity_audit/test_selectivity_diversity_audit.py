import pytest

from speace_core.cellular_brain.selectivity_audit.selectivity_diversity_audit import (
    SelectivityDiversityAudit,
)


def test_audit_empty():
    audit = SelectivityDiversityAudit()
    report = audit.audit([])
    assert report.total_neurons == 0
    assert report.diversity_score == 0.0


def test_audit_uniform():
    audit = SelectivityDiversityAudit()
    # All neurons have the same selectivity -> low diversity
    indices = [0.5] * 10
    report = audit.audit(indices)
    assert report.mean_selectivity == pytest.approx(0.5)
    assert report.entropy == pytest.approx(0.0)
    assert report.gini_index == pytest.approx(0.0)
    assert report.diversity_score == pytest.approx(0.2)


def test_audit_diverse():
    audit = SelectivityDiversityAudit()
    indices = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    report = audit.audit(indices)
    assert report.mean_selectivity > 0.0
    assert report.entropy > 0.0
    assert report.cv_selectivity > 0.0
    assert report.diversity_score > 0.0
    assert report.specialized_neurons >= 1


def test_audit_specialized_count():
    audit = SelectivityDiversityAudit(specialization_threshold=0.7)
    indices = [0.1, 0.3, 0.8, 0.9]
    report = audit.audit(indices)
    assert report.specialized_neurons == 2


def test_gini_perfect_equality():
    audit = SelectivityDiversityAudit()
    gini = audit._compute_gini([1.0, 1.0, 1.0])
    assert gini == pytest.approx(0.0)


def test_gini_max_inequality():
    audit = SelectivityDiversityAudit()
    gini = audit._compute_gini([0.0, 0.0, 10.0])
    assert gini > 0.0
