import pytest

from speace_core.cellular_brain.self_organization.perturbation_scheduler import (
    PerturbationResult,
    PerturbationScheduler,
)


class TestPerturbationScheduler:
    def test_disabled_does_not_activate(self):
        sched = PerturbationScheduler(enabled=False)
        result = sched.apply_noise_injection()
        assert sched.active_count == 0
        assert result.safe is True

    def test_enabled_activates(self):
        sched = PerturbationScheduler(enabled=True)
        result = sched.apply_noise_injection(magnitude=0.2)
        assert sched.active_count == 1
        assert result.magnitude == 0.2

    def test_magnitude_bounded(self):
        sched = PerturbationScheduler(enabled=True)
        result = sched.apply_noise_injection(magnitude=1.5)
        assert result.magnitude == 1.0
        result2 = sched.apply_noise_injection(magnitude=-0.5)
        assert result2.magnitude == 0.0

    def test_max_active_limit(self):
        sched = PerturbationScheduler(enabled=True, max_active_perturbations=2)
        sched.apply_noise_injection()
        sched.apply_mutation_pulse()
        sched.apply_resource_scarcity()
        assert sched.active_count == 2
        assert sched.total_applied == 3

    def test_tick_expires(self):
        sched = PerturbationScheduler(enabled=True, default_duration=1)
        result = sched.apply_noise_injection()
        assert sched.active_count == 1
        expired = sched.tick()
        assert len(expired) == 1
        assert expired[0].reverted is True
        assert sched.active_count == 0

    def test_revert_all(self):
        sched = PerturbationScheduler(enabled=True)
        sched.apply_noise_injection()
        sched.apply_mutation_pulse()
        sched.revert_all()
        assert sched.active_count == 0
        assert sched.total_applied == 2

    def test_get_active_effects(self):
        sched = PerturbationScheduler(enabled=True)
        sched.apply_noise_injection(magnitude=0.2)
        sched.apply_pathway_suppression(magnitude=0.3)
        effects = sched.get_active_effects()
        assert "noise_multiplier" in effects
        assert "routing_multiplier" in effects
        assert effects["routing_multiplier"] == 0.7

    def test_set_recovery_score(self):
        sched = PerturbationScheduler(enabled=True)
        result = sched.apply_noise_injection()
        assert sched.set_recovery_score(result.perturbation_id, 0.8) is True
        assert result.recovery_score == 0.8
        assert sched.set_recovery_score("nonexistent", 0.5) is False

    def test_summary(self):
        sched = PerturbationScheduler(enabled=True)
        sched.apply_noise_injection()
        summary = sched.summary()
        assert summary["enabled"] is True
        assert summary["active_count"] == 1

    def test_perturbation_types(self):
        sched = PerturbationScheduler(enabled=True)
        assert isinstance(sched.apply_noise_injection(), PerturbationResult)
        assert isinstance(sched.apply_pathway_suppression(), PerturbationResult)
        assert isinstance(sched.apply_mutation_pulse(), PerturbationResult)
        assert isinstance(sched.apply_resource_scarcity(), PerturbationResult)
        assert isinstance(sched.apply_plasticity_spike(), PerturbationResult)
        assert isinstance(sched.apply_activation_clamp(), PerturbationResult)
