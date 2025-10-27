"""
UNSLUG Algorithm - 피보나치 되돌림 기반 저점 매수 신호
"""
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf
import structlog

logger = structlog.get_logger(__name__)


class UnslugConfig:
    """UNSLUG 설정"""
    START_DATE = "2018-01-01"
    LOOKBACK_DAYS = 30
    TOL_PCT = 3.0  # 23.6% 근처 허용 오차 (%)

    # COVID 저점 탐색 범위
    COVID_PERIOD_1 = ("2020-03-01", "2020-03-31")
    COVID_PERIOD_2 = ("2020-02-15", "2020-04-15")

    # 피보나치 레벨
    FIB_23_6 = 23.6
    FIB_38_2 = 38.2


class UnslugCalculator:
    """UNSLUG 알고리즘 계산기"""

    def __init__(self, config: UnslugConfig = None):
        self.config = config or UnslugConfig()

    def _naive_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """타임존 제거"""
        if getattr(df.index, "tz", None) is not None:
            df = df.copy()
            df.index = df.index.tz_convert(None)
        return df

    def fib_up(self, L: float, H: float, p: float) -> float:
        """피보나치 레벨 계산"""
        return L + (H - L) * (p / 100.0)

    def fetch_daily_data(self, ticker: str) -> pd.DataFrame:
        """일별 데이터 가져오기"""
        try:
            df = yf.Ticker(ticker).history(
                period="max",
                interval="1d",
                auto_adjust=False
            )

            if df is None or df.empty:
                return pd.DataFrame()

            df = self._naive_index(df.sort_index())
            df = df.loc[pd.to_datetime(self.config.START_DATE):]

            # 필수 컬럼 확인
            need = ["Open", "High", "Low", "Close", "Volume"]
            for c in need:
                if c not in df.columns:
                    df[c] = df["Close"] if c != "Volume" else np.nan

            return df[need]

        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            return pd.DataFrame()

    def find_covid_low_high(self, daily: pd.DataFrame) -> Optional[Dict]:
        """2020년 팬데믹 저점(L)과 이후 최고점(H) 탐색"""
        if daily is None or daily.empty:
            return None

        df = daily.sort_index()

        def _min_in(s, e):
            w = df.loc[pd.to_datetime(s):pd.to_datetime(e)]
            if w.empty:
                return None, None
            dt = w["Low"].idxmin()
            val = float(w.loc[dt, "Low"])
            return dt, val

        # 저점 찾기
        ldt, L = _min_in(*self.config.COVID_PERIOD_1)
        if ldt is None:
            ldt, L = _min_in(*self.config.COVID_PERIOD_2)
        if ldt is None:
            return None

        # 이후 최고점 찾기
        after = df.loc[ldt:]
        if after.empty:
            return None

        hdt = after["High"].idxmax()
        H = float(after.loc[hdt, "High"]) if hdt is not None else None

        if hdt is None or H is None or H <= L:
            return None

        return {
            "low_dt": ldt,
            "low_val": L,
            "high_dt": hdt,
            "high_val": H
        }

    def hits_in_range(
        self,
        daily: pd.DataFrame,
        lo: float,
        hi: float,
        lookback_days: int
    ) -> Tuple[int, Optional[pd.Timestamp]]:
        """최근 lookback 구간에서 범위 내 히트 횟수"""
        if daily is None or daily.empty:
            return 0, None

        tail = daily.tail(lookback_days)
        if tail.empty:
            return 0, None

        close = tail["Close"]
        lo_, hi_ = (lo, hi) if lo <= hi else (hi, lo)
        mask = (close >= lo_) & (close <= hi_)
        idx = close.index[mask]

        if len(idx) == 0:
            return 0, None

        return int(mask.sum()), pd.Timestamp(idx[0])

    def calculate_signal(self, ticker: str) -> Optional[Dict]:
        """UNSLUG 신호 계산"""
        try:
            # 데이터 가져오기
            df = self.fetch_daily_data(ticker)
            if df.empty:
                return None

            # COVID 저점/고점 찾기
            sw = self.find_covid_low_high(df)
            if not sw:
                return None

            L, H = sw["low_val"], sw["high_val"]
            r23 = self.fib_up(L, H, self.config.FIB_23_6)
            r382 = self.fib_up(L, H, self.config.FIB_38_2)
            curr = float(df["Close"].iloc[-1])

            # 현재가 밴드 라벨
            if curr < L:
                band = "Below 0%"
            elif curr <= r23:
                band = "0–23.6%"
            elif curr <= r382:
                band = "23.6–38.2%"
            else:
                band = "Above 38.2%"

            # 최근 히트 체크
            hits_all, first_all = self.hits_in_range(
                df, L, r382, self.config.LOOKBACK_DAYS
            )

            # 23.6% 근처 체크
            near23 = abs(curr - r23) <= max(1e-9, (self.config.TOL_PCT / 100.0) * (H - L))

            # 신호 판정
            in_band = L <= curr <= r382
            has_signal = in_band or near23 or hits_all > 0

            if not has_signal:
                return None

            # Trust Score 계산
            trust = 0.0
            if in_band:
                # 밴드 내 위치에 따른 신뢰도
                position = (curr - L) / (r382 - L) if (r382 - L) > 0 else 0
                trust = 0.9 - (position * 0.4)  # 0%에 가까울수록 높은 신뢰도
            elif near23:
                trust = 0.75
            elif hits_all > 0:
                trust = 0.6

            return {
                "ticker": ticker.upper(),
                "signal": "BUY" if has_signal else "NEUTRAL",
                "trust": round(trust, 2),
                "current_price": round(curr, 2),
                "band": band,
                "near_23_6": near23,
                "hits_0_38": hits_all,
                "first_hit_date": first_all.date().isoformat() if first_all else None,
                "covid_low": {
                    "date": sw["low_dt"].date().isoformat(),
                    "price": round(L, 2)
                },
                "covid_high": {
                    "date": sw["high_dt"].date().isoformat(),
                    "price": round(H, 2)
                },
                "fib_levels": {
                    "0%": round(L, 2),
                    "23.6%": round(r23, 2),
                    "38.2%": round(r382, 2),
                    "100%": round(H, 2)
                },
                "calculated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"UNSLUG calculation failed for {ticker}: {e}")
            return None

    def scan_watchlist(self, tickers: List[str]) -> List[Dict]:
        """워치리스트 스캔"""
        results = []

        for ticker in tickers:
            signal = self.calculate_signal(ticker)
            if signal:
                results.append(signal)
                logger.info(f"UNSLUG signal found: {ticker}")

        return results


# Global instance
unslug_calculator = UnslugCalculator()
