"""
Factor Calculations Module
Normalized factor utilities for UNSLUG City organisms.

All factors are normalized to [0, 1] scale using monotone transforms.
"""

from typing import List, Optional, Tuple
import math
import structlog

logger = structlog.get_logger(__name__)


# ============================================================================
# UTILITY: NORMALIZATION FUNCTIONS
# ============================================================================

def zscore(values: List[float], safe: bool = True) -> List[float]:
    """
    Calculate z-scores for a series of values.

    Args:
        values: List of numeric values
        safe: If True, handle edge cases (empty list, std=0)

    Returns:
        List of z-scores, bounded to [-3, 3] for stability

    Examples:
        >>> zscore([100, 101, 102, 103, 104])
        [-1.414, -0.707, 0.0, 0.707, 1.414]
    """
    if not values or len(values) < 2:
        if safe:
            return [0.0] * len(values)
        raise ValueError("Need at least 2 values for z-score")

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = math.sqrt(variance)

    if std == 0:
        if safe:
            return [0.0] * len(values)
        raise ValueError("Standard deviation is zero; cannot compute z-score")

    # Bound to [-3, 3] for stability
    z_scores = [(x - mean) / std for x in values]
    return [max(-3.0, min(3.0, z)) for z in z_scores]


def pct_rank(values: List[float]) -> List[float]:
    """
    Calculate percentile rank for each value in a series.

    Args:
        values: List of numeric values

    Returns:
        List of percentile ranks ∈ [0, 1]

    Examples:
        >>> pct_rank([10, 20, 30, 40, 50])
        [0.0, 0.25, 0.5, 0.75, 1.0]
    """
    if not values:
        return []

    if len(values) == 1:
        return [0.5]

    sorted_indices = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)

    for rank, idx in enumerate(sorted_indices):
        # Percentile: (rank) / (n - 1)
        ranks[idx] = rank / (len(values) - 1)

    return ranks


def rolling_minmax(values: List[float], window: int = 20) -> List[float]:
    """
    Normalize each value to [0, 1] within a rolling window.

    Args:
        values: List of numeric values
        window: Rolling window size (default 20)

    Returns:
        List of normalized values ∈ [0, 1]

    Examples:
        >>> rolling_minmax([1, 2, 3, 4, 5], window=3)
        [0.0, 0.5, 1.0, 0.5, 1.0]
    """
    if not values:
        return []

    if window <= 0:
        raise ValueError("Window size must be > 0")

    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_slice = values[start:i + 1]

        min_val = min(window_slice)
        max_val = max(window_slice)

        if min_val == max_val:
            # All values are the same; default to 0.5
            result.append(0.5)
        else:
            normalized = (values[i] - min_val) / (max_val - min_val)
            result.append(normalized)

    return result


# ============================================================================
# FACTORS: INDIVIDUAL SIGNAL COMPONENTS
# ============================================================================

def vwap_zscore(
    highs: List[float],
    lows: List[float],
    closes: List[float],
    volumes: List[float],
    lookback: int = 20
) -> float:
    """
    Calculate VWAP z-score as a factor (normalized to [0, 1]).

    VWAP (Volume Weighted Average Price) indicates the "center of gravity"
    for recent trading. A negative z-score suggests undervaluation.

    Args:
        highs: List of high prices
        lows: List of low prices
        closes: List of close prices
        volumes: List of volumes
        lookback: Number of periods for VWAP calculation (default 20)

    Returns:
        Factor ∈ [0, 1]: 0 = deeply below VWAP, 0.5 = at VWAP, 1 = deeply above
    """
    if not (highs and lows and closes and volumes) or len(closes) < lookback:
        return 0.5  # Default to neutral if insufficient data

    # Use last `lookback` periods
    recent_highs = highs[-lookback:]
    recent_lows = lows[-lookback:]
    recent_closes = closes[-lookback:]
    recent_volumes = volumes[-lookback:]

    # Calculate VWAP: sum(typical_price * volume) / sum(volume)
    typical_prices = [(h + l + c) / 3 for h, l, c in zip(recent_highs, recent_lows, recent_closes)]
    vwap = sum(tp * v for tp, v in zip(typical_prices, recent_volumes)) / sum(recent_volumes)

    current_price = closes[-1]
    z_score = (current_price - vwap) / (vwap * 0.02 + 0.01)  # Scale by ~2% volatility

    # Convert z-score [-3, 3] to [0, 1]
    # -3 => 0 (far below), 0 => 0.5 (at VWAP), +3 => 1 (far above)
    factor = (z_score + 3.0) / 6.0
    return max(0.0, min(1.0, factor))


