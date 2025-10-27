"""
Individual Stock Fear & Greed Index
Based on the SSFG (Single-Stock Fear & Greed) algorithm
"""

import os
import math
import re
import io
import zipfile
import pickle
import statistics
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict, Any
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

# Optional OCR support
try:
    import cv2
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

@dataclass
class FearIndexConfig:
    lookback_days: int = 600
    momentum_ma: int = 125
    strength_window: int = 252
    breadth_window: int = 20
    rv_window: int = 20
    rv_ref_window: int = 50
    safehaven_window: int = 20
    tlt_symbol: str = "TLT"
    use_cboe_env: bool = True
    env_days: int = 60

@dataclass
class DataBundle:
    prices: pd.DataFrame
    tlt: pd.DataFrame
    hy_oas: pd.Series
    finra_short_ratio: pd.Series
    cboe_equity_pc: Optional[float] = None
    cboe_equity_pc_hist: Optional[pd.Series] = None

@dataclass
class ComponentScores:
    momentum: pd.Series
    strength: pd.Series
    breadth: pd.Series
    volatility: pd.Series
    safehaven: pd.Series
    credit: pd.Series
    short_sentiment: pd.Series

class FearIndexCalculator:
    def __init__(self, config: FearIndexConfig = None):
        self.config = config or FearIndexConfig()
        self.alpha_api_key = os.getenv("ALPHAVANTAGE_API_KEY", "4PALBFA85A7FRJCH")
        self.fred_api_key = os.getenv("FRED_API_KEY", "26f33e328797864cb0ab4aa2f17af44c")
        
    def rolling_percentile(self, series: pd.Series, window: int, min_periods: Optional[int] = None) -> pd.Series:
        """Calculate rolling percentile"""
        min_periods = window if min_periods is None else min_periods
        def pct_rank(x):
            s = pd.Series(x).dropna()
            if len(s) <= 1: return np.nan
            return 100.0 * s.rank(pct=True).iloc[-1]
        return series.rolling(window, min_periods=min_periods).apply(lambda x: pct_rank(x), raw=False)

    def obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume calculation"""
        sign = np.sign(close.diff().fillna(0))
        return (volume * sign).cumsum()

    def annualized_vol(self, close: pd.Series, window: int) -> pd.Series:
        """Calculate annualized volatility"""
        ret = close.pct_change()
        return ret.rolling(window).std(ddof=0) * np.sqrt(252)

    def clamp_0_100(self, s: pd.Series) -> pd.Series:
        """Clamp values between 0 and 100"""
        return s.clip(lower=0, upper=100)

    def pct_rank_of_value(self, value: float, series: pd.Series) -> float:
        """Calculate percentile rank of a value in a series"""
        s = pd.Series(series).dropna().sort_values()
        if len(s) == 0 or value is None or math.isnan(value): 
            return float("nan")
        return float(100.0 * (s.searchsorted(value, side="right") / len(s)))

    def av_daily_adjusted(self, symbol: str, outputsize: str = "full") -> pd.DataFrame:
        """Fetch daily adjusted data from Alpha Vantage"""
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": outputsize,
            "datatype": "json",
            "apikey": self.alpha_api_key
        }
        
        try:
            r = requests.get("https://www.alphavantage.co/query", params=params, timeout=30)
            r.raise_for_status()
            js = r.json()
            
            key = "Time Series (Daily)"
            if key not in js:
                raise RuntimeError(f"AlphaVantage error: {js.get('Note') or js.get('Error Message') or 'Unknown'}")
            
            ts = pd.DataFrame(js[key]).T.sort_index()
            ts.index = pd.to_datetime(ts.index)
            
            df = ts.rename(columns={
                "1. open": "open", "2. high": "high", "3. low": "low", 
                "4. close": "close", "6. volume": "volume"
            })[["open", "high", "low", "close", "volume"]].astype(float)
            
            return df
        except Exception as e:
            print(f"Alpha Vantage API failed for {symbol}: {e}")
            # Fallback to Stooq
            return self.stooq_daily_us(symbol)

    def stooq_daily_us(self, symbol: str) -> pd.DataFrame:
        """Fallback data source from Stooq"""
        try:
            url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df["Date"] = pd.to_datetime(df["Date"])
            out = df.set_index("Date")[["Open", "High", "Low", "Close", "Volume"]]
            out.columns = ["open", "high", "low", "close", "volume"]
            return out.astype(float)
        except Exception as e:
            print(f"Stooq API failed for {symbol}: {e}")
            return pd.DataFrame()

    def fred_series(self, series_id: str, start: Optional[str] = None) -> pd.Series:
        """Fetch FRED economic data"""
        params = {"series_id": series_id, "api_key": self.fred_api_key, "file_type": "json"}
        if start: 
            params["observation_start"] = start
            
        try:
            r = requests.get("https://api.stlouisfed.org/fred/series/observations", params=params, timeout=30)
            r.raise_for_status()
            js = r.json()
            obs = js.get("observations", [])
            
            if not obs: 
                return pd.Series(dtype=float)
                
            df = pd.DataFrame(obs)
            df["date"] = pd.to_datetime(df["date"])
            s = pd.to_numeric(df["value"].replace(".", np.nan), errors="coerce")
            s.index = df["date"]
            s.name = series_id
            return s
        except Exception as e:
            print(f"FRED API failed for {series_id}: {e}")
            return pd.Series(dtype=float)

    def cboe_equity_pc_latest(self) -> Optional[float]:
        """Get latest Cboe Equity Put/Call ratio"""
        try:
            url = "https://www.cboe.com/us/options/market_statistics/daily/"
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")
            table = soup.find("table")
            if not table: 
                return None
                
            for tr in table.find_all("tr"):
                txt = tr.get_text(" ", strip=True).upper()
                if "EQUITY PUT/CALL RATIO" in txt:
                    nums = [x for x in txt.split() if x.replace(".", "", 1).isdigit()]
                    return float(nums[-1]) if nums else None
            return None
        except Exception:
            return None

    def load_data_bundle(self, ticker: str) -> DataBundle:
        """Load all required data for Fear Index calculation"""
        print(f"[FearIndex] Loading data for {ticker}...")
        
        # Price data
        prices = self.av_daily_adjusted(ticker, outputsize="full")
        prices = prices.tail(self.config.lookback_days)
        
        # TLT data
        tlt = self.av_daily_adjusted(self.config.tlt_symbol, outputsize="full")[["close"]]
        tlt = tlt.tail(self.config.lookback_days)
        
        # HY OAS from FRED
        start = (prices.index.min() - pd.Timedelta(days=60)).date().isoformat()
        hy_oas = self.fred_series("BAMLH0A0HYM2", start=start)
        
        # Simplified FINRA short ratio (mock data for now)
        finra_short_ratio = pd.Series(
            np.random.uniform(0.3, 0.7, len(prices.index)),
            index=prices.index,
            name="finra_short_ratio"
        )
        
        # Cboe Equity P/C
        cboe_equity_pc = self.cboe_equity_pc_latest() if self.config.use_cboe_env else None
        
        return DataBundle(
            prices=prices,
            tlt=tlt,
            hy_oas=hy_oas,
            finra_short_ratio=finra_short_ratio,
            cboe_equity_pc=cboe_equity_pc,
            cboe_equity_pc_hist=None
        )

    def compute_components(self, bundle: DataBundle) -> ComponentScores:
        """Calculate all Fear Index components"""
        close = bundle.prices["close"].copy()
        vol = bundle.prices["volume"].copy()

        # 1) Momentum (price vs 125-day SMA) -> 252D percentile
        sma = close.rolling(self.config.momentum_ma).mean()
        mom_ratio = close / sma
        momentum = self.rolling_percentile(mom_ratio, window=max(self.config.momentum_ma, 200))

        # 2) Strength (position within 52-week range)
        low = close.rolling(self.config.strength_window).min()
        high = close.rolling(self.config.strength_window).max()
        strength = 100.0 * (close - low) / (high - low)
        strength = strength.replace([np.inf, -np.inf], np.nan)

        # 3) Breadth (OBV 20D change percentile)
        obv_series = self.obv(close, vol)
        obv_delta = obv_series.diff(self.config.breadth_window)
        breadth = self.rolling_percentile(obv_delta, window=252)

        # 4) Volatility (RV20/RV50 ratio, inverted)
        rv20 = self.annualized_vol(close, self.config.rv_window)
        rv50 = self.annualized_vol(close, self.config.rv_ref_window)
        rv_rat = rv20 / rv50
        volatility = 100.0 - self.rolling_percentile(rv_rat, window=252)

        # 5) Safe Haven (relative performance vs TLT)
        tlt_close = bundle.tlt["close"].reindex(close.index).interpolate()
        rel_ret = close.pct_change(self.config.safehaven_window) - tlt_close.pct_change(self.config.safehaven_window)
        safehaven = self.rolling_percentile(rel_ret, window=252)

        # 6) Credit (HY OAS, inverted)
        hy_pct = self.rolling_percentile(bundle.hy_oas.reindex(close.index).interpolate(), window=252)
        credit = 100.0 - hy_pct

        # 7) Short Sentiment (FINRA short ratio, inverted)
        sr_pct = self.rolling_percentile(bundle.finra_short_ratio.reindex(close.index), window=252)
        short_sentiment = 100.0 - sr_pct

        return ComponentScores(
            momentum=self.clamp_0_100(momentum),
            strength=self.clamp_0_100(strength),
            breadth=self.clamp_0_100(breadth),
            volatility=self.clamp_0_100(volatility),
            safehaven=self.clamp_0_100(safehaven),
            credit=self.clamp_0_100(credit),
            short_sentiment=self.clamp_0_100(short_sentiment)
        )

    def calculate_fear_index(self, symbol: str) -> Dict[str, Any]:
        """Main function to calculate Fear Index for a symbol"""
        try:
            bundle = self.load_data_bundle(symbol)
            components = self.compute_components(bundle)
            
            # Create component DataFrame
            comp_df = pd.DataFrame({
                "momentum": components.momentum,
                "strength": components.strength,
                "breadth": components.breadth,
                "volatility": components.volatility,
                "safehaven": components.safehaven,
                "credit": components.credit,
                "short_sentiment": components.short_sentiment,
            })
            
            # Calculate final score (simple average)
            score = comp_df.mean(axis=1, skipna=True)
            
            # Get latest values
            latest_date = score.index.max()
            latest_score = float(score.iloc[-1])
            latest_components = comp_df.iloc[-1].to_dict()
            
            # Environment adjustment
            env_adj = 0.0
            if self.config.use_cboe_env and bundle.cboe_equity_pc:
                # Simple linear adjustment based on P/C ratio
                env_adj = float(np.clip((0.7 - bundle.cboe_equity_pc) / 0.3 * 5.0, -5.0, 5.0))
            
            final_score = float(np.clip(latest_score + env_adj, 0, 100))
            
            return {
                "symbol": symbol.upper(),
                "date": latest_date.strftime("%Y-%m-%d"),
                "fear_index": final_score,
                "components": latest_components,
                "env_adjustment": env_adj,
                "cboe_pc_ratio": bundle.cboe_equity_pc,
                "regime": self.get_regime_label(final_score),
                "explanation": self.generate_explanation(latest_components, final_score)
            }
            
        except Exception as e:
            return {
                "symbol": symbol.upper(),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "fear_index": 50.0,  # Neutral fallback
                "error": str(e),
                "regime": "Neutral"
            }

    def get_regime_label(self, score: float) -> str:
        """Get regime label based on score"""
        if score >= 70: return "Extreme Greed"
        if score >= 55: return "Greed"
        if score <= 30: return "Extreme Fear"
        if score <= 45: return "Fear"
        return "Neutral"

    def generate_explanation(self, components: Dict[str, float], final_score: float) -> List[Dict[str, Any]]:
        """Generate explanation for the Fear Index"""
        explanations = []
        
        component_names = {
            "momentum": "Price Momentum",
            "strength": "Price Strength", 
            "breadth": "Volume Breadth",
            "volatility": "Volatility",
            "safehaven": "Safe Haven Demand",
            "credit": "Credit Conditions",
            "short_sentiment": "Short Interest"
        }
        
        for comp, value in components.items():
            if not math.isnan(value):
                contribution = "neutral"
                if value > 60:
                    contribution = "decreases_fear"  # Higher score = less fear
                elif value < 40:
                    contribution = "increases_fear"  # Lower score = more fear
                    
                explanations.append({
                    "name": component_names.get(comp, comp.title()),
                    "value": round(value, 1),
                    "contribution": contribution
                })
        
        return explanations

# Global instance
fear_calculator = FearIndexCalculator()
