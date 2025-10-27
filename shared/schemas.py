"""
공통 스키마 정의 - 백엔드와 프론트엔드 간 공유
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class OrganismType(str, Enum):
    """Organism 타입"""
    UNSLUG = "UNSLUG"
    FEAR_INDEX = "FearIndex"
    MARKET_FLOW = "MarketFlow"


class SignalType(str, Enum):
    """신호 타입"""
    BUY = "BUY"
    NEUTRAL = "NEUTRAL"
    RISK = "RISK"


class CityState(str, Enum):
    """도시 상태"""
    DIM = "dim"
    STABLE = "stable"
    THRIVING = "thriving"


class TrustContribution(str, Enum):
    """Trust 기여도"""
    INCREASES_TRUST = "increases_trust"
    DECREASES_TRUST = "decreases_trust"
    NEUTRAL = "neutral"


class InputSlice(BaseModel):
    """입력 데이터 슬라이스"""
    symbol: str
    interval: str = Field(..., regex="^(1d|1h|5m)$")
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: Optional[float] = None
    features: dict = Field(default_factory=dict)


class ExplainEntry(BaseModel):
    """신호 설명 항목"""
    name: str
    value: Union[float, str, None]
    contribution: TrustContribution


class OrganismOutput(BaseModel):
    """Organism 출력"""
    organism: OrganismType
    symbol: str
    ts: datetime
    signal: SignalType
    trust: float = Field(..., ge=0.0, le=1.0)
    explain: List[ExplainEntry]
    meta: Optional[dict] = None


class CityVisualizationState(BaseModel):
    """도시 시각화 상태"""
    city_state: CityState
    unslug_trust: float = Field(..., ge=0.0, le=1.0)
    fear_trust: float = Field(..., ge=0.0, le=1.0)
    flow_trust: float = Field(..., ge=0.0, le=1.0)
    notes: Optional[str] = None


class UserCreate(BaseModel):
    """사용자 생성 요청"""
    email: str = Field(..., regex=r'^[^@]+@[^@]+\.[^@]+$')
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2)


class UserLogin(BaseModel):
    """사용자 로그인 요청"""
    email: str
    password: str


class UserResponse(BaseModel):
    """사용자 응답"""
    id: int
    email: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """토큰 응답"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class SubscriptionPlan(str, Enum):
    """구독 플랜"""
    BASIC = "basic"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


class PaymentMethod(str, Enum):
    """결제 수단"""
    TOSS = "toss"
    STRIPE = "stripe"
    CRYPTO = "crypto"


class SubscriptionCreate(BaseModel):
    """구독 생성 요청"""
    plan: SubscriptionPlan
    payment_method: PaymentMethod


class WebSocketMessage(BaseModel):
    """WebSocket 메시지"""
    type: str
    data: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    """채팅 메시지"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """채팅 요청"""
    messages: List[ChatMessage]
    model: Optional[str] = "gpt-4"  # "gpt-4" or "claude-3"
