"""
Yahoo Finance Data Adapter
Fetches OHLCV data via yfinance with retry logic and error handling.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import time
import structlog

try:
    import yfinance as yf
except ImportError:
    yf = None

from shared.schemas import InputSlice

logger = structlog.get_logger(__name__)


class YahooDataAdapter:
    """
    Adapter for fetching market data from Yahoo Finance.

    Features:
    - Exponential backoff retry logic
    - Timeout handling
    - Data validation
    - Logging of failures
    """

    def __init__(
        self,
        max_retries: int = 3,
        timeout: int = 10,
        backoff_base: float = 2.0
    ):
        """
        Initialize Yahoo adapter.

        Args:
            max_retries: Maximum number of retry attempts (default 3)
            timeout: Timeout in seconds (default 10)
            backoff_base: Exponential backoff base (default 2.0)
        """
        if yf is None:
            raise ImportError("yfinance not installed. Run: pip install yfinance")

        self.max_retries = max_retries
        self.timeout = timeout
        self.backoff_base = backoff_base
        self.logger = logger.bind(adapter="yahoo")

    def fetch_ohlcv(
        self,
        symbol: str,
        period: str = "5y",
        interval: str = "1d"
    ) -> Optional[List[InputSlice]]:
        """
        Fetch OHLCV data for a symbol.

        Args:
            symbol: Ticker symbol (e.g., "SPY", "AAPL")
            period: Time period ("5y", "1y", "6mo", "3mo", "1mo", "1d", etc.)
            interval: Candle interval ("1d", "1h", "5m", etc.)

        Returns:
            List of InputSlice objects, or None if failed after retries
        """
        attempt = 0
        while attempt < self.max_retries:
            try:
                self.logger.info(f"Fetching {symbol} (period={period}, interval={interval})", attempt=attempt)

                # Fetch data
                ticker = yf.Ticker(symbol)
                df = ticker.history(period=period, interval=interval)

                if df.empty:
                    self.logger.warning(f"No data returned for {symbol}")
                    return None

                # Convert to InputSlice
                result = self._convert_to_input_slices(symbol, df, interval)

                if result:
                    self.logger.info(f"Successfully fetched {len(result)} candles for {symbol}")
                    return result
                else:
                    self.logger.warning(f"Failed to convert data for {symbol}")
                    return None

            except Exception as e:
                attempt += 1
                wait_time = self.backoff_base ** (attempt - 1)

                if attempt >= self.max_retries:
                    self.logger.error(
                        f"Failed after {self.max_retries} retries for {symbol}",
                        error=str(e),
                        final_attempt=True
                    )
                    return None

                self.logger.warning(
                    f"Attempt {attempt} failed for {symbol}, retrying in {wait_time}s",
                    error=str(e)
                )
                time.sleep(wait_time)

        return None

    def fetch_latest(
        self,
        symbol: str,
        lookback: int = 20
    ) -> Optional[List[InputSlice]]:
        """
        Fetch recent data for a symbol (minimum lookback for factor computation).

        Args:
            symbol: Ticker symbol
            lookback: Number of days to fetch (default 20)

        Returns:
            List of InputSlice objects (recent data only)
        """
        try:
            self.logger.info(f"Fetching latest {lookback} days for {symbol}")

            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{lookback + 5}d", interval="1d")  # Fetch extra for gaps

            if df.empty:
                self.logger.warning(f"No recent data for {symbol}")
                return None

            # Keep only last `lookback` rows
            df = df.tail(lookback)

            result = self._convert_to_input_slices(symbol, df, "1d")

            if result:
                self.logger.info(f"Fetched {len(result)} recent candles for {symbol}")
                return result
            else:
                return None

        except Exception as e:
            self.logger.error(f"Failed to fetch latest for {symbol}: {str(e)}")
            return None

    def _convert_to_input_slices(
        self,
        symbol: str,
        df,
        interval: str
    ) -> List[InputSlice]:
        """
        Convert yfinance DataFrame to InputSlice objects.

        Args:
            symbol: Ticker symbol
            df: yfinance DataFrame with columns [Open, High, Low, Close, Volume]
            interval: Candle interval

        Returns:
            List of InputSlice objects
        """
        result = []

        try:
            for idx, row in df.iterrows():
                # Handle both datetime index and string index
                if hasattr(idx, 'tz_localize'):
                    # Timezone-aware datetime
                    ts = idx.tz_localize(None)  # Remove timezone for consistency
                else:
                    ts = idx

                # Convert to datetime if needed
                if not isinstance(ts, datetime):
                    ts = pd.Timestamp(ts).to_pydatetime()

                # Map interval format (yfinance uses "1d", we use "1d")
                interval_str = interval

                # Extract OHLCV
                try:
                    open_price = float(row.get("Open", 0))
                    high = float(row.get("High", 0))
                    low = float(row.get("Low", 0))
                    close = float(row.get("Close", 0))
                    volume = float(row.get("Volume", 0))
                    adj_close = float(row.get("Adj Close", close))
                except (ValueError, TypeError):
                    self.logger.warning(f"Skipping invalid row for {symbol} at {ts}")
                    continue

                # Validate prices
                if close <= 0 or high <= 0 or low <= 0 or open_price <= 0:
                    self.logger.warning(f"Invalid prices for {symbol} at {ts}: OHLC={open_price},{high},{low},{close}")
                    continue

                # Create InputSlice
                slice_obj = InputSlice(
                    symbol=symbol,
                    interval=interval_str,
                    ts=ts,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    adj_close=adj_close,
                    features={}  # Will be computed later
                )

                result.append(slice_obj)

            self.logger.info(f"Converted {len(result)} rows for {symbol}")
            return result

        except Exception as e:
            self.logger.error(f"Conversion failed for {symbol}: {str(e)}")
            return []

    def validate_data(self, slices: List[InputSlice]) -> bool:
        """
        Validate data integrity.

        Args:
            slices: List of InputSlice objects

        Returns:
            True if valid, False otherwise
        """
        if not slices:
            self.logger.warning("Empty slice list")
            return False

        for i, slice_obj in enumerate(slices):
            # Check scale
            if not (0.0 < slice_obj.close < 100000):
                self.logger.warning(f"Slice {i}: price out of reasonable range: {slice_obj.close}")
                return False

            # Check OHLC relationships
            if slice_obj.high < slice_obj.low:
                self.logger.warning(f"Slice {i}: high < low")
                return False

            if slice_obj.high < slice_obj.close or slice_obj.low > slice_obj.close:
                self.logger.warning(f"Slice {i}: close outside [low, high]")
                return False

            # Check ordering
            if i > 0 and slices[i].ts < slices[i - 1].ts:
                self.logger.warning(f"Slice {i}: timestamp not increasing")
                return False

        return True


# Singleton instance
_adapter = None


def get_yahoo_adapter() -> YahooDataAdapter:
    """Get or create singleton Yahoo adapter."""
    global _adapter
    if _adapter is None:
        _adapter = YahooDataAdapter()
    return _adapter


def fetch_symbol_daily(symbol: str, lookback: int = 20) -> Optional[List[InputSlice]]:
    """
    Convenience function to fetch latest daily data for a symbol.

    Args:
        symbol: Ticker symbol
        lookback: Number of days (default 20)

    Returns:
        List of InputSlice objects or None
    """
    adapter = get_yahoo_adapter()
    return adapter.fetch_latest(symbol, lookback)


def fetch_symbol_historical(
    symbol: str,
    period: str = "5y",
    interval: str = "1d"
) -> Optional[List[InputSlice]]:
    """
    Convenience function to fetch historical data for a symbol.

    Args:
        symbol: Ticker symbol
        period: Time period (default "5y")
        interval: Candle interval (default "1d")

    Returns:
        List of InputSlice objects or None
    """
    adapter = get_yahoo_adapter()
    return adapter.fetch_ohlcv(symbol, period, interval)


# Import pandas for compatibility
try:
    import pandas as pd
except ImportError:
    pd = None
