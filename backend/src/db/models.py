"""
데이터베이스 모델 정의
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, 
    Integer, JSON, String, Text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from backend.src.db.database import Base
from shared.schemas import OrganismType, SignalType, SubscriptionPlan, PaymentMethod


class User(Base):
    """사용자 모델"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    subscriptions = relationship("Subscription", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    watchlists = relationship("Watchlist", back_populates="user")
    notifications = relationship("Notification", back_populates="user")


class Subscription(Base):
    """구독 모델"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan = Column(Enum(SubscriptionPlan), nullable=False)
    status = Column(String(20), default="active")  # active, cancelled, expired
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="subscriptions")
    payments = relationship("Payment", back_populates="subscription")


class Payment(Base):
    """결제 모델"""
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=True)
    payment_method = Column(Enum(PaymentMethod), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="KRW")
    status = Column(String(20), default="pending")  # pending, completed, failed, refunded
    external_id = Column(String(255), nullable=True)  # 외부 결제 시스템 ID
    payment_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")


class Signal(Base):
    """신호 모델 (P3.1: UNSLUG + Fear&Greed 신호 저장)"""
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    organism = Column(Enum(OrganismType), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)

    # P3 신호 점수
    unslug_score = Column(Float, nullable=True)  # [0,1]
    fear_score = Column(Float, nullable=True)    # [0,1]
    combined_trust = Column(Float, nullable=True)  # [0,1]

    # 신호 상태
    signal = Column(Enum(SignalType), nullable=False)
    trust = Column(Float, nullable=False)
    status = Column(String(50), default="PENDING_REVIEW")  # PENDING_REVIEW, APPROVED_BUY, APPROVED_RISK, APPROVED_NEUTRAL

    # 설명 & 메타
    explain = Column(JSON, nullable=True)  # ExplainEntry 리스트
    recommendation = Column(JSON, nullable=True)  # {suggested: BUY|RISK|NEUTRAL, logic: str}
    meta = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    approvals = relationship("SignalApproval", back_populates="signal")

    # Indexes for efficient querying
    __table_args__ = (
        {"extend_existing": True},
    )


class Watchlist(Base):
    """관심 종목 모델"""
    __tablename__ = "watchlists"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="watchlists")


class Notification(Base):
    """알림 모델"""
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)  # signal, system, payment, etc.
    is_read = Column(Boolean, default=False)
    notification_data = Column(JSON, nullable=True)  # 추가 데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="notifications")


class ChatSession(Base):
    """채팅 세션 모델"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=True)
    model = Column(String(50), default="gpt-4")  # gpt-4, claude-3
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ChatMessage(Base):
    """채팅 메시지 모델"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    session = relationship("ChatSession")


class SignalApproval(Base):
    """신호 승인 모델 (P3.1: 팀원의 신호 승인 기록)"""
    __tablename__ = "signal_approvals"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)

    # 승인자 정보
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null이면 system approval
    approved_status = Column(String(50), nullable=False)  # BUY, RISK, NEUTRAL

    # 승인 메모
    note = Column(Text, nullable=True)

    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    signal = relationship("Signal", back_populates="approvals")
    user = relationship("User")
