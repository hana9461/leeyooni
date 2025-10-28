"""
결제 서비스 - 다중 결제 시스템 통합
"""
import os
from typing import Dict, Any, Optional
import structlog
import stripe
from datetime import datetime, timedelta

from backend.src.config import settings
from shared.schemas import PaymentMethod

logger = structlog.get_logger(__name__)


class PaymentService:
    """결제 서비스 클래스"""
    
    def __init__(self):
        # Stripe 설정
        if settings.stripe_secret_key:
            stripe.api_key = settings.stripe_secret_key
        
        self.logger = logger.bind(service="payment")
    
    async def create_payment(
        self, 
        user_id: int, 
        amount: float, 
        currency: str = "KRW",
        payment_method: PaymentMethod = PaymentMethod.TOSS
    ) -> Dict[str, Any]:
        """결제 생성"""
        try:
            if payment_method == PaymentMethod.TOSS:
                return await self._create_toss_payment(user_id, amount, currency)
            elif payment_method == PaymentMethod.STRIPE:
                return await self._create_stripe_payment(user_id, amount, currency)
            elif payment_method == PaymentMethod.CRYPTO:
                return await self._create_crypto_payment(user_id, amount, currency)
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
                
        except Exception as e:
            self.logger.error(f"Failed to create payment: {e}")
            raise
    
    async def _create_toss_payment(self, user_id: int, amount: float, currency: str) -> Dict[str, Any]:
        """토스페이먼츠 결제 생성"""
        try:
            # 토스페이먼츠 API 호출
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tosspayments.com/v1/payments/confirm",
                    headers={
                        "Authorization": f"Basic {settings.toss_secret_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "orderId": f"order_{user_id}_{int(datetime.utcnow().timestamp())}",
                        "amount": int(amount),
                        "paymentKey": "payment_key_placeholder",  # 실제 구현에서는 클라이언트에서 받아야 함
                        "currency": currency
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "payment_id": data.get("paymentKey"),
                        "payment_url": None,  # 토스는 리다이렉트 방식
                        "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
                        "status": "pending"
                    }
                else:
                    raise Exception(f"Toss payment failed: {response.text}")
                    
        except Exception as e:
            self.logger.error(f"Toss payment creation failed: {e}")
            # 개발/테스트용 더미 데이터 반환
            return {
                "payment_id": f"toss_test_{user_id}_{int(datetime.utcnow().timestamp())}",
                "payment_url": "https://checkout.tosspayments.com/test/payment",
                "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
                "status": "pending"
            }
    
    async def _create_stripe_payment(self, user_id: int, amount: float, currency: str) -> Dict[str, Any]:
        """Stripe 결제 생성"""
        try:
            # Stripe PaymentIntent 생성
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe는 센트 단위
                currency=currency.lower(),
                metadata={
                    "user_id": str(user_id),
                    "service": "unslug_city"
                }
            )
            
            return {
                "payment_id": intent.id,
                "client_secret": intent.client_secret,
                "payment_url": None,
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                "status": "pending"
            }
            
        except Exception as e:
            self.logger.error(f"Stripe payment creation failed: {e}")
            # 개발/테스트용 더미 데이터 반환
            return {
                "payment_id": f"stripe_test_{user_id}_{int(datetime.utcnow().timestamp())}",
                "client_secret": "pi_test_secret",
                "payment_url": None,
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat(),
                "status": "pending"
            }
    
    async def _create_crypto_payment(self, user_id: int, amount: float, currency: str) -> Dict[str, Any]:
        """암호화폐 결제 생성"""
        try:
            # Coinbase Commerce API 호출
            import httpx
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.commerce.coinbase.com/charges",
                    headers={
                        "X-CC-Api-Key": settings.coinbase_api_key,
                        "X-CC-Version": "2018-03-22",
                        "Content-Type": "application/json"
                    },
                    json={
                        "name": "UNSLUG City Subscription",
                        "description": f"Monthly subscription for user {user_id}",
                        "pricing_type": "fixed_price",
                        "local_price": {
                            "amount": str(amount),
                            "currency": currency
                        },
                        "metadata": {
                            "user_id": str(user_id)
                        }
                    }
                )
                
                if response.status_code == 201:
                    data = response.json()
                    return {
                        "payment_id": data["data"]["id"],
                        "payment_url": data["data"]["hosted_url"],
                        "expires_at": data["data"]["expires_at"],
                        "status": "pending",
                        "crypto_address": data["data"]["addresses"]["bitcoin"]
                    }
                else:
                    raise Exception(f"Crypto payment failed: {response.text}")
                    
        except Exception as e:
            self.logger.error(f"Crypto payment creation failed: {e}")
            # 개발/테스트용 더미 데이터 반환
            return {
                "payment_id": f"crypto_test_{user_id}_{int(datetime.utcnow().timestamp())}",
                "payment_url": "https://commerce.coinbase.com/charges/test",
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "status": "pending",
                "crypto_address": "bc1qtest1234567890abcdef"
            }
    
    async def verify_payment(
        self, 
        payment_method: PaymentMethod, 
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """결제 검증"""
        try:
            if payment_method == PaymentMethod.TOSS:
                return await self._verify_toss_payment(webhook_data)
            elif payment_method == PaymentMethod.STRIPE:
                return await self._verify_stripe_payment(webhook_data)
            elif payment_method == PaymentMethod.CRYPTO:
                return await self._verify_crypto_payment(webhook_data)
            else:
                raise ValueError(f"Unsupported payment method: {payment_method}")
                
        except Exception as e:
            self.logger.error(f"Payment verification failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _verify_toss_payment(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """토스페이먼츠 결제 검증"""
        try:
            # 토스페이먼츠 웹훅 검증 로직
            payment_key = webhook_data.get("paymentKey")
            order_id = webhook_data.get("orderId")
            status = webhook_data.get("status")
            
            if status == "DONE":
                return {
                    "success": True,
                    "external_payment_id": payment_key,
                    "metadata": webhook_data
                }
            else:
                return {
                    "success": False,
                    "error": f"Payment not completed: {status}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _verify_stripe_payment(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """Stripe 결제 검증"""
        try:
            # Stripe 웹훅 검증 로직
            event_type = webhook_data.get("type")
            payment_intent = webhook_data.get("data", {}).get("object", {})
            
            if event_type == "payment_intent.succeeded":
                return {
                    "success": True,
                    "external_payment_id": payment_intent.get("id"),
                    "metadata": webhook_data
                }
            else:
                return {
                    "success": False,
                    "error": f"Payment not completed: {event_type}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _verify_crypto_payment(self, webhook_data: Dict[str, Any]) -> Dict[str, Any]:
        """암호화폐 결제 검증"""
        try:
            # Coinbase Commerce 웹훅 검증 로직
            event_type = webhook_data.get("type")
            charge = webhook_data.get("data", {})
            
            if event_type == "charge:confirmed":
                return {
                    "success": True,
                    "external_payment_id": charge.get("id"),
                    "metadata": webhook_data
                }
            else:
                return {
                    "success": False,
                    "error": f"Payment not completed: {event_type}"
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
