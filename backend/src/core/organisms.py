"""
Organism 로직 통합 - UNSLUG, FearIndex, MarketFlow
P3: UNSLUG Scanner + Fear&Greed Index 통합
"""
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import structlog
import numpy as np

from shared.schemas import (
    OrganismType, InputSlice, OrganismOutput,
    SignalType, ExplainEntry, TrustContribution
)
from backend.src.core.unslug_scanner import unslug_scanner
from backend.src.core.fear_index_ticker import fear_index

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
        """
        UNSLUG organism 계산 (P3: UnslugScanner 통합)

        Logic:
        - UnslugScanner로 UNSLUG Score 계산 (0-1)
        - trust = unslug_score (이미 0-1 범위)
        - signal은 아직 PENDING_REVIEW (팀 승인 필요)
        """
        latest = series[-1]
        trust_factors = []

        try:
            # UNSLUG Scanner 실행
            result = unslug_scanner.scan(series)

            # Score 추출
            unslug_score = result.get('unslug_score', 0.5)
            band = result.get('band', 'N/A')
            signal_strength = result.get('signal_strength', 0.5)

            # Trust = UNSLUG Score (0-1 범위)
            trust = float(np.clip(unslug_score, 0, 1))

            # Signal은 PENDING_REVIEW (팀이 승인할 때까지)
            signal = SignalType.NEUTRAL

            # Explain 구성
            trust_factors = [
                ExplainEntry(
                    name="unslug_score",
                    value=f"{unslug_score:.3f}",
                    contribution=TrustContribution.INCREASES_TRUST if unslug_score > 0.5 else TrustContribution.DECREASES_TRUST
                ),
                ExplainEntry(
                    name="band",
                    value=band,
                    contribution=TrustContribution.NEUTRAL
                ),
                ExplainEntry(
                    name="low_price",
                    value=f"${result.get('low_val', 0):.2f}" if result.get('low_val') else "N/A",
                    contribution=TrustContribution.NEUTRAL
                ),
                ExplainEntry(
                    name="current_price",
                    value=f"${result.get('current_price', 0):.2f}" if result.get('current_price') else "N/A",
                    contribution=TrustContribution.NEUTRAL
                ),
            ]

            self.logger.info(
                f"UNSLUG computed for {latest.symbol}",
                trust=trust,
                band=band
            )

        except Exception as e:
            self.logger.error(f"UNSLUG computation failed: {e}")
            trust = 0.5
            signal = SignalType.NEUTRAL
            trust_factors = [
                ExplainEntry(
                    name="error",
                    value=str(e),
                    contribution=TrustContribution.DECREASES_TRUST
                )
            ]

        return OrganismOutput(
            organism=OrganismType.UNSLUG,
            symbol=latest.symbol,
            ts=datetime.utcnow(),
            signal=signal,
            trust=trust,
            explain=trust_factors
        )
    
    async def _compute_fear_index(self, series: List[InputSlice]) -> OrganismOutput:
        """
        FearIndex organism 계산 (P3: FearIndexTicker 통합)

        Logic:
        - FearIndexTicker로 Fear&Greed Score 계산 (0-100)
        - trust = fear_score / 100 (0-1 범위로 정규화)
        - signal은 PENDING_REVIEW (팀 승인 필요)
        """
        latest = series[-1]
        trust_factors = []

        try:
            # Fear Index 계산
            result = fear_index.calculate(series)

            # Score 추출
            fear_score = result.get('fear_score', 50.0)  # 0-100
            components = result.get('components', {})
            label = result.get('label', 'Neutral')

            # Trust = fear_score / 100 (0-1 범위)
            trust = float(np.clip(fear_score / 100.0, 0, 1))

            # Signal은 PENDING_REVIEW (팀이 승인할 때까지)
            signal = SignalType.NEUTRAL

            # Explain 구성 (상위 3개 컴포넌트)
            top_components = sorted(
                [(k, v) for k, v in components.items() if v is not None],
                key=lambda x: abs(50 - x[1]),
                reverse=True
            )[:3]

            trust_factors = [
                ExplainEntry(
                    name="fear_greed_score",
                    value=f"{fear_score:.1f}",
                    contribution=TrustContribution.NEUTRAL
                ),
                ExplainEntry(
                    name="label",
                    value=label,
                    contribution=TrustContribution.NEUTRAL
                ),
            ]

            # 상위 컴포넌트 추가
            for comp_name, comp_val in top_components:
                contrib = TrustContribution.INCREASES_TRUST if comp_val > 50 else TrustContribution.DECREASES_TRUST
                trust_factors.append(
                    ExplainEntry(
                        name=comp_name,
                        value=f"{comp_val:.1f}",
                        contribution=contrib
                    )
                )

            self.logger.info(
                f"FearIndex computed for {latest.symbol}",
                fear_score=fear_score,
                label=label
            )

        except Exception as e:
            self.logger.error(f"FearIndex computation failed: {e}")
            trust = 0.5
            signal = SignalType.NEUTRAL
            trust_factors = [
                ExplainEntry(
                    name="error",
                    value=str(e),
                    contribution=TrustContribution.DECREASES_TRUST
                )
            ]

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
