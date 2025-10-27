"""
Organism 로직 통합 - UNSLUG, FearIndex, MarketFlow
Factor 계산 및 Trust 점수 생성을 위한 통합 인터페이스
"""
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import structlog

from shared.schemas import (
    OrganismType, InputSlice, OrganismOutput,
    SignalType, ExplainEntry, TrustContribution
)
from src.core.factor_calculations import (
    vwap_zscore,
    realized_volatility_pct,
    volume_turnover_ratio,
    drawdown_intensity,
    liquidity_floor,
)
from src.core.trust_aggregation import (
    TrustScoreBuilder,
    geometric_mean,
)

logger = structlog.get_logger(__name__)


class BaseOrganism:
    """
    Organism 기본 클래스

    각 organism은 다양한 팩터를 계산하고 신뢰도(trust score)를 생성합니다.
    모든 팩터는 [0, 1]로 정규화되고, 단조 집계(monotone aggregation)를 사용합니다.
    """

    def __init__(self, organism_type: OrganismType):
        self.organism_type = organism_type
        self.logger = logger.bind(organism=organism_type.value)

    async def compute_trust(self, series: List[InputSlice]) -> OrganismOutput:
        """
        신호와 trust score를 계산하여 반환

        Args:
            series: InputSlice 객체의 시계열 리스트

        Returns:
            OrganismOutput: 신호, 신뢰도, 설명 인자 포함
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
        UNSLUG organism 계산 - 하락장 이후 반등 신호 감지

        UNSLUG는 저가대에서의 매수 신호를 감지합니다.
        팩터: VWAP 괴리도, 거래량 비율, 유동성 확인
        """
        latest = series[-1]

        if len(series) < 20:
            # 데이터 부족
            return OrganismOutput(
                organism=OrganismType.UNSLUG,
                symbol=latest.symbol,
                ts=datetime.utcnow(),
                signal=SignalType.NEUTRAL,
                trust=0.0,
                explain=[
                    ExplainEntry(
                        name="insufficient_data",
                        value=f"{len(series)} periods (need ≥20)",
                        contribution=TrustContribution.DECREASES_TRUST
                    )
                ]
            )

        try:
            # 데이터 추출
            highs = [s.high for s in series]
            lows = [s.low for s in series]
            closes = [s.close for s in series]
            volumes = [s.volume for s in series]

            # Factor 계산
            vwap_z = vwap_zscore(highs, lows, closes, volumes, lookback=20)
            vol_ratio = volume_turnover_ratio(volumes, lookback=10)
            liq_check = liquidity_floor(volumes, min_volume_threshold=1e6)

            # Trust 계산 (geometric mean)
            builder = TrustScoreBuilder()
            builder.add_factors(
                vwap_z=vwap_z,
                volume_ratio=vol_ratio,
                liquidity=liq_check
            )
            trust = builder.compute(method="geometric_mean")

            # Signal 결정 (trust 기반)
            if trust >= 0.7:
                signal = SignalType.BUY
            elif trust >= 0.4:
                signal = SignalType.NEUTRAL
            else:
                signal = SignalType.RISK

            # Explanation
            explain = [
                ExplainEntry(
                    name="vwap_z_score",
                    value=f"{vwap_z:.3f}",
                    contribution=TrustContribution.INCREASES_TRUST if vwap_z < 0.5 else TrustContribution.DECREASES_TRUST
                ),
                ExplainEntry(
                    name="volume_ratio",
                    value=f"{vol_ratio:.3f}",
                    contribution=TrustContribution.INCREASES_TRUST if vol_ratio > 0.5 else TrustContribution.NEUTRAL
                ),
                ExplainEntry(
                    name="liquidity_floor",
                    value="pass" if liq_check == 1.0 else "fail",
                    contribution=TrustContribution.INCREASES_TRUST if liq_check == 1.0 else TrustContribution.DECREASES_TRUST
                ),
            ]

            self.logger.info(
                f"UNSLUG computed for {latest.symbol}",
                trust=trust,
                signal=signal.value
            )

            return OrganismOutput(
                organism=OrganismType.UNSLUG,
                symbol=latest.symbol,
                ts=datetime.utcnow(),
                signal=signal,
                trust=trust,
                explain=explain
            )

        except Exception as e:
            self.logger.error(f"UNSLUG computation failed: {e}")
            return OrganismOutput(
                organism=OrganismType.UNSLUG,
                symbol=latest.symbol,
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
    
    async def _compute_fear_index(self, series: List[InputSlice]) -> OrganismOutput:
        """
        Fear Index organism 계산 - 시장 공포/스트레스 지표

        Fear Index는 변동성, 손실 강도, 갭 위험을 측정합니다.
        팩터: 실현 변동성, 낙폭강도
        """
        latest = series[-1]

        if len(series) < 20:
            return OrganismOutput(
                organism=OrganismType.FEAR_INDEX,
                symbol=latest.symbol,
                ts=datetime.utcnow(),
                signal=SignalType.NEUTRAL,
                trust=0.0,
                explain=[
                    ExplainEntry(
                        name="insufficient_data",
                        value=f"{len(series)} periods (need ≥20)",
                        contribution=TrustContribution.DECREASES_TRUST
                    )
                ]
            )

        try:
            # 데이터 추출
            prices = [s.close for s in series]
            returns = [(prices[i] - prices[i-1]) / prices[i-1] if prices[i-1] != 0 else 0
                       for i in range(1, len(prices))]

            # Factor 계산
            vol_pct = realized_volatility_pct(returns, window=20)
            drawdown_int = drawdown_intensity(prices, window=20)

            # Trust 계산 (geometric mean)
            builder = TrustScoreBuilder()
            builder.add_factors(
                volatility=vol_pct,
                drawdown=drawdown_int
            )
            trust = builder.compute(method="geometric_mean")

            # Signal 결정 (fear level에 따라)
            if trust >= 0.7:
                signal = SignalType.RISK  # 높은 두려움 = RISK
            elif trust >= 0.4:
                signal = SignalType.NEUTRAL
            else:
                signal = SignalType.BUY  # 낮은 두려움 = 기회

            # Explanation
            explain = [
                ExplainEntry(
                    name="realized_volatility",
                    value=f"{vol_pct:.3f}",
                    contribution=TrustContribution.INCREASES_TRUST if vol_pct > 0.5 else TrustContribution.NEUTRAL
                ),
                ExplainEntry(
                    name="drawdown_intensity",
                    value=f"{drawdown_int:.3f}",
                    contribution=TrustContribution.INCREASES_TRUST if drawdown_int > 0.5 else TrustContribution.NEUTRAL
                ),
            ]

            self.logger.info(
                f"FearIndex computed for {latest.symbol}",
                trust=trust,
                signal=signal.value
            )

            return OrganismOutput(
                organism=OrganismType.FEAR_INDEX,
                symbol=latest.symbol,
                ts=datetime.utcnow(),
                signal=signal,
                trust=trust,
                explain=explain
            )

        except Exception as e:
            self.logger.error(f"FearIndex computation failed: {e}")
            return OrganismOutput(
                organism=OrganismType.FEAR_INDEX,
                symbol=latest.symbol,
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
    
    async def _compute_market_flow(self, series: List[InputSlice]) -> OrganismOutput:
        """
        Market Flow organism 계산 - 유동성/참여도 흐름 분석

        Market Flow는 거래량, 변동성, 가격 방향을 종합합니다.
        팩터: 거래량 비율, 유동성 확인
        """
        latest = series[-1]

        if len(series) < 10:
            return OrganismOutput(
                organism=OrganismType.MARKET_FLOW,
                symbol=latest.symbol,
                ts=datetime.utcnow(),
                signal=SignalType.NEUTRAL,
                trust=0.0,
                explain=[
                    ExplainEntry(
                        name="insufficient_data",
                        value=f"{len(series)} periods (need ≥10)",
                        contribution=TrustContribution.DECREASES_TRUST
                    )
                ]
            )

        try:
            # 데이터 추출
            volumes = [s.volume for s in series]
            closes = [s.close for s in series]

            # Factor 계산
            vol_ratio = volume_turnover_ratio(volumes, lookback=10)
            liq_check = liquidity_floor(volumes, min_volume_threshold=5e5)  # Lower threshold for flow

            # 가격 방향 (단순: 최근 3일 추세)
            recent_closes = closes[-3:] if len(closes) >= 3 else closes
            price_trend = 1.0 if recent_closes[-1] > recent_closes[0] else 0.0

            # Trust 계산 (volume + liquidity + trend 가중치)
            builder = TrustScoreBuilder()
            builder.add_factors(
                volume_turnover=vol_ratio,
                liquidity=liq_check,
                price_trend=price_trend
            )
            trust = builder.compute(method="geometric_mean")

            # Signal 결정
            if trust >= 0.7:
                signal = SignalType.BUY  # 강한 유동성 흐름
            elif trust >= 0.4:
                signal = SignalType.NEUTRAL
            else:
                signal = SignalType.RISK  # 약한 유동성

            # Explanation
            explain = [
                ExplainEntry(
                    name="volume_turnover",
                    value=f"{vol_ratio:.3f}",
                    contribution=TrustContribution.INCREASES_TRUST if vol_ratio > 0.5 else TrustContribution.NEUTRAL
                ),
                ExplainEntry(
                    name="liquidity_check",
                    value="pass" if liq_check == 1.0 else "fail",
                    contribution=TrustContribution.INCREASES_TRUST if liq_check == 1.0 else TrustContribution.DECREASES_TRUST
                ),
                ExplainEntry(
                    name="price_trend",
                    value="uptrend" if price_trend == 1.0 else "downtrend",
                    contribution=TrustContribution.INCREASES_TRUST if price_trend == 1.0 else TrustContribution.NEUTRAL
                ),
            ]

            self.logger.info(
                f"MarketFlow computed for {latest.symbol}",
                trust=trust,
                signal=signal.value
            )

            return OrganismOutput(
                organism=OrganismType.MARKET_FLOW,
                symbol=latest.symbol,
                ts=datetime.utcnow(),
                signal=signal,
                trust=trust,
                explain=explain
            )

        except Exception as e:
            self.logger.error(f"MarketFlow computation failed: {e}")
            return OrganismOutput(
                organism=OrganismType.MARKET_FLOW,
                symbol=latest.symbol,
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
