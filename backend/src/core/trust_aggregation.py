"""
Trust Score Aggregation Module
Monotone aggregation functions for combining normalized factors into Trust scores.

All aggregation methods are monotone (increasing in all inputs) to ensure
that improving any factor never decreases the overall Trust score.
"""

from typing import List, Optional
import math
import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# MONOTONE AGGREGATION METHODS
# ============================================================================

def geometric_mean(factors: List[float]) -> float:
    """
    Aggregate factors using geometric mean.

    Geometric mean is monotone, stable, and gives equal weight to all factors.
    Less sensitive to outliers compared to arithmetic mean.

    Formula: (f1 * f2 * ... * fn) ^ (1/n)

    Args:
        factors: List of factors ∈ [0, 1]

    Returns:
        Trust score ∈ [0, 1]

    Examples:
        >>> geometric_mean([0.8, 0.6, 0.9])
        0.755
    """
    if not factors:
        return 0.5

    if any(f < 0 or f > 1 for f in factors):
        logger.warning(f"Factors out of range: {factors}")
        factors = [max(0.0, min(1.0, f)) for f in factors]

    # Handle zero factors gracefully
    if any(f == 0.0 for f in factors):
        # If any factor is 0, geometric mean is 0
        # But we can use a small epsilon to avoid harsh penalty
        factors = [max(0.01, f) for f in factors]

    product = 1.0
    for factor in factors:
        product *= factor

    trust = product ** (1.0 / len(factors))
    return max(0.0, min(1.0, trust))


def harmonic_mean(factors: List[float]) -> float:
    """
    Aggregate factors using harmonic mean.

    Harmonic mean is monotone and conservative—it penalizes any single
    weak factor more than geometric mean does.

    Formula: n / (1/f1 + 1/f2 + ... + 1/fn)

    Args:
        factors: List of factors ∈ [0, 1]

    Returns:
        Trust score ∈ [0, 1]

    Examples:
        >>> harmonic_mean([0.8, 0.6, 0.9])
        0.721
    """
    if not factors:
        return 0.5

    if any(f < 0 or f > 1 for f in factors):
        logger.warning(f"Factors out of range: {factors}")
        factors = [max(0.0, min(1.0, f)) for f in factors]

    # Avoid division by zero
    factors = [max(0.01, f) for f in factors]

    reciprocal_sum = sum(1.0 / f for f in factors)
    trust = len(factors) / reciprocal_sum

    return max(0.0, min(1.0, trust))


def arithmetic_mean(factors: List[float]) -> float:
    """
    Aggregate factors using simple arithmetic mean.

    Arithmetic mean is monotone and simple. Least resistant to outliers.

    Formula: (f1 + f2 + ... + fn) / n

    Args:
        factors: List of factors ∈ [0, 1]

    Returns:
        Trust score ∈ [0, 1]

    Examples:
        >>> arithmetic_mean([0.8, 0.6, 0.9])
        0.767
    """
    if not factors:
        return 0.5

    if any(f < 0 or f > 1 for f in factors):
        logger.warning(f"Factors out of range: {factors}")
        factors = [max(0.0, min(1.0, f)) for f in factors]

    trust = sum(factors) / len(factors)
    return max(0.0, min(1.0, trust))


def capped_mean(factors: List[float], cap: float = 0.95) -> float:
    """
    Aggregate factors using arithmetic mean, capped at a maximum.

    Prevents any combination from reaching perfect 1.0 (epistemic humility).

    Args:
        factors: List of factors ∈ [0, 1]
        cap: Maximum trust score allowed (default 0.95)

    Returns:
        Trust score ∈ [0, cap]

    Examples:
        >>> capped_mean([0.99, 0.98, 0.97], cap=0.95)
        0.95
    """
    if not factors:
        return 0.5

    mean = arithmetic_mean(factors)
    return min(cap, mean)


