"""
Signals API Routes
GET /api/v1/signals/{symbol}
GET /api/v1/scan/top?n=10
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import List, Dict, Optional
import structlog

from shared.schemas import OrganismType, SignalType
from backend.src.core.organisms import organism_manager
from backend.src.adapters.data.yahoo import fetch_symbol_daily

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["signals"])


@router.get("/signals/{symbol}")
async def get_signal(symbol: str) -> Dict:
    """
    Get latest signal for a symbol

    Returns:
    {
        "symbol": str,
        "ts": datetime,
        "unslug_score": float (0-1),
        "fear_score": float (0-1),
        "combined_trust": float (0-1),
        "status": "PENDING_REVIEW",
        "recommendation": {...},
        "explain": [...]
    }
    """
    try:
        # Fetch data
        data = fetch_symbol_daily(symbol.upper(), lookback=30)
        if not data:
            raise HTTPException(status_code=404, detail=f"No data for {symbol}")

        # Compute organisms
        outputs = await organism_manager.compute_all_organisms(data)

        # Extract scores
        unslug_output = outputs.get(OrganismType.UNSLUG)
        fear_output = outputs.get(OrganismType.FEAR_INDEX)

        unslug_score = unslug_output.trust if unslug_output else 0.5
        fear_score = fear_output.trust if fear_output else 0.5

        # Combined trust (geometric mean)
        combined_trust = (unslug_score * fear_score) ** 0.5 if unslug_score > 0 and fear_score > 0 else 0.5

        # Recommendation logic: unslug >= 0.6 & fear >= 0.5 → BUY
        if unslug_score >= 0.6 and fear_score >= 0.5:
            recommended_status = "BUY"
        elif unslug_score < 0.4 or fear_score < 0.3:
            recommended_status = "RISK"
        else:
            recommended_status = "NEUTRAL"

        return {
            "symbol": symbol.upper(),
            "ts": datetime.utcnow().isoformat(),
            "unslug_score": round(unslug_score, 3),
            "fear_score": round(fear_score, 3),
            "combined_trust": round(combined_trust, 3),
            "status": "PENDING_REVIEW",
            "recommendation": {
                "suggested": recommended_status,
                "unslug": unslug_score,
                "fear": fear_score,
                "logic": f"unslug={unslug_score:.2f} & fear={fear_score:.2f}"
            },
            "explain": {
                "unslug": [e.dict() for e in (unslug_output.explain if unslug_output else [])],
                "fear": [e.dict() for e in (fear_output.explain if fear_output else [])]
            },
            "awaiting_approval": True
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signal fetch error for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/top")
async def scan_top_signals(n: int = Query(10, ge=1, le=100)) -> Dict:
    """
    Get top N signals by combined trust score

    Returns:
    {
        "count": int,
        "signals": [
            {...same as get_signal...}
        ]
    }
    """
    try:
        # Sample watchlist (can be extended)
        watchlist = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]

        signals = []
        for symbol in watchlist:
            try:
                signal = await get_signal(symbol)
                signals.append(signal)
            except Exception as e:
                logger.warning(f"Skipping {symbol}: {e}")
                continue

        # Sort by combined_trust descending
        signals.sort(key=lambda x: x.get("combined_trust", 0), reverse=True)

        # Limit to n
        signals = signals[:n]

        return {
            "count": len(signals),
            "top_n": n,
            "signals": signals
        }

    except Exception as e:
        logger.error(f"Scan top signals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
