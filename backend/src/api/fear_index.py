"""
Fear Index API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
import structlog
from datetime import datetime, timedelta, date

from src.core.fear_index import fear_calculator
from src.api.auth import get_current_user
from src.db.models import User

logger = structlog.get_logger(__name__)

router = APIRouter()

# 간단한 메모리 캐시
_cache = {}
_cache_date = {}


def get_cached_fear_index(ticker: str) -> Optional[dict]:
    """캐시에서 Fear Index 가져오기 (당일 데이터만)"""
    today = date.today()

    if ticker in _cache and _cache_date.get(ticker) == today:
        return _cache[ticker]

    return None


def set_cached_fear_index(ticker: str, data: dict):
    """Fear Index 캐시 저장"""
    _cache[ticker] = data
    _cache_date[ticker] = date.today()


@router.get("/search")
async def search_fear_index(
    ticker: str = Query(..., description="Stock ticker symbol"),
    current_user: User = Depends(get_current_user)
):
    """
    특정 종목의 Fear Index 조회
    - 로그인 필요
    - 당일 데이터는 캐싱됨
    """
    try:
        ticker = ticker.upper()

        # 캐시 체크
        cached = get_cached_fear_index(ticker)
        if cached is not None:
            logger.info(f"Returning cached Fear Index for {ticker}", user_id=current_user.id)
            return {
                **cached,
                "cached": True
            }

        # Fear Index 계산
        logger.info(f"Calculating Fear Index for {ticker}", user_id=current_user.id)
        result = fear_calculator.calculate_fear_index(ticker)

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )

        # 캐시 저장
        set_cached_fear_index(ticker, result)

        return {
            **result,
            "cached": False
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fear Index calculation failed for {ticker}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate Fear Index: {str(e)}"
        )


@router.get("/preview/{ticker}")
async def preview_fear_index(ticker: str):
    """
    Fear Index 미리보기 (로그인 불필요)
    - 기본 정보만 반환
    """
    try:
        ticker = ticker.upper()

        # 캐시 체크
        cached = get_cached_fear_index(ticker)
        if cached is not None:
            return {
                "symbol": cached["symbol"],
                "date": cached["date"],
                "fear_index": cached["fear_index"],
                "regime": cached["regime"],
                "message": "Login to see detailed analysis"
            }

        # 간단한 계산
        result = fear_calculator.calculate_fear_index(ticker)

        if "error" in result:
            return {
                "symbol": ticker,
                "message": "Data not available",
                "error": result["error"]
            }

        return {
            "symbol": result["symbol"],
            "date": result["date"],
            "fear_index": result["fear_index"],
            "regime": result["regime"],
            "message": "Login to see detailed analysis"
        }

    except Exception as e:
        logger.error(f"Fear Index preview failed for {ticker}: {e}")
        return {
            "symbol": ticker,
            "message": "Unable to calculate Fear Index",
            "error": str(e)
        }


@router.delete("/cache")
async def clear_fear_index_cache(
    current_user: User = Depends(get_current_user)
):
    """캐시 초기화 (관리자용)"""
    try:
        _cache.clear()
        _cache_date.clear()

        logger.info("Fear Index cache cleared", user_id=current_user.id)

        return {
            "message": "Cache cleared successfully"
        }

    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear cache"
        )
