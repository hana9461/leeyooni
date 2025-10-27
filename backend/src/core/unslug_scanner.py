"""
UNSLUG Scanner - 저점 탐지 및 Fibonacci 기반 신호 생성
(Adapted from user's UNSLUG code)
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple
import numpy as np
import pandas as pd
import structlog

from shared.schemas import InputSlice

logger = structlog.get_logger(__name__)


def fib_up(L: float, H: float, p: float) -> float:
    """
    Fibonacci retracement 계산
    Args:
        L: 저가 (Low)
        H: 고가 (High)
        p: 피보나치 수준 (0-100)
    Returns:
        해당 수준의 가격
    """
    if H <= L:
        return L
    return L + (H - L) * (p / 100.0)


class UnslugScanner:
    """
    COVID-19 팬데믹 저점 기반 UNSLUG 신호 생성기

    Logic:
    1. 2020년 3월 팬데믹 저점 찾기
    2. 이후 최고점 찾기
    3. Fibonacci 23.6%, 38.2% 밴드 계산
    4. 현재가가 어느 밴드에 있는지 판단
    5. 최근 30일 내 밴드 내 히트 여부 확인
    """

    def __init__(self, start_date: str = "2018-01-01", lookback_days: int = 30):
        """
        Args:
            start_date: 데이터 시작일
            lookback_days: 최근 히트 추적 기간
        """
        self.start_date = start_date
        self.lookback_days = lookback_days
        self.logger = logger.bind(module="unslug_scanner")

    def scan(self, series: List[InputSlice]) -> Dict:
        """
        UNSLUG 신호 계산

        Args:
            series: InputSlice 리스트 (OHLCV)

        Returns:
            {
                'unslug_score': float ∈ [0,1],
                'band': str (Below 0%, 0-23.6%, 23.6-38.2%, Above 38.2%),
                'current_price': float,
                'low_dt': datetime,
                'low_val': float,
                'high_dt': datetime,
                'high_val': float,
                'fib_23_6': float,
                'fib_38_2': float,
                'hits_in_range': int,
                'first_hit': Optional[datetime],
                'signal_strength': float
            }
        """
        if not series or len(series) < 20:
            self.logger.warning("Insufficient data for UNSLUG scan", length=len(series))
            return self._null_result()

        # DataFrame으로 변환
        df = self._convert_to_dataframe(series)

        # COVID 저점 + 이후 고점 찾기
        covid_info = self._find_covid_low_then_high(df)
        if not covid_info:
            self.logger.warning("No COVID low-high pattern found")
            return self._null_result()

        L = covid_info['low_val']
        H = covid_info['high_val']
        low_dt = covid_info['low_dt']
        high_dt = covid_info['high_dt']

        # Fibonacci 레벨 계산
        fib_23_6 = fib_up(L, H, 23.6)
        fib_38_2 = fib_up(L, H, 38.2)

        # 현재가
        curr = float(df["close"].iloc[-1])

        # 밴드 결정
        if curr < L:
            band = "Below 0%"
        elif curr <= fib_23_6:
            band = "0–23.6%"
        elif curr <= fib_38_2:
            band = "23.6–38.2%"
        else:
            band = "Above 38.2%"

        # 최근 30일 내 0-38.2% 밴드 히트
        hits, first_hit = self._hits_in_range(df, L, fib_38_2, self.lookback_days)

        # UNSLUG Score 계산 (0-1)
        # Logic: 현재가가 0-38.2% 범위 + 최근 히트 여부 → 점수
        unslug_score = self._calculate_score(
            curr, L, fib_38_2, band, hits
        )

        return {
            'unslug_score': unslug_score,
            'band': band,
            'current_price': curr,
            'low_dt': low_dt.date() if low_dt else None,
            'low_val': L,
            'high_dt': high_dt.date() if high_dt else None,
            'high_val': H,
            'fib_23_6': fib_23_6,
            'fib_38_2': fib_38_2,
            'hits_in_range': hits,
            'first_hit': first_hit.date() if first_hit else None,
            'signal_strength': float(np.clip(unslug_score, 0, 1))
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

    def _find_covid_low_then_high(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        COVID-19 팬데믹 저점(2020년 3월) + 이후 고점 찾기

        Returns:
            {
                'low_dt': pd.Timestamp,
                'low_val': float,
                'high_dt': pd.Timestamp,
                'high_val': float
            }
            또는 None
        """
        df = df.sort_values('ts').copy()

        # 2020년 3월 저점 찾기 (1차 시도)
        covid_start = pd.to_datetime("2020-03-01")
        covid_end = pd.to_datetime("2020-03-31")
        w = df[(df['ts'] >= covid_start) & (df['ts'] <= covid_end)]

        if w.empty:
            # 2차 시도: 더 넓은 범위
            covid_start = pd.to_datetime("2020-02-15")
            covid_end = pd.to_datetime("2020-04-15")
            w = df[(df['ts'] >= covid_start) & (df['ts'] <= covid_end)]

        if w.empty:
            return None

        # 저점 찾기
        ldt = w["low"].idxmin()
        L = float(w.loc[ldt, "low"])
        ldt_val = w.loc[ldt, "ts"]

        # 저점 이후 고점 찾기
        after = df[df["ts"] >= ldt_val]
        if after.empty:
            return None

        hdt = after["high"].idxmax()
        H = float(after.loc[hdt, "high"]) if hdt is not None else None
        hdt_val = after.loc[hdt, "ts"] if hdt is not None else None

        if hdt is None or H is None or H <= L:
            return None

        return {
            'low_dt': ldt_val,
            'low_val': L,
            'high_dt': hdt_val,
            'high_val': H
        }

    def _hits_in_range(
        self,
        df: pd.DataFrame,
        lo: float,
        hi: float,
        lookback_days: int
    ) -> Tuple[int, Optional[pd.Timestamp]]:
        """
        최근 lookback_days 기간 내 종가가 [lo, hi] 범위에 있는 횟수

        Returns:
            (hit_count, first_hit_datetime)
        """
        if df.empty:
            return 0, None

        tail = df.tail(lookback_days)
        if tail.empty:
            return 0, None

        close = tail["close"]
        lo_, hi_ = (lo, hi) if lo <= hi else (hi, lo)
        mask = (close >= lo_) & (close <= hi_)

        if not mask.any():
            return 0, None

        hit_dates = tail.loc[mask, "ts"]
        count = int(mask.sum())
        first_hit = hit_dates.iloc[0] if len(hit_dates) > 0 else None

        return count, first_hit

    def _calculate_score(
        self,
        curr: float,
        L: float,
        H_38: float,
        band: str,
        hits: int
    ) -> float:
        """
        UNSLUG Score 계산 (0-1)

        Logic:
        - 현재가가 0-38.2% 범위 → 높은 점수
        - 최근 30일 내 밴드 히트 → 보너스
        - Below 0% → 높은 점수 (더 싼 것)
        """
        if L == 0 or H_38 == 0:
            return 0.5  # 기본값

        # Base score: 현재가가 0-38.2% 범위에 얼마나 가까운가
        if curr < L:
            # Below 0%: 가장 높은 점수
            base_score = 0.9
        elif curr <= H_38:
            # 0-38.2% 범위: 상대 위치에 따라
            ratio = (curr - L) / (H_38 - L) if H_38 > L else 0
            base_score = 0.9 - (ratio * 0.3)  # 0.6-0.9
        else:
            # Above 38.2%: 낮은 점수
            base_score = 0.4

        # 히트 여부 보너스
        hit_bonus = min(hits * 0.05, 0.1)  # 최대 0.1 보너스

        final_score = np.clip(base_score + hit_bonus, 0, 1)
        return float(final_score)

    def _null_result(self) -> Dict:
        """데이터 부족 시 기본값"""
        return {
            'unslug_score': 0.5,
            'band': 'N/A',
            'current_price': None,
            'low_dt': None,
            'low_val': None,
            'high_dt': None,
            'high_val': None,
            'fib_23_6': None,
            'fib_38_2': None,
            'hits_in_range': 0,
            'first_hit': None,
            'signal_strength': 0.5
        }


# 전역 인스턴스
unslug_scanner = UnslugScanner()
