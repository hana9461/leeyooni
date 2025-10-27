"""
Unit Tests for Trust Score Aggregation
"""

import pytest
import math
from src.core.trust_aggregation import (
    geometric_mean,
    harmonic_mean,
    arithmetic_mean,
    capped_mean,
    weighted_mean,
    logistic_blend,
    min_mean_hybrid,
    validate_factors,
    clamp_factors,
    TrustScoreBuilder,
)


class TestAggregationMethods:
    """Test monotone aggregation methods."""

    def test_geometric_mean_basic(self):
        """Test geometric mean with simple factors."""
        factors = [0.8, 0.6, 0.9]
        trust = geometric_mean(factors)

        assert 0.0 <= trust <= 1.0
        # Geometric mean should be between min and max
        assert min(factors) <= trust <= max(factors)

    def test_geometric_mean_all_ones(self):
        """Test geometric mean with all 1.0."""
        factors = [1.0, 1.0, 1.0]
        trust = geometric_mean(factors)
        assert trust == 1.0

    def test_geometric_mean_all_zeros(self):
        """Test geometric mean with all near-zero."""
        factors = [0.01, 0.01, 0.01]
        trust = geometric_mean(factors)
        assert 0.0 <= trust <= 1.0

    def test_geometric_mean_monotone(self):
        """Test that geometric mean is monotone."""
        # Increase any factor should not decrease result
        base = [0.5, 0.5, 0.5]
        base_trust = geometric_mean(base)

        increased = [0.6, 0.5, 0.5]
        increased_trust = geometric_mean(increased)

        assert increased_trust >= base_trust

    def test_harmonic_mean_basic(self):
        """Test harmonic mean."""
        factors = [0.8, 0.6, 0.9]
        trust = harmonic_mean(factors)

        assert 0.0 <= trust <= 1.0
        # Harmonic mean is ≤ geometric mean
        geo = geometric_mean(factors)
        assert trust <= geo

    def test_harmonic_mean_penalizes_weak(self):
        """Test that harmonic mean penalizes weak factors."""
        strong = [0.99, 0.99, 0.99]
        weak = [0.99, 0.99, 0.3]

        strong_trust = harmonic_mean(strong)
        weak_trust = harmonic_mean(weak)

        # Weak factor should significantly impact harmonic mean
        assert weak_trust < strong_trust
        assert (strong_trust - weak_trust) > 0.2

    def test_arithmetic_mean_basic(self):
        """Test arithmetic mean."""
        factors = [0.8, 0.6, 0.9]
        trust = arithmetic_mean(factors)

        expected = (0.8 + 0.6 + 0.9) / 3
        assert abs(trust - expected) < 1e-6

    def test_arithmetic_mean_scale(self):
        """Test arithmetic mean scale."""
        factors = [0.0, 0.5, 1.0]
        trust = arithmetic_mean(factors)

        assert trust == 0.5

    def test_capped_mean_cap_applied(self):
        """Test capped mean respects cap."""
        factors = [0.99, 0.99, 0.99]
        trust = capped_mean(factors, cap=0.95)

        assert trust == 0.95

    def test_capped_mean_below_cap(self):
        """Test capped mean when below cap."""
        factors = [0.7, 0.7, 0.7]
        trust = capped_mean(factors, cap=0.95)

        assert abs(trust - 0.7) < 1e-6  # Allow for floating point precision

    def test_weighted_mean_equal_weights(self):
        """Test weighted mean with equal weights."""
        factors = [0.8, 0.6, 0.9]
        weights = [1.0, 1.0, 1.0]
        trust = weighted_mean(factors, weights)

        expected = arithmetic_mean(factors)
        assert abs(trust - expected) < 1e-6

    def test_weighted_mean_custom_weights(self):
        """Test weighted mean with custom weights."""
        factors = [0.8, 0.6]
        weights = [2.0, 1.0]
        trust = weighted_mean(factors, weights)

        expected = (0.8 * 2 + 0.6 * 1) / 3
        assert abs(trust - expected) < 1e-6

    def test_weighted_mean_zero_weight(self):
        """Test weighted mean with zero weight (ignored factor)."""
        factors = [0.0, 1.0]  # First factor is 0 (bad)
        weights = [0.0, 1.0]  # But it has zero weight

        trust = weighted_mean(factors, weights)
        assert trust == 1.0

    def test_logistic_blend_basic(self):
        """Test logistic blend aggregation."""
        factors = [0.8, 0.6, 0.9]
        trust = logistic_blend(factors)

        assert 0.0 <= trust <= 1.0

    def test_logistic_blend_sharpness(self):
        """Test logistic blend with different sharpness."""
        factors = [0.6, 0.7, 0.8]

        # Higher sharpness = more aggressive response
        trust_low = logistic_blend(factors, sharpness=2.0)
        trust_high = logistic_blend(factors, sharpness=10.0)

        # Both should be in range
        assert 0.0 <= trust_low <= 1.0
        assert 0.0 <= trust_high <= 1.0

    def test_logistic_blend_monotone(self):
        """Test that logistic blend is monotone."""
        base = [0.5, 0.5, 0.5]
        base_trust = logistic_blend(base)

        increased = [0.6, 0.5, 0.5]
        increased_trust = logistic_blend(increased)

        assert increased_trust >= base_trust

    def test_min_mean_hybrid_basic(self):
        """Test min-mean hybrid."""
        factors = [0.9, 0.6, 0.8]
        trust = min_mean_hybrid(factors, min_weight=0.3)

        assert 0.0 <= trust <= 1.0
        # Should be between min and mean
        min_factor = min(factors)
        mean_factor = sum(factors) / len(factors)
        assert min_factor <= trust <= mean_factor

    def test_min_mean_hybrid_weak_link(self):
        """Test that hybrid penalizes weak factor."""
        strong = [0.95, 0.95, 0.95]
        weak = [0.95, 0.95, 0.3]

        strong_trust = min_mean_hybrid(strong, min_weight=0.5)
        weak_trust = min_mean_hybrid(weak, min_weight=0.5)

        # Weak factor should reduce trust
        assert weak_trust < strong_trust


