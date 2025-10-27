"""
결제 API 엔드포인트
"""
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from src.db.database import get_db
from src.db.models import User, Payment, Subscription, SubscriptionPlan, PaymentMethod
from src.api.auth import get_current_user
from src.services.payment_service import PaymentService

logger = structlog.get_logger(__name__)

router = APIRouter()
payment_service = PaymentService()


@router.post("/create")
async def create_payment(
    amount: float,
    currency: str = "KRW",
    method: str = "toss",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """결제 생성"""
    try:
        # 결제 방법 검증
        try:
            payment_method = PaymentMethod(method)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment method"
            )
        
        # 결제 생성
        payment_result = await payment_service.create_payment(
            user_id=current_user.id,
            amount=amount,
            currency=currency,
            payment_method=payment_method
        )
        
        # DB에 결제 기록 저장
        payment_record = Payment(
            user_id=current_user.id,
            payment_method=payment_method,
            amount=amount,
            currency=currency,
            status="pending",
            external_id=payment_result.get("payment_id"),
            metadata=payment_result
        )
        
        db.add(payment_record)
        await db.commit()
        await db.refresh(payment_record)
        
        logger.info("Payment created", 
                   user_id=current_user.id, 
                   amount=amount, 
                   method=method)
        
        return {
            "payment_id": payment_record.id,
            "external_payment_id": payment_result.get("payment_id"),
            "amount": amount,
            "currency": currency,
            "status": "pending",
            "payment_url": payment_result.get("payment_url"),
            "expires_at": payment_result.get("expires_at")
        }
        
    except Exception as e:
        logger.error(f"Failed to create payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment"
        )


@router.post("/webhook/{method}")
async def payment_webhook(
    method: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """결제 웹훅 처리"""
    try:
        # 결제 방법 검증
        try:
            payment_method = PaymentMethod(method)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment method"
            )
        
        # 웹훅 데이터 가져오기
        if method == "toss":
            webhook_data = await request.json()
        elif method == "stripe":
            webhook_data = await request.json()
        elif method == "crypto":
            webhook_data = await request.json()
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported payment method"
            )
        
        # 결제 검증 및 처리
        verification_result = await payment_service.verify_payment(
            payment_method=payment_method,
            webhook_data=webhook_data
        )
        
        if verification_result["success"]:
            # 결제 상태 업데이트
            external_id = verification_result["external_payment_id"]
            result = await db.execute(
                select(Payment).where(Payment.external_id == external_id)
            )
            payment = result.scalar_one_or_none()
            
            if payment:
                payment.status = "completed"
                payment.metadata = verification_result.get("metadata", {})
                await db.commit()
                
                logger.info("Payment completed", 
                           payment_id=payment.id, 
                           external_id=external_id)
                
                # 구독 활성화 (필요한 경우)
                await _activate_subscription_if_needed(payment, db)
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Payment webhook failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """결제 내역 조회"""
    try:
        result = await db.execute(
            select(Payment)
            .where(Payment.user_id == current_user.id)
            .order_by(Payment.created_at.desc())
            .limit(50)
        )
        payments = result.scalars().all()
        
        return {
            "payments": [
                {
                    "id": payment.id,
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": payment.status,
                    "payment_method": payment.payment_method.value,
                    "created_at": payment.created_at,
                    "metadata": payment.metadata
                }
                for payment in payments
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get payment history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment history"
        )


async def _activate_subscription_if_needed(payment: Payment, db: AsyncSession):
    """결제 완료 시 구독 활성화"""
    try:
        # 결제와 연결된 구독이 있는지 확인
        result = await db.execute(
            select(Subscription).where(Subscription.user_id == payment.user_id)
        )
        subscription = result.scalar_one_or_none()
        
        if not subscription:
            # 기본 구독 생성 (Basic 플랜, 1개월)
            subscription = Subscription(
                user_id=payment.user_id,
                plan=SubscriptionPlan.BASIC,
                status="active",
                started_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            db.add(subscription)
            await db.commit()
            
            logger.info("Subscription activated", 
                       user_id=payment.user_id, 
                       plan=subscription.plan.value)
        
    except Exception as e:
        logger.error(f"Failed to activate subscription: {e}")
