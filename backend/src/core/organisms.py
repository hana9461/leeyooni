"""
Organism 로직 통합 - UNSLUG, FearIndex, MarketFlow
기존 코드를 기반으로 한 통합 인터페이스
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import structlog

from shared.schemas import (
    OrganismType, InputSlice, OrganismOutput, 
    SignalType, ExplainEntry, TrustContribution
)

logger = structlog.get_logger(__name__)


class BaseOrganism:
    """Organism 기본 클래스"""
    
    def __init__(self, organism_type: OrganismType):
        self.organism_type = organism_type
        self.logger = logger.bind(organism=organism_type.value)
    
    async def compute_trust(self, series: List[InputSlice]) -> OrganismOutput:
        """
        신호와 trust score를 계산하여 반환
        기존 organism 로직을 호출하는 래퍼
        """
        if not series:
            raise ValueError("Input series cannot be empty")
        
        latest_slice = series[-1]
        
        try:
            # 각 organism별 로직 호출
            if self.organism_type == OrganismType.UNSLUG:
                result = await self._compute_unslug(series)
            elif self.organism_type == OrganismType.FEAR_INDEX:
                result = await self._compute_fear_index(series)
            elif self.organism_type == OrganismType.MARKET_FLOW:
                result = await self._compute_market_flow(series)
            else:
                raise ValueError(f"Unknown organism type: {self.organism_type}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to compute trust: {e}")
            # 에러 시 기본값 반환
            return OrganismOutput(
                organism=self.organism_type,
                symbol=latest_slice.symbol,
                ts=datetime.utcnow(),
                signal=SignalType.NEUTRAL,
                trust=0.0,
                explain=[
                    ExplainEntry(
                        name="error",
                        value=str(e),
                        contribution=TrustContribution.DECREASES_TRUST
                    )
                ]
            )
    
    async def _compute_unslug(self, series: List[InputSlice]) -> OrganismOutput:
        """UNSLUG organism 계산"""
        # TODO: 기존 UNSLUG 로직 통합
        # 현재는 기본 구현
        
        latest = series[-1]
        trust_factors = []
        
        # 기본 trust 계산 로직
        if len(series) >= 20:  # 충분한 데이터가 있는 경우
            # 단순한 RSI 기반 계산 예시
            recent_closes = [s.close for s in series[-14:]]
            price_change = (recent_closes[-1] - recent_closes[0]) / recent_closes[0]
            
            if price_change < -0.05:  # 5% 이상 하락
                signal = SignalType.BUY
                trust = 0.7
                trust_factors.append(
                    ExplainEntry(
                        name="price_drop",
                        value=f"{price_change:.2%}",
                        contribution=TrustContribution.INCREASES_TRUST
                    )
                )
            elif price_change > 0.05:  # 5% 이상 상승
                signal = SignalType.RISK
                trust = 0.3
                trust_factors.append(
                    ExplainEntry(
                        name="price_rise",
                        value=f"{price_change:.2%}",
                        contribution=TrustContribution.DECREASES_TRUST
                    )
                )
            else:
                signal = SignalType.NEUTRAL
                trust = 0.5
                trust_factors.append(
                    ExplainEntry(
                        name="stable_price",
                        value=f"{price_change:.2%}",
                        contribution=TrustContribution.NEUTRAL
                    )
                )
        else:
            signal = SignalType.NEUTRAL
            trust = 0.0
            trust_factors.append(
                ExplainEntry(
                    name="insufficient_data",
                    value=f"{len(series)} periods",
                    contribution=TrustContribution.DECREASES_TRUST
                )
            )
        
        return OrganismOutput(
            organism=OrganismType.UNSLUG,
            symbol=latest.symbol,
            ts=datetime.utcnow(),
            signal=signal,
            trust=trust,
            explain=trust_factors
        )
    
    async def _compute_fear_index(self, series: List[InputSlice]) -> OrganismOutput:
        """FearIndex organism 계산"""
        # TODO: 기존 FearIndex 로직 통합
        
        latest = series[-1]
        trust_factors = []
        
        # 기본 변동성 기반 계산
        if len(series) >= 20:
            prices = [s.close for s in series[-20:]]
            returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
            volatility = (sum(r**2 for r in returns) / len(returns))**0.5
            
            if volatility > 0.03:  # 3% 이상 변동성
                signal = SignalType.RISK
                trust = 0.8
                trust_factors.append(
                    ExplainEntry(
                        name="high_volatility",
                        value=f"{volatility:.2%}",
                        contribution=TrustContribution.INCREASES_TRUST
                    )
                )
            else:
                signal = SignalType.NEUTRAL
                trust = 0.6
                trust_factors.append(
                    ExplainEntry(
                        name="low_volatility",
                        value=f"{volatility:.2%}",
                        contribution=TrustContribution.NEUTRAL
                    )
                )
        else:
            signal = SignalType.NEUTRAL
            trust = 0.0
            trust_factors.append(
                ExplainEntry(
                    name="insufficient_data",
                    value=f"{len(series)} periods",
                    contribution=TrustContribution.DECREASES_TRUST
                )
            )
        
        return OrganismOutput(
            organism=OrganismType.FEAR_INDEX,
            symbol=latest.symbol,
            ts=datetime.utcnow(),
            signal=signal,
            trust=trust,
            explain=trust_factors
        )
    
    async def _compute_market_flow(self, series: List[InputSlice]) -> OrganismOutput:
        """MarketFlow organism 계산"""
        # TODO: 기존 MarketFlow 로직 통합
        
        latest = series[-1]
        trust_factors = []
        
        # 기본 거래량 기반 계산
        if len(series) >= 10:
            volumes = [s.volume for s in series[-10:]]
            avg_volume = sum(volumes[:-1]) / len(volumes[:-1])
            current_volume = volumes[-1]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            if volume_ratio > 1.5:  # 거래량 50% 증가
                signal = SignalType.BUY
                trust = 0.7
                trust_factors.append(
                    ExplainEntry(
                        name="high_volume",
                        value=f"{volume_ratio:.2f}x",
                        contribution=TrustContribution.INCREASES_TRUST
                    )
                )
            elif volume_ratio < 0.5:  # 거래량 50% 감소
                signal = SignalType.RISK
                trust = 0.3
                trust_factors.append(
                    ExplainEntry(
                        name="low_volume",
                        value=f"{volume_ratio:.2f}x",
                        contribution=TrustContribution.DECREASES_TRUST
                    )
                )
            else:
                signal = SignalType.NEUTRAL
                trust = 0.5
                trust_factors.append(
                    ExplainEntry(
                        name="normal_volume",
                        value=f"{volume_ratio:.2f}x",
                        contribution=TrustContribution.NEUTRAL
                    )
                )
        else:
            signal = SignalType.NEUTRAL
            trust = 0.0
            trust_factors.append(
                ExplainEntry(
                    name="insufficient_data",
                    value=f"{len(series)} periods",
                    contribution=TrustContribution.DECREASES_TRUST
                )
            )
        
        return OrganismOutput(
            organism=OrganismType.MARKET_FLOW,
            symbol=latest.symbol,
            ts=datetime.utcnow(),
            signal=signal,
            trust=trust,
            explain=trust_factors
        )


class OrganismManager:
    """Organism 관리자"""
    
    def __init__(self):
        self.organisms = {
            OrganismType.UNSLUG: BaseOrganism(OrganismType.UNSLUG),
            OrganismType.FEAR_INDEX: BaseOrganism(OrganismType.FEAR_INDEX),
            OrganismType.MARKET_FLOW: BaseOrganism(OrganismType.MARKET_FLOW),
        }
    
    async def compute_all_organisms(self, series: List[InputSlice]) -> Dict[OrganismType, OrganismOutput]:
        """모든 organism에 대해 신호 계산"""
        results = {}
        
        for organism_type, organism in self.organisms.items():
            try:
                result = await organism.compute_trust(series)
                results[organism_type] = result
            except Exception as e:
                logger.error(f"Failed to compute {organism_type}: {e}")
                # 에러 시 기본값 추가
                results[organism_type] = OrganismOutput(
                    organism=organism_type,
                    symbol=series[-1].symbol if series else "UNKNOWN",
                    ts=datetime.utcnow(),
                    signal=SignalType.NEUTRAL,
                    trust=0.0,
                    explain=[
                        ExplainEntry(
                            name="error",
                            value=str(e),
                            contribution=TrustContribution.DECREASES_TRUST
                        )
                    ]
                )
        
        return results
    
    async def compute_single_organism(self, organism_type: OrganismType, series: List[InputSlice]) -> OrganismOutput:
        """단일 organism 신호 계산"""
        if organism_type not in self.organisms:
            raise ValueError(f"Unknown organism type: {organism_type}")
        
        return await self.organisms[organism_type].compute_trust(series)


# 전역 organism manager 인스턴스
organism_manager = OrganismManager()
