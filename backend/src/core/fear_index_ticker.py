"""
Fear & Greed Index Calculator - 개별 종목 공포/탐욕 지수
(Adapted from user's SSFG code, simplified for Yahoo data)

Components:
1. Momentum (가격/125SMA) → 252D 백분위
2. Strength (52주 고저 대비 위치)
3. Volatility (RV20/RV50 비율 → 역순)
4. Breadth (OBV 변화의 백분위)
5. SafeHaven (상대 수익률)
6. Credit (간단 스코어)
7. ShortSentiment (거래량 기반)
"""
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd
import structlog
import math

from shared.schemas import InputSlice
from backend.src.core.factor_calculations import zscore, rolling_minmax

logger = structlog.get_logger(__name__)


def rolling_percentile(series: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series:
    """
    시계열의 각 포인트가 윈도우 내에서 몇 백분위인지 계산
    """
    min_periods = window if min_periods is None else min_periods

    def pct_rank(x):
        s = pd.Series(x).dropna()
        if len(s) <= 1:
            return np.nan
        return 100.0 * s.rank(pct=True).iloc[-1]

    return series.rolling(window, min_periods=min_periods).apply(
        lambda x: pct_rank(x), raw=False
    )


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume"""
    sign = np.sign(close.diff().fillna(0))
    return (volume * sign).cumsum()


def annualized_vol(close: pd.Series, window: int) -> pd.Series:
    """연간화된 변동성 (rolling std * sqrt(252))"""
    ret = close.pct_change()
    return ret.rolling(window).std(ddof=0) * np.sqrt(252)


def clamp_0_100(s: pd.Series) -> pd.Series:
    """0-100 범위로 클립"""
    return s.clip(lower=0, upper=100)


class FearIndexTicker:
    """
    개별 종목 Fear & Greed 점수 계산기

    입력: OHLCV 데이터 (Yahoo)
    출력: fear_score (0-100), components breakdown
    """

    def __init__(
        self,
        lookback_days: int = 600,
        momentum_ma: int = 125,
        strength_window: int = 252,
        breadth_window: int = 20,
        rv_window: int = 20,
    ):
        self.lookback_days = lookback_days
        self.momentum_ma = momentum_ma
        self.strength_window = strength_window
        self.breadth_window = breadth_window
        self.rv_window = rv_window
        self.logger = logger.bind(module="fear_index_ticker")

    def calculate(self, series: List[InputSlice]) -> Dict:
        """
        Fear & Greed 점수 계산

        Args:
            series: InputSlice 리스트 (OHLCV)

        Returns:
            {
                'fear_score': float (0-100),
                'components': {
                    'momentum': float,
                    'strength': float,
                    'volatility': float,
                    'breadth': float,
                    'safe_haven': float,
                    'credit': float,
                    'short_sentiment': float
                },
                'label': 'Fear' | 'Neutral' | 'Greed',
                'change_1d': float,
                'change_5d': float
            }
        """
        if not series or len(series) < 50:
            self.logger.warning("Insufficient data for Fear Index", length=len(series))
            return self._null_result()

        # DataFrame 변환
        df = self._convert_to_dataframe(series)
        df = df.tail(self.lookback_days)  # 최근 lookback_days만

        # 컴포넌트 계산
        components = self._compute_components(df)

        # 최종 점수
        scores_list = [v for v in components.values() if v is not None and not math.isnan(v)]
        if not scores_list:
            return self._null_result()

        fear_score = float(np.nanmean(scores_list))
        fear_score = np.clip(fear_score, 0, 100)

        # 레이블
        if fear_score >= 70:
            label = "Greed"
        elif fear_score <= 30:
            label = "Fear"
        else:
            label = "Neutral"

        # 변화량 계산
        change_1d = None
        change_5d = None
        if len(df) >= 2:
            # 어제 점수 (재계산 필요, 간단화)
            change_1d = 0.0  # TODO: 실제 계산 시 필요

        return {
            'fear_score': float(fear_score),
            'components': components,
            'label': label,
            'change_1d': change_1d,
            'change_5d': change_5d,
            'signal_strength': float(np.clip(fear_score / 100.0, 0, 1))
        }

    def _convert_to_dataframe(self, series: List[InputSlice]) -> pd.DataFrame:
        """InputSlice → DataFrame"""
        data = {
            'ts': [s.ts for s in series],
            'open': [s.open for s in series],
            'high': [s.high for s in series],
            'low': [s.low for s in series],
            'close': [s.close for s in series],
            'volume': [s.volume for s in series],
        }
        df = pd.DataFrame(data)
        df['ts'] = pd.to_datetime(df['ts'])
        df = df.sort_values('ts').reset_index(drop=True)
        return df

    def _compute_components(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        7개 컴포넌트 계산

        각 컴포넌트는 0-100 범위
        높은 값 = Greed (탐욕)
        낮은 값 = Fear (공포)
        """
        components = {}

        try:
            close = df["close"].copy()
            volume = df["volume"].copy()

            # 1) Momentum: 가격 vs 125-SMA의 상대 위치
            sma = close.rolling(self.momentum_ma).mean()
            mom_ratio = close / sma
            momentum = rolling_percentile(mom_ratio, window=max(self.momentum_ma, 200))
            components['momentum'] = float(momentum.iloc[-1]) if not momentum.empty else 50.0

            # 2) Strength: 52주(252일) 고저 대비 현재 위치
            low_252 = close.rolling(self.strength_window).min()
            high_252 = close.rolling(self.strength_window).max()
            strength = 100.0 * (close - low_252) / (high_252 - low_252)
            strength = strength.replace([np.inf, -np.inf], np.nan)
            components['strength'] = float(strength.iloc[-1]) if not strength.empty else 50.0

            # 3) Volatility: RV20/RV50 비율 (높은 변동성 = 공포)
            # 높은 변동성 → 낮은 점수, 따라서 역순
            rv20 = annualized_vol(close, self.rv_window)
            rv50 = annualized_vol(close, self.rv_window * 2.5)
            rv_rat = (rv20 / rv50).replace([np.inf, -np.inf], np.nan)
            volatility = 100.0 - rolling_percentile(rv_rat, window=252)
            components['volatility'] = float(volatility.iloc[-1]) if not volatility.empty else 50.0

            # 4) Breadth: OBV 변화 (거래량 추세)
            obv_series = obv(close, volume)
            obv_delta = obv_series.diff(self.breadth_window)
            breadth = rolling_percentile(obv_delta, window=252)
            components['breadth'] = float(breadth.iloc[-1]) if not breadth.empty else 50.0

            # 5) SafeHaven: 상대 수익률 (간단화)
            # 현재 상승세 = 안전자산 수요 낮음 (Greed)
            returns = close.pct_change(20)
            safe_haven = rolling_percentile(returns, window=252)
            # 역순: 높은 수익률 = 낮은 safe_haven 수요
            components['safe_haven'] = float(100.0 - safe_haven.iloc[-1]) if not safe_haven.empty else 50.0

            # 6) Credit: 단순 스코어 (현재 가격이 200SMA 위/아래)
            sma_200 = close.rolling(200).mean()
            credit_score = 100.0 if close.iloc[-1] > sma_200.iloc[-1] else 30.0
            components['credit'] = float(credit_score)

            # 7) ShortSentiment: 거래량 기반 (높은 거래량 = 활발한 매매 = Greed)
            volume_pct = rolling_percentile(volume, window=252)
            components['short_sentiment'] = float(volume_pct.iloc[-1]) if not volume_pct.empty else 50.0

        except Exception as e:
            self.logger.error(f"Component calculation error: {e}")
            # 기본값 반환
            components = {
                'momentum': 50.0,
                'strength': 50.0,
                'volatility': 50.0,
                'breadth': 50.0,
                'safe_haven': 50.0,
                'credit': 50.0,
                'short_sentiment': 50.0
            }

        # 모든 값을 0-100 범위로 정규화
        for key in components:
            components[key] = float(np.clip(components[key], 0, 100))

        return components

    def _null_result(self) -> Dict:
        """데이터 부족 시 기본값"""
        return {
            'fear_score': 50.0,
            'components': {
                'momentum': 50.0,
                'strength': 50.0,
                'volatility': 50.0,
                'breadth': 50.0,
                'safe_haven': 50.0,
                'credit': 50.0,
                'short_sentiment': 50.0
            },
            'label': 'Neutral',
            'change_1d': None,
            'change_5d': None,
            'signal_strength': 0.5
        }


# 전역 인스턴스
fear_index = FearIndexTicker()
