"""
Signal Approval Routes - Team approval workflow
POST /api/v1/signals/{symbol}/approve
P3.3: WebSocket approval notifications
"""
from fastapi import APIRouter, HTTPException, Query, Body
from datetime import datetime
from typing import Optional
import structlog

router = APIRouter(prefix="/api/v1", tags=["approvals"])
logger = structlog.get_logger(__name__)

# WebSocket manager for approval notifications
socket_manager = None

def set_socket_manager(sm):
    """Set socket manager instance for WebSocket broadcasts"""
    global socket_manager
    socket_manager = sm


@router.post("/signals/{symbol}/approve")
async def approve_signal(
    symbol: str,
    status: str = Body(..., embed=True),  # BUY | NEUTRAL | RISK
    user_id: Optional[str] = Body(None, embed=True),
    note: Optional[str] = Body(None, embed=True)
) -> dict:
    """
    Approve a signal (Team Gate)

    Request:
    {
        "status": "BUY" | "NEUTRAL" | "RISK",
        "user_id": "team-member-id",
        "note": "optional reasoning"
    }

    Returns:
    {
        "symbol": str,
        "approved_status": str,
        "approved_by": str,
        "approved_at": datetime,
        "note": str
    }
    """
    try:
        # Validate status
        if status not in ["BUY", "NEUTRAL", "RISK"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be BUY, NEUTRAL, or RISK"
            )

        # TODO: In production, fetch signal from DB
        # signal = await db.get_signal(symbol)
        # if not signal:
        #     raise HTTPException(status_code=404, detail=f"Signal not found for {symbol}")

        # TODO: Update signal.status in DB
        # await db.update_signal_status(signal.id, f"APPROVED_{status}")

        # TODO: Record approval in signal_approvals table
        # approval = SignalApproval(
        #     signal_id=signal.id,
        #     symbol=symbol,
        #     user_id=user_id,
        #     approved_status=status,
        #     note=note
        # )
        # db.add(approval)
        # await db.commit()

        logger.info(
            "Signal approved",
            symbol=symbol,
            status=status,
            user_id=user_id,
            note=note
        )

        # P3.3: Broadcast approval notification via WebSocket
        if socket_manager:
            approval_notification = {
                "type": "approval_notification",
                "data": {
                    "symbol": symbol.upper(),
                    "approved_status": status,
                    "approved_by": user_id or "system",
                    "approved_at": datetime.utcnow().isoformat(),
                    "note": note or ""
                },
                "timestamp": datetime.utcnow().isoformat()
            }

            # Broadcast to all connected clients
            import asyncio
            try:
                asyncio.create_task(socket_manager.broadcast_signal(approval_notification["data"], symbol=symbol.upper()))
                logger.info("Approval notification broadcasted", symbol=symbol)
            except Exception as e:
                logger.warning(f"Failed to broadcast approval notification: {e}")

        return {
            "symbol": symbol.upper(),
            "approved_status": status,
            "approved_by": user_id or "system",
            "approved_at": datetime.utcnow().isoformat(),
            "note": note or "",
            "message": f"✅ {symbol} signal approved as {status}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approval failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals/{symbol}/approvals")
async def get_signal_approvals(symbol: str) -> dict:
    """
    Get approval history for a symbol

    Returns:
    {
        "symbol": str,
        "approvals": [
            {
                "id": int,
                "approved_status": str,
                "approved_by": str,
                "approved_at": datetime,
                "note": str
            }
        ]
    }
    """
    try:
        # TODO: Fetch from signal_approvals table
        # approvals = await db.get_approvals(symbol)

        logger.info("Fetching approvals", symbol=symbol)

        return {
            "symbol": symbol.upper(),
            "approvals": []  # Empty for now, will populate from DB in P3.2
        }

    except Exception as e:
        logger.error(f"Failed to fetch approvals for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