def realized_volatility_pct(
    returns: List[float],
    window: int = 20
) -> float:
    """
    Calculate realized volatility as a percentile rank (normalized to [0, 1]).

    High volatility (near 1.0) suggests market stress or opportunity.
    Low volatility (near 0.0) suggests calm market.

    Args:
        returns: List of daily returns (e.g., [0.01, -0.02, 0.03, ...])
        window: Rolling window for volatility (default 20 days)

    Returns:
        Factor ∈ [0, 1]: 0 = very low volatility, 1 = very high volatility
    """
    if not returns or len(returns) < window:
        return 0.5

    # Calculate rolling volatility
    rolling_vols = []
    for i in range(len(returns) - window + 1):
        window_returns = returns[i:i + window]
        mean_ret = sum(window_returns) / len(window_returns)
        variance = sum((r - mean_ret) ** 2 for r in window_returns) / len(window_returns)
        vol = math.sqrt(variance)
        rolling_vols.append(vol)

    if not rolling_vols:
        return 0.5

    current_vol = rolling_vols[-1]

    # Rank current volatility against historical rolling vols
    rank = sum(1 for v in rolling_vols if v <= current_vol) / len(rolling_vols)
    return max(0.0, min(1.0, rank))


def volume_turnover_ratio(
    volumes: List[float],
    lookback: int = 10
) -> float:
    """
    Calculate volume turnover ratio (normalized to [0, 1]).

    High ratio (> 1.5) suggests strong participation; low ratio (< 0.5)
    suggests weak interest.

    Args:
        volumes: List of trading volumes
        lookback: Window for average volume (default 10 days)

    Returns:
        Factor ∈ [0, 1]: 0 = very low turnover, 1 = very high turnover
    """
    if not volumes or len(volumes) < lookback + 1:
        return 0.5

    # Average volume of previous `lookback` periods
    avg_vol = sum(volumes[-lookback - 1:-1]) / lookback
    current_vol = volumes[-1]

    if avg_vol == 0:
        return 0.5

    ratio = current_vol / avg_vol

    # Map ratio to [0, 1]: 0.5x => 0, 1.0x => 0.5, 2.0x => 1.0
    # Using logistic transform: 1 / (1 + exp(-k * (ratio - 1)))
    factor = 1.0 / (1.0 + math.exp(-5.0 * (ratio - 1.0)))
    return max(0.0, min(1.0, factor))


def drawdown_intensity(
    prices: List[float],
    window: int = 20
) -> float:
    """
    Calculate maximum drawdown intensity within a window (normalized to [0, 1]).

    High intensity (near 1.0) suggests recent sharp declines.
    Low intensity (near 0.0) suggests minimal recent losses.

    Args:
        prices: List of closing prices
        window: Lookback window (default 20 days)

    Returns:
        Factor ∈ [0, 1]: 0 = no drawdown, 1 = severe drawdown
    """
    if not prices or len(prices) < window:
        return 0.5

    recent_prices = prices[-window:]

    # Find running maximum and maximum drawdown
    running_max = recent_prices[0]
    max_drawdown = 0.0

    for price in recent_prices[1:]:
        if price > running_max:
            running_max = price
        else:
            dd = (running_max - price) / running_max
            max_drawdown = max(max_drawdown, dd)

    # Normalize: 0% => 0, 5% => 0.5, 10%+ => 1.0
    factor = min(1.0, max_drawdown / 0.10)
    return max(0.0, min(1.0, factor))


def liquidity_floor(
    volumes: List[float],
    min_volume_threshold: float = 1e6
) -> float:
    """
    Check if recent volume exceeds minimum liquidity threshold.

    Args:
        volumes: List of trading volumes
        min_volume_threshold: Minimum acceptable volume

    Returns:
        Factor ∈ [0, 1]: 1.0 if above threshold, 0.0 if below
    """
    if not volumes:
        return 0.0

    recent_volume = volumes[-1]
    return 1.0 if recent_volume >= min_volume_threshold else 0.0


# ============================================================================
# COMPOSITE FACTORS
# ============================================================================

def mean_reversion_signal(
    prices: List[float],
    volumes: List[float],
    lookback: int = 20
) -> Tuple[float, List[float]]:
    """
    Composite signal combining VWAP z-score, volatility, and volume.

    Returns:
        (composite_trust, [vwap_z, volatility, volume_ratio])
    """
    if len(prices) < lookback:
        return 0.5, [0.5, 0.5, 0.5]

    highs = prices  # Simplified: assume close price is in middle
    lows = prices
    closes = prices

    vwap_z = vwap_zscore(highs, lows, closes, volumes, lookback)

    # Compute returns for volatility
    returns = [(prices[i] - prices[i-1]) / prices[i-1] if prices[i-1] != 0 else 0
               for i in range(1, len(prices))]
    vol = realized_volatility_pct(returns, lookback)

    turn_ratio = volume_turnover_ratio(volumes, lookback)

    return (vwap_z + vol + turn_ratio) / 3.0, [vwap_z, vol, turn_ratio]


# ============================================================================
# VALIDATION & HELPERS
# ============================================================================

def validate_factor_output(factor_value: float, name: str = "factor") -> bool:
    """
    Validate that a factor is in [0, 1] range.

    Args:
        factor_value: The factor value to validate
        name: Name of the factor (for logging)

    Returns:
        True if valid, False otherwise
    """
    if not (0.0 <= factor_value <= 1.0):
        logger.warning(f"{name} out of range: {factor_value}")
        return False
    return True


def clamp_to_unit(value: float) -> float:
    """
    Forcefully clamp a value to [0, 1].

    Args:
        value: Any float

    Returns:
        Value clamped to [0, 1]
    """
    return max(0.0, min(1.0, value))
