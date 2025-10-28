"""
UNSLUG API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from typing import List, Optional
import structlog
from datetime import datetime, timedelta

from backend.src.core.unslug import unslug_calculator, UnslugConfig
from backend.src.api.auth import get_current_user
from backend.src.db.models import User

logger = structlog.get_logger(__name__)

router = APIRouter()

# 기본 워치리스트
DEFAULT_WATCHLIST = [
    "UNH", "AAPL", "MSFT", "NVDA", "META", "GOOGL", "AMZN", "AVGO",
    "ADBE", "COST", "PEP", "LLY", "JPM", "XOM", "LIN", "NFLX",
    "TSLA", "COIN", "PLTR", "MDB", "SHOP", "CRWD", "SNOW", "RBLX"
]

# 간단한 메모리 캐시 (나중에 Redis로 교체 가능)
_cache = {}
_cache_ttl = {}


def get_cached_signals(cache_key: str) -> Optional[List]:
    """캐시에서 신호 가져오기"""
    if cache_key in _cache:
        # TTL 체크 (1시간)
        if datetime.utcnow() < _cache_ttl.get(cache_key, datetime.utcnow()):
            return _cache[cache_key]
    return None


def set_cached_signals(cache_key: str, signals: List):
    """신호 캐시 저장"""
    _cache[cache_key] = signals
    _cache_ttl[cache_key] = datetime.utcnow() + timedelta(hours=1)


@router.get("/scan")
async def scan_unslug_signals(
    current_user: User = Depends(get_current_user)
):
    """
    UNSLUG 신호 스캔
    - 구독자만 접근 가능
    - 워치리스트의 모든 종목 스캔
    """
    try:
        # 캐시 체크
        cache_key = "unslug_signals"
        cached = get_cached_signals(cache_key)

        if cached is not None:
            logger.info("Returning cached UNSLUG signals", user_id=current_user.id)
            return {
                "signals": cached,
                "cached": True,
                "scanned_at": _cache_ttl.get(cache_key).isoformat()
            }

        # 워치리스트 스캔
        logger.info("Scanning UNSLUG signals", user_id=current_user.id)
        signals = unslug_calculator.scan_watchlist(DEFAULT_WATCHLIST)

        # 캐시 저장
        set_cached_signals(cache_key, signals)

        return {
            "signals": signals,
            "cached": False,
            "scanned_at": datetime.utcnow().isoformat(),
            "total_signals": len(signals)
        }

    except Exception as e:
        logger.error(f"UNSLUG scan failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to scan UNSLUG signals"
        )


@router.get("/signal/{ticker}")
async def get_unslug_signal(
    ticker: str,
    current_user: User = Depends(get_current_user)
):
    """
    특정 종목의 UNSLUG 신호 조회
    - 구독자만 접근 가능
    """
    try:
        ticker = ticker.upper()

        # 캐시 체크
        cache_key = f"unslug_signal_{ticker}"
        cached = get_cached_signals(cache_key)

        if cached is not None:
            logger.info(f"Returning cached UNSLUG signal for {ticker}", user_id=current_user.id)
            return cached[0] if cached else None

        # 신호 계산
        logger.info(f"Calculating UNSLUG signal for {ticker}", user_id=current_user.id)
        signal = unslug_calculator.calculate_signal(ticker)

        if signal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No UNSLUG signal found for {ticker}"
            )

        # 캐시 저장
        set_cached_signals(cache_key, [signal])

        return signal

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"UNSLUG signal calculation failed for {ticker}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate UNSLUG signal"
        )


@router.get("/preview")
async def get_unslug_preview():
    """
    UNSLUG 미리보기
    - 로그인 불필요
    - 신호 개수만 반환 (티커는 숨김)
    """
    try:
        # 캐시 체크
        cache_key = "unslug_signals"
        cached = get_cached_signals(cache_key)

        if cached is not None:
            return {
                "signal_count": len(cached),
                "message": "Login to see signals",
                "scanned_at": _cache_ttl.get(cache_key).isoformat()
            }

        # 신호 스캔
        signals = unslug_calculator.scan_watchlist(DEFAULT_WATCHLIST)
        set_cached_signals(cache_key, signals)

        return {
            "signal_count": len(signals),
            "message": "Login to see signals",
            "scanned_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"UNSLUG preview failed: {e}")
        return {
            "signal_count": 0,
            "message": "Unable to scan signals",
            "error": str(e)
        }
