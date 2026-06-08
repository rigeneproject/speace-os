"""Tests for T130 — Cognitive Strategy Evaluator."""

from speace_core.cellular_brain.metacognition.cognitive_strategy_evaluator import (
    CognitiveStrategyEvaluator,
)


def test_record_outcome_improved():
    eval_ = CognitiveStrategyEvaluator()
    result = eval_.record_outcome("increase stability bias", pre_health=0.3, post_health=0.9)
    assert result.improved is True
    assert abs(result.delta - 0.6) < 1e-9


def test_record_outcome_not_improved():
    eval_ = CognitiveStrategyEvaluator()
    result = eval_.record_outcome("increase stability bias", pre_health=0.8, post_health=0.82)
    assert result.improved is False


def test_evaluate_strategy_effective():
    eval_ = CognitiveStrategyEvaluator()
    for _ in range(10):
        eval_.record_outcome("increase stability bias", pre_health=0.3, post_health=0.9)
    verdict = eval_.evaluate_strategy("increase stability bias")
    assert verdict["verdict"] == "effective"
    assert verdict["success_rate"] == 1.0


def test_evaluate_strategy_ineffective():
    eval_ = CognitiveStrategyEvaluator()
    for _ in range(10):
        eval_.record_outcome("increase stability bias", pre_health=0.8, post_health=0.75)
    verdict = eval_.evaluate_strategy("increase stability bias")
    assert verdict["verdict"] == "ineffective"


def test_evaluate_all():
    eval_ = CognitiveStrategyEvaluator()
    eval_.record_outcome("strategy_a", pre_health=0.3, post_health=0.9)
    eval_.record_outcome("strategy_b", pre_health=0.8, post_health=0.75)
    all_ = eval_.evaluate_all()
    assert "strategy_a" in all_
    assert "strategy_b" in all_


def test_best_strategy():
    eval_ = CognitiveStrategyEvaluator()
    eval_.record_outcome("good", pre_health=0.2, post_health=0.9)
    eval_.record_outcome("bad", pre_health=0.8, post_health=0.7)
    assert eval_.best_strategy() == "good"


def test_trend_for_strategy():
    eval_ = CognitiveStrategyEvaluator()
    eval_.record_outcome("s", pre_health=0.3, post_health=0.5)
    eval_.record_outcome("s", pre_health=0.5, post_health=0.7)
    trend = eval_.trend_for_strategy("s")
    assert len(trend) == 2
    assert abs(trend[0] - 0.2) < 1e-9
    assert abs(trend[1] - 0.2) < 1e-9