class TestFactorValidation:
    """Test factor validation functions."""

    def test_validate_factors_valid(self):
        """Test validation with valid factors."""
        factors = [0.0, 0.5, 1.0]
        assert validate_factors(factors) is True

    def test_validate_factors_invalid_high(self):
        """Test validation with out-of-range high."""
        factors = [0.5, 1.5]
        assert validate_factors(factors) is False

    def test_validate_factors_invalid_low(self):
        """Test validation with out-of-range low."""
        factors = [-0.1, 0.5]
        assert validate_factors(factors) is False

    def test_validate_factors_empty(self):
        """Test validation with empty list."""
        assert validate_factors([]) is False

    def test_clamp_factors(self):
        """Test factor clamping."""
        factors = [0.5, 1.5, -0.1]
        clamped = clamp_factors(factors)

        assert clamped == [0.5, 1.0, 0.0]
        assert all(0.0 <= f <= 1.0 for f in clamped)


class TestTrustScoreBuilder:
    """Test TrustScoreBuilder pattern."""

    def test_builder_basic(self):
        """Test basic builder usage."""
        builder = TrustScoreBuilder()
        builder.add_factor("factor1", 0.8)
        builder.add_factor("factor2", 0.6)

        trust = builder.compute(method="arithmetic_mean")
        assert abs(trust - 0.7) < 1e-6

    def test_builder_chaining(self):
        """Test builder method chaining."""
        trust = (
            TrustScoreBuilder()
            .add_factor("a", 0.8)
            .add_factor("b", 0.6)
            .compute(method="geometric_mean")
        )

        assert 0.0 <= trust <= 1.0

    def test_builder_add_factors_kwargs(self):
        """Test adding multiple factors at once."""
        builder = TrustScoreBuilder()
        builder.add_factors(factor1=0.8, factor2=0.6, factor3=0.9)

        assert len(builder.factors_dict()) == 3

    def test_builder_compute_methods(self):
        """Test all compute methods."""
        builder = TrustScoreBuilder()
        builder.add_factors(a=0.7, b=0.8, c=0.6)

        methods = [
            "geometric_mean",
            "harmonic_mean",
            "arithmetic_mean",
            "capped_mean",
            "logistic_blend",
            "min_mean_hybrid",
        ]

        for method in methods:
            trust = builder.compute(method=method)
            assert 0.0 <= trust <= 1.0, f"Method {method} out of range: {trust}"

    def test_builder_weighted_compute(self):
        """Test builder with weighted compute."""
        builder = TrustScoreBuilder()
        builder.add_factors(vwap=0.8, volatility=0.6, volume=0.9)

        weights = {"vwap": 2.0, "volatility": 1.0, "volume": 1.0}

        trust = builder.compute_with_weights(
            method="weighted_mean",
            weights=weights
        )

        assert 0.0 <= trust <= 1.0

    def test_builder_reset(self):
        """Test builder reset."""
        builder = TrustScoreBuilder()
        builder.add_factors(a=0.5, b=0.6)
        assert len(builder.factors_dict()) == 2

        builder.reset()
        assert len(builder.factors_dict()) == 0

    def test_builder_out_of_range_factor(self):
        """Test builder clamps out-of-range factors."""
        builder = TrustScoreBuilder()
        builder.add_factor("invalid", 1.5)

        # Should be clamped to 1.0
        assert builder.factors_dict()["invalid"] == 1.0


class TestMonotoneProperty:
    """Test monotone property of aggregation methods."""

    def test_all_methods_monotone(self):
        """Test that all aggregation methods are monotone."""
        base = [0.5, 0.5, 0.5]
        methods = [
            ("geometric_mean", geometric_mean),
            ("harmonic_mean", harmonic_mean),
            ("arithmetic_mean", arithmetic_mean),
            ("logistic_blend", logistic_blend),
            ("min_mean_hybrid", min_mean_hybrid),
        ]

        base_trusts = {}
        for name, func in methods:
            base_trusts[name] = func(base)

        # Increase each factor position
        for i in range(len(base)):
            increased = base.copy()
            increased[i] = 0.7  # Increase from 0.5 to 0.7

            for name, func in methods:
                increased_trust = func(increased)
                base_trust = base_trusts[name]

                assert increased_trust >= base_trust, \
                    f"{name} not monotone: base={base_trust}, increased={increased_trust}"


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_factors(self):
        """Test aggregation with empty factors."""
        assert geometric_mean([]) == 0.5
        assert harmonic_mean([]) == 0.5
        assert arithmetic_mean([]) == 0.5

    def test_single_factor(self):
        """Test aggregation with single factor."""
        assert geometric_mean([0.7]) == 0.7
        assert harmonic_mean([0.7]) == 0.7
        assert arithmetic_mean([0.7]) == 0.7

    def test_mixed_scales(self):
        """Test that clamping handles out-of-range factors."""
        factors = [0.5, 1.5, -0.1]
        clamped = clamp_factors(factors)

        trust = geometric_mean(clamped)
        assert 0.0 <= trust <= 1.0
