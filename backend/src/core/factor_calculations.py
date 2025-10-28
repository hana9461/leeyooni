"""
Factor Calculations - Utility Functions
P1 module stub for zscore and rolling_minmax
"""
import numpy as np
import pandas as pd
from typing import Optional


def zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """
    Z-score normalization over rolling window
    """
    rolling_mean = series.rolling(window=window, min_periods=1).mean()
    rolling_std = series.rolling(window=window, min_periods=1).std()
    rolling_std = rolling_std.replace(0, 1)  # Avoid division by zero
    return (series - rolling_mean) / rolling_std


def rolling_minmax(series: pd.Series, window: int = 20) -> pd.Series:
    """
    Min-Max normalization over rolling window
    Returns values ∈ [0, 1]
    """
    rolling_min = series.rolling(window=window, min_periods=1).min()
    rolling_max = series.rolling(window=window, min_periods=1).max()

    denominator = rolling_max - rolling_min
    denominator = denominator.replace(0, 1)  # Avoid division by zero

    return (series - rolling_min) / denominator
