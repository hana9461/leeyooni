"""
구독 API 엔드포인트
"""
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from src.db.database import get_db
from src.db.models import User, Subscription, SubscriptionPlan
from src.api.auth import get_current_user
from shared.schemas import SubscriptionCreate

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/")
async def get_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """현재 구독 정보 조회"""
    try:
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == current_user.id)
            .order_by(Subscription.created_at.desc())
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            return {
                "has_subscription": False,
                "message": "No active subscription found"
            }
        
        return {
            "has_subscription": True,
            "subscription": {
                "id": subscription.id,
                "plan": subscription.plan.value,
                "status": subscription.status,
                "started_at": subscription.started_at,
                "expires_at": subscription.expires_at,
                "is_active": subscription.expires_at > datetime.utcnow() and subscription.status == "active"
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve subscription"
        )


@router.post("/create")
async def create_subscription(
    subscription_data: SubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 생성"""
    try:
        # 기존 활성 구독 확인
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == current_user.id)
            .where(Subscription.status == "active")
            .where(Subscription.expires_at > datetime.utcnow())
        )
        existing_subscription = result.scalar_one_or_none()
        
        if existing_subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User already has an active subscription"
            )
        
        # 구독 기간 설정
        plan_duration = {
            SubscriptionPlan.BASIC: 30,      # 30일
            SubscriptionPlan.PREMIUM: 30,    # 30일
            SubscriptionPlan.ENTERPRISE: 365 # 1년
        }
        
        duration_days = plan_duration.get(subscription_data.plan, 30)
        expires_at = datetime.utcnow() + timedelta(days=duration_days)
        
        # 구독 생성
        subscription = Subscription(
            user_id=current_user.id,
            plan=subscription_data.plan,
            status="pending",  # 결제 완료 후 active로 변경
            expires_at=expires_at
        )
        
        db.add(subscription)
        await db.commit()
        await db.refresh(subscription)
        
        logger.info("Subscription created", 
                   user_id=current_user.id, 
                   plan=subscription_data.plan.value,
                   payment_method=subscription_data.payment_method.value)
        
        return {
            "subscription_id": subscription.id,
            "plan": subscription.plan.value,
            "status": subscription.status,
            "expires_at": subscription.expires_at,
            "next_step": "payment_required"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription"
        )


@router.post("/cancel")
async def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 취소"""
    try:
        # 활성 구독 찾기
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == current_user.id)
            .where(Subscription.status == "active")
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        # 구독 취소
        subscription.status = "cancelled"
        await db.commit()
        
        logger.info("Subscription cancelled", 
                   user_id=current_user.id, 
                   subscription_id=subscription.id)
        
        return {
            "message": "Subscription cancelled successfully",
            "subscription_id": subscription.id,
            "cancelled_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription"
        )


@router.post("/upgrade")
async def upgrade_subscription(
    new_plan: SubscriptionPlan,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """구독 업그레이드"""
    try:
        # 현재 구독 찾기
        result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == current_user.id)
            .where(Subscription.status == "active")
        )
        current_subscription = result.scalar_one_or_none()
        
        if not current_subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription found"
            )
        
        # 같은 플랜인지 확인
        if current_subscription.plan == new_plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Already subscribed to this plan"
            )
        
        # 업그레이드 가능한지 확인
        plan_hierarchy = {
            SubscriptionPlan.BASIC: 1,
            SubscriptionPlan.PREMIUM: 2,
            SubscriptionPlan.ENTERPRISE: 3
        }
        
        current_level = plan_hierarchy.get(current_subscription.plan, 0)
        new_level = plan_hierarchy.get(new_plan, 0)
        
        if new_level <= current_level:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only upgrade to a higher tier plan"
            )
        
        # 구독 업그레이드
        current_subscription.plan = new_plan
        await db.commit()
        
        logger.info("Subscription upgraded", 
                   user_id=current_user.id, 
                   from_plan=current_subscription.plan.value,
                   to_plan=new_plan.value)
        
        return {
            "message": "Subscription upgraded successfully",
            "subscription_id": current_subscription.id,
            "new_plan": new_plan.value,
            "upgraded_at": datetime.utcnow()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upgrade subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upgrade subscription"
        )