def weighted_mean(
    factors: List[float],
    weights: Optional[List[float]] = None
) -> float:
    """
    Aggregate factors using weighted mean.

    Allows explicit importance weighting per factor.
    Must be monotone: all weights > 0.

    Args:
        factors: List of factors ∈ [0, 1]
        weights: Optional list of weights (default: equal weight)
                 Weights are auto-normalized to sum to 1.0

    Returns:
        Trust score ∈ [0, 1]

    Examples:
        >>> weighted_mean([0.8, 0.6], weights=[2.0, 1.0])
        0.733
    """
    if not factors:
        return 0.5

    if len(factors) == 0:
        return 0.5

    if weights is None:
        # Equal weights
        weights = [1.0] * len(factors)

    if len(weights) != len(factors):
        raise ValueError(f"Weights length {len(weights)} != factors length {len(factors)}")

    if any(w < 0 for w in weights):
        logger.warning(f"Negative weights detected: {weights}")
        weights = [max(0.0, w) for w in weights]

    weight_sum = sum(weights)
    if weight_sum == 0:
        logger.warning("Weight sum is zero; defaulting to equal weights")
        weights = [1.0] * len(factors)
        weight_sum = len(factors)

    # Normalize weights
    normalized_weights = [w / weight_sum for w in weights]

    trust = sum(f * w for f, w in zip(factors, normalized_weights))
    return max(0.0, min(1.0, trust))


# ============================================================================
# ADVANCED: LOGISTIC-BASED BLENDING
# ============================================================================

def logistic_blend(
    factors: List[float],
    weights: Optional[List[float]] = None,
    sharpness: float = 5.0
) -> float:
    """
    Aggregate factors using logistic blend (monotone, nonlinear).

    Combines weighted mean with logistic curve to add sensitivity to
    extreme values. Still monotone, but gives more dynamic response.

    Formula: sigmoid(sharpness * (weighted_mean(factors) - 0.5))
    This shifts the response curve so 0.5 maps to 0.5, but extremes (0 or 1)
    are amplified based on `sharpness`.

    Args:
        factors: List of factors ∈ [0, 1]
        weights: Optional weights (auto-normalized)
        sharpness: Curve sharpness. Higher = steeper S-curve (default 5.0)

    Returns:
        Trust score ∈ [0, 1]

    Examples:
        >>> logistic_blend([0.8, 0.6], sharpness=5.0)
        0.731
    """
    if not factors:
        return 0.5

    # Start with weighted mean
    mean = weighted_mean(factors, weights)

    # Apply logistic transform around 0.5
    # logistic(x) = 1 / (1 + exp(-x))
    # We use: logistic(sharpness * (mean - 0.5))
    # This keeps mean=0.5 → 0.5, and amplifies extremes
    try:
        exponent = sharpness * (mean - 0.5)
        # Clamp exponent to avoid overflow
        exponent = max(-100.0, min(100.0, exponent))
        trust = 1.0 / (1.0 + math.exp(-exponent))
    except (OverflowError, ValueError):
        logger.warning(f"Logistic overflow; using mean: {mean}")
        trust = mean

    return max(0.0, min(1.0, trust))


def min_mean_hybrid(
    factors: List[float],
    min_weight: float = 0.3
) -> float:
    """
    Hybrid aggregation: blend minimum factor with mean.

    Acts as a "weak link" detector: the weakest factor has some influence,
    but doesn't completely dominate.

    Formula: (1 - min_weight) * mean + min_weight * min(factors)

    Args:
        factors: List of factors ∈ [0, 1]
        min_weight: Weight given to minimum factor (0.0–1.0, default 0.3)

    Returns:
        Trust score ∈ [0, 1]

    Examples:
        >>> min_mean_hybrid([0.9, 0.6, 0.8], min_weight=0.3)
        0.77
    """
    if not factors:
        return 0.5

    if not (0.0 <= min_weight <= 1.0):
        logger.warning(f"min_weight out of range: {min_weight}; clamping")
        min_weight = max(0.0, min(1.0, min_weight))

    min_factor = min(factors)
    mean_factor = arithmetic_mean(factors)

    trust = (1.0 - min_weight) * mean_factor + min_weight * min_factor
    return max(0.0, min(1.0, trust))


