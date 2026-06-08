import pytest

from speace_core.cellular_brain.self_organization.emergence_metrics import EmergenceMetrics


class TestModularityGain:
    def test_positive_gain(self):
        assert EmergenceMetrics.compute_modularity_gain(0.3, 0.5) == 0.2

    def test_negative_gain(self):
        assert EmergenceMetrics.compute_modularity_gain(0.5, 0.3) == -0.2

    def test_clamped(self):
        assert EmergenceMetrics.compute_modularity_gain(0.0, 2.0) == 1.0
        assert EmergenceMetrics.compute_modularity_gain(1.0, -1.0) == -1.0


class TestSpontaneousAssemblyGrowth:
    def test_growth(self):
        assert EmergenceMetrics.compute_spontaneous_assembly_growth(10, 15) == 0.5

    def test_decline(self):
        assert EmergenceMetrics.compute_spontaneous_assembly_growth(10, 5) == -0.5

    def test_zero_pre(self):
        assert EmergenceMetrics.compute_spontaneous_assembly_growth(0, 0) == 0.0
        assert EmergenceMetrics.compute_spontaneous_assembly_growth(0, 5) == 1.0


class TestSemanticClusterCoherence:
    def test_perfect(self):
        assert EmergenceMetrics.compute_semantic_cluster_coherence([1.0, 1.0, 1.0]) == 1.0

    def test_empty(self):
        assert EmergenceMetrics.compute_semantic_cluster_coherence([]) == 0.0

    def test_mixed(self):
        coh = EmergenceMetrics.compute_semantic_cluster_coherence([0.5, 0.5, 0.5])
        assert coh == 0.5


class TestRegionSpecializationIndex:
    def test_uniform(self):
        assert EmergenceMetrics.compute_region_specialization_index({"a": 0.5, "b": 0.5}) == 0.0

    def test_specialized(self):
        idx = EmergenceMetrics.compute_region_specialization_index({"a": 1.0, "b": 0.0})
        assert idx > 0.4

    def test_empty(self):
        assert EmergenceMetrics.compute_region_specialization_index({}) == 0.0


class TestPostShockRecoveryGain:
    def test_recovery(self):
        gain = EmergenceMetrics.compute_post_shock_recovery_gain(0.1, 0.4, 0.5)
        assert gain > 0.0

    def test_worse(self):
        gain = EmergenceMetrics.compute_post_shock_recovery_gain(0.4, 0.1, 0.5)
        assert gain < 0.0

    def test_zero_baseline(self):
        assert EmergenceMetrics.compute_post_shock_recovery_gain(0.1, 0.4, 0.0) == 0.0


class TestNovelFunctionalPathways:
    def test_net_positive(self):
        assert EmergenceMetrics.compute_novel_functional_pathways(10, 15, 2) == 0.3

    def test_net_negative(self):
        assert EmergenceMetrics.compute_novel_functional_pathways(10, 5, 2) == -0.7

    def test_zero_pre(self):
        assert EmergenceMetrics.compute_novel_functional_pathways(0, 5, 0) == 0.0


class TestCompression:
    def test_full_compression(self):
        assert EmergenceMetrics.compute_compression_of_successful_patterns(10, 10) == 1.0

    def test_half_compression(self):
        assert EmergenceMetrics.compute_compression_of_successful_patterns(10, 5) == 0.5

    def test_zero_patterns(self):
        assert EmergenceMetrics.compute_compression_of_successful_patterns(0, 5) == 0.0


class TestCrossRegionCoordination:
    def test_empty(self):
        assert EmergenceMetrics.compute_cross_region_coordination_score([]) == 0.0

    def test_optimal(self):
        score = EmergenceMetrics.compute_cross_region_coordination_score([0.5])
        assert score == 0.5


class TestSelfOrganizationScore:
    def test_perfect(self):
        score = EmergenceMetrics.compute_self_organization_score(
            modularity_gain=1.0,
            spontaneous_assembly_growth=1.0,
            semantic_cluster_coherence=1.0,
            region_specialization_index=1.0,
            post_shock_recovery_gain=1.0,
            novel_functional_pathways=1.0,
            compression_of_successful_patterns=1.0,
            cross_region_coordination_score=1.0,
        )
        assert score == 1.0

    def test_zero(self):
        score = EmergenceMetrics.compute_self_organization_score(
            modularity_gain=0.0,
            spontaneous_assembly_growth=0.0,
            semantic_cluster_coherence=0.0,
            region_specialization_index=0.0,
            post_shock_recovery_gain=0.0,
            novel_functional_pathways=0.0,
            compression_of_successful_patterns=0.0,
            cross_region_coordination_score=0.0,
        )
        assert score == 0.0


class TestMeasureCycle:
    def test_measure_pre_post(self):
        em = EmergenceMetrics()
        em.measure_pre(modularity=0.3, assembly_count=10, phi=0.2, pathway_count=20)
        result = em.measure_post(
            modularity=0.4,
            assembly_count=12,
            phi=0.35,
            pathway_count=22,
            pruned_count=1,
            baseline_phi=0.4,
        )
        assert "self_organization_score" in result
        assert result["modularity_gain"] == 0.1
        assert result["post_shock_recovery_gain"] > 0.0
        assert em.latest() == result

    def test_summary(self):
        em = EmergenceMetrics()
        em.measure_pre(modularity=0.3, assembly_count=10, phi=0.2, pathway_count=20)
        em.measure_post(modularity=0.3, assembly_count=10, phi=0.2, pathway_count=20)
        summary = em.summary()
        assert summary["history_length"] == 1
        assert "mean_self_organization_score" in summary
