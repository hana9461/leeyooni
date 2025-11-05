"""
신호 API 엔드포인트
"""
from typing import List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timedelta

from backend.src.db.database import get_db
from backend.src.db.models import User, Signal, Watchlist
from backend.src.api.auth import get_current_user
from backend.src.core.organisms import organism_manager
from backend.src.core.fear_index import fear_calculator
from shared.schemas import (
    OrganismType, OrganismOutput, CityVisualizationState, 
    CityState, InputSlice
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/{organism}", response_model=OrganismOutput)
async def get_organism_signal(
    organism: OrganismType,
    symbol: str = Query(..., description="종목 심볼 (예: AAPL, TSLA)"),
    current_user: User = Depends(get_current_user)
):
    """특정 organism의 신호 조회"""
    try:
        # TODO: 실제 데이터 소스에서 데이터 가져오기
        # 현재는 모의 데이터 사용
        mock_data = await _get_mock_data(symbol)
        
        # Organism 계산
        result = await organism_manager.compute_single_organism(organism, mock_data)
        
        # 결과를 DB에 저장
        # TODO: DB 저장 로직 추가
        
        logger.info("Organism signal retrieved", 
                   organism=organism.value, 
                   symbol=symbol, 
                   user_id=current_user.id)
        
        return result
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get organism signal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve signal"
        )


@router.get("/symbol/{symbol}", response_model=List[OrganismOutput])
async def get_symbol_signals(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """특정 종목의 모든 organism 신호 조회"""
    try:
        # TODO: 실제 데이터 소스에서 데이터 가져오기
        mock_data = await _get_mock_data(symbol)
        
        # 모든 organism 계산
        results = await organism_manager.compute_all_organisms(mock_data)
        
        # 결과를 리스트로 변환
        organism_outputs = list(results.values())
        
        logger.info("All organism signals retrieved", 
                   symbol=symbol, 
                   user_id=current_user.id)
        
        return organism_outputs
        
    except Exception as e:
        logger.error(f"Failed to get symbol signals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve signals"
        )


@router.get("/city/state", response_model=CityVisualizationState)
async def get_city_state(
    symbol: str = Query("AAPL", description="기준 종목 심볼"),
    current_user: User = Depends(get_current_user)
):
    """도시 시각화 상태 조회"""
    try:
        # 모든 organism 신호 계산
        mock_data = await _get_mock_data(symbol)
        organism_outputs = await organism_manager.compute_all_organisms(mock_data)
        
        # Trust score 추출
        unslug_trust = organism_outputs[OrganismType.UNSLUG].trust
        fear_trust = organism_outputs[OrganismType.FEAR_INDEX].trust
        flow_trust = organism_outputs[OrganismType.MARKET_FLOW].trust
        
        # 도시 상태 결정 (평균 trust 기반)
        avg_trust = (unslug_trust + fear_trust + flow_trust) / 3
        
        if avg_trust >= 0.7:
            city_state = CityState.THRIVING
        elif avg_trust >= 0.4:
            city_state = CityState.STABLE
        else:
            city_state = CityState.DIM
        
        city_visualization = CityVisualizationState(
            city_state=city_state,
            unslug_trust=unslug_trust,
            fear_trust=fear_trust,
            flow_trust=flow_trust,
            notes=f"Based on {symbol} analysis"
        )
        
        logger.info("City state retrieved", 
                   symbol=symbol, 
                   city_state=city_state.value,
                   avg_trust=avg_trust,
                   user_id=current_user.id)
        
        return city_visualization
        
    except Exception as e:
        logger.error(f"Failed to get city state: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve city state"
        )


@router.get("/history/{symbol}")
async def get_signal_history(
    symbol: str,
    organism: Optional[OrganismType] = Query(None, description="특정 organism 필터"),
    limit: int = Query(50, ge=1, le=100, description="조회할 레코드 수"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """신호 히스토리 조회"""
    try:
        query = select(Signal).where(Signal.symbol == symbol.upper())
        
        if organism:
            query = query.where(Signal.organism == organism)
        
        query = query.order_by(desc(Signal.created_at)).limit(limit)
        
        result = await db.execute(query)
        signals = result.scalars().all()
        
        logger.info("Signal history retrieved", 
                   symbol=symbol, 
                   organism=organism.value if organism else "all",
                   count=len(signals),
                   user_id=current_user.id)
        
        return {
            "symbol": symbol,
            "organism": organism.value if organism else "all",
            "signals": [
                {
                    "id": signal.id,
                    "organism": signal.organism.value,
                    "signal": signal.signal.value,
                    "trust": signal.trust,
                    "created_at": signal.created_at,
                    "explain": signal.explain
                }
                for signal in signals
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get signal history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve signal history"
        )


@router.get("/fear-index/{symbol}")
async def get_fear_index(
    symbol: str,
    current_user: User = Depends(get_current_user)
):
    """개별종목 Fear & Greed Index 계산"""
    try:
        # Fear Index 계산
        result = fear_calculator.calculate_fear_index(symbol.upper())
        
        logger.info("Fear index calculated", 
                   symbol=symbol, 
                   fear_index=result.get("fear_index"),
                   regime=result.get("regime"),
                   user_id=current_user.id)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to calculate fear index: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate fear index"
        )


async def _get_mock_data(symbol: str) -> List[InputSlice]:
    """모의 데이터 생성 (실제로는 데이터 소스에서 가져와야 함)"""
    from datetime import datetime, timedelta
    import random
    
    # 30일간의 모의 데이터 생성
    data = []
    base_price = 150.0
    
    for i in range(30):
        date = datetime.utcnow() - timedelta(days=29-i)
        
        # 가격 변동 시뮬레이션
        change = random.uniform(-0.05, 0.05)  # ±5% 변동
        base_price *= (1 + change)
        
        high = base_price * random.uniform(1.0, 1.03)
        low = base_price * random.uniform(0.97, 1.0)
        open_price = base_price * random.uniform(0.99, 1.01)
        close = base_price
        volume = random.randint(1000000, 10000000)
        
        data.append(InputSlice(
            symbol=symbol.upper(),
            interval="1d",
            ts=date,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close, 2),
            volume=volume,
            adj_close=round(close, 2),
            features={
                "rsi": random.uniform(20, 80),
                "vwap_deviation": random.uniform(-0.02, 0.02),
                "rolling_vol": random.uniform(0.01, 0.05),
                "liquidity_ratio": random.uniform(0.5, 2.0),
                "sentiment": random.uniform(-1, 1)
            }
        ))
    
    return data