# ============================================================================
# TRUST CALIBRATION & VALIDATION
# ============================================================================

def validate_factors(factors: List[float]) -> bool:
    """
    Validate that all factors are in [0, 1].

    Args:
        factors: List of factors to validate

    Returns:
        True if all valid, False otherwise
    """
    if not factors:
        return False

    for i, f in enumerate(factors):
        if not (0.0 <= f <= 1.0):
            logger.warning(f"Factor[{i}] out of range: {f}")
            return False

    return True


def clamp_factors(factors: List[float]) -> List[float]:
    """
    Forcefully clamp all factors to [0, 1].

    Args:
        factors: List of factors

    Returns:
        Clamped factors
    """
    return [max(0.0, min(1.0, f)) for f in factors]


# ============================================================================
# TRUST SCORE BUILDER
# ============================================================================

class TrustScoreBuilder:
    """
    Builder pattern for composing complex trust scores.

    Example:
        >>> builder = TrustScoreBuilder()
        >>> builder.add_factor("vwap_z", 0.8)
        >>> builder.add_factor("volatility", 0.6)
        >>> trust = builder.compute(method="geometric_mean")
        >>> print(trust)
        0.695
    """

    def __init__(self):
        self.factors: dict = {}

    def add_factor(self, name: str, value: float) -> "TrustScoreBuilder":
        """Add a named factor."""
        if not (0.0 <= value <= 1.0):
            logger.warning(f"Factor {name} out of range: {value}; clamping")
            value = max(0.0, min(1.0, value))
        self.factors[name] = value
        return self

    def add_factors(self, **factors) -> "TrustScoreBuilder":
        """Add multiple factors at once."""
        for name, value in factors.items():
            self.add_factor(name, value)
        return self

    def compute(self, method: str = "geometric_mean") -> float:
        """
        Compute trust score using specified aggregation method.

        Args:
            method: "geometric_mean", "harmonic_mean", "arithmetic_mean",
                   "capped_mean", "logistic_blend", "min_mean_hybrid"

        Returns:
            Trust score ∈ [0, 1]
        """
        if not self.factors:
            return 0.5

        factors_list = list(self.factors.values())

        if method == "geometric_mean":
            return geometric_mean(factors_list)
        elif method == "harmonic_mean":
            return harmonic_mean(factors_list)
        elif method == "arithmetic_mean":
            return arithmetic_mean(factors_list)
        elif method == "capped_mean":
            return capped_mean(factors_list)
        elif method == "logistic_blend":
            return logistic_blend(factors_list)
        elif method == "min_mean_hybrid":
            return min_mean_hybrid(factors_list)
        else:
            logger.warning(f"Unknown method: {method}; using geometric_mean")
            return geometric_mean(factors_list)

    def compute_with_weights(
        self,
        method: str = "weighted_mean",
        weights: Optional[dict] = None
    ) -> float:
        """
        Compute trust score with custom factor weights.

        Args:
            method: "weighted_mean" or "logistic_blend"
            weights: Dict mapping factor names to weights

        Returns:
            Trust score ∈ [0, 1]
        """
        if not self.factors:
            return 0.5

        if weights is None:
            weights = {name: 1.0 for name in self.factors}

        factor_names = list(self.factors.keys())
        factors_list = list(self.factors.values())
        weights_list = [weights.get(name, 1.0) for name in factor_names]

        if method == "weighted_mean":
            return weighted_mean(factors_list, weights_list)
        elif method == "logistic_blend":
            return logistic_blend(factors_list, weights_list)
        else:
            logger.warning(f"Unknown method: {method}; using weighted_mean")
            return weighted_mean(factors_list, weights_list)

    def factors_dict(self) -> dict:
        """Return current factors as dict."""
        return self.factors.copy()

    def reset(self) -> "TrustScoreBuilder":
        """Reset all factors."""
        self.factors = {}
        return self
