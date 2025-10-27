"""
스케줄러 서비스 - 주기적 신호 계산 및 브로드캐스트
"""
import asyncio
from typing import List
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from src.core.organisms import organism_manager
from src.websocket.socket_manager import socket_manager
from shared.schemas import OrganismType, InputSlice

logger = structlog.get_logger(__name__)


class SchedulerService:
    """스케줄러 서비스"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.logger = logger.bind(service="scheduler")
        self.is_running = False
        
        # 모니터링할 종목 리스트 (실제로는 DB에서 가져와야 함)
        self.watchlist_symbols = ["AAPL", "TSLA", "MSFT", "GOOGL", "NVDA"]
    
    async def start(self):
        """스케줄러 시작"""
        if self.is_running:
            return
        
        try:
            # 5분마다 신호 계산 및 브로드캐스트
            self.scheduler.add_job(
                self._calculate_and_broadcast_signals,
                IntervalTrigger(minutes=5),
                id="signal_calculation",
                replace_existing=True
            )
            
            # 1분마다 도시 상태 업데이트
            self.scheduler.add_job(
                self._update_city_state,
                IntervalTrigger(minutes=1),
                id="city_state_update",
                replace_existing=True
            )
            
            # 30초마다 연결 상태 체크
            self.scheduler.add_job(
                self._check_connections,
                IntervalTrigger(seconds=30),
                id="connection_check",
                replace_existing=True
            )
            
            self.scheduler.start()
            self.is_running = True
            
            self.logger.info("Scheduler service started")
            
        except Exception as e:
            self.logger.error(f"Failed to start scheduler: {e}")
            raise
    
    async def stop(self):
        """스케줄러 중지"""
        if not self.is_running:
            return
        
        try:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            self.logger.info("Scheduler service stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop scheduler: {e}")
    
    async def _calculate_and_broadcast_signals(self):
        """신호 계산 및 브로드캐스트"""
        try:
            self.logger.info("Starting signal calculation", 
                           symbols_count=len(self.watchlist_symbols))
            
            for symbol in self.watchlist_symbols:
                try:
                    # 모의 데이터 생성 (실제로는 데이터 소스에서 가져와야 함)
                    mock_data = await self._get_mock_data(symbol)
                    
                    # 모든 organism에 대해 신호 계산
                    organism_outputs = await organism_manager.compute_all_organisms(mock_data)
                    
                    # 각 신호를 브로드캐스트
                    for organism_type, output in organism_outputs.items():
                        await socket_manager.broadcast_signal(
                            signal_data=output.dict(),
                            symbol=symbol
                        )
                        
                        self.logger.debug("Signal broadcasted", 
                                        organism=organism_type.value,
                                        symbol=symbol,
                                        signal=output.signal.value,
                                        trust=output.trust)
                
                except Exception as e:
                    self.logger.error(f"Failed to process symbol {symbol}: {e}")
                    continue
            
            self.logger.info("Signal calculation completed")
            
        except Exception as e:
            self.logger.error(f"Signal calculation failed: {e}")
    
    async def _update_city_state(self):
        """도시 상태 업데이트"""
        try:
            # 대표 종목 (AAPL)의 상태를 기반으로 도시 상태 계산
            symbol = "AAPL"
            mock_data = await self._get_mock_data(symbol)
            organism_outputs = await organism_manager.compute_all_organisms(mock_data)
            
            # Trust score 추출
            unslug_trust = organism_outputs[OrganismType.UNSLUG].trust
            fear_trust = organism_outputs[OrganismType.FEAR_INDEX].trust
            flow_trust = organism_outputs[OrganismType.MARKET_FLOW].trust
            
            # 도시 상태 결정
            avg_trust = (unslug_trust + fear_trust + flow_trust) / 3
            
            if avg_trust >= 0.7:
                city_state = "thriving"
            elif avg_trust >= 0.4:
                city_state = "stable"
            else:
                city_state = "dim"
            
            city_visualization = {
                "city_state": city_state,
                "unslug_trust": unslug_trust,
                "fear_trust": fear_trust,
                "flow_trust": flow_trust,
                "notes": f"Based on {symbol} analysis",
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # 도시 상태 브로드캐스트
            await socket_manager.broadcast_city_state(city_visualization)
            
            self.logger.debug("City state updated", 
                            city_state=city_state,
                            avg_trust=avg_trust)
            
        except Exception as e:
            self.logger.error(f"City state update failed: {e}")
    
    async def _check_connections(self):
        """연결 상태 체크"""
        try:
            stats = socket_manager.get_stats()
            
            if stats["total_connections"] > 0:
                self.logger.debug("Connection check", **stats)
            
        except Exception as e:
            self.logger.error(f"Connection check failed: {e}")
    
    async def _get_mock_data(self, symbol: str) -> List[InputSlice]:
        """모의 데이터 생성 (실제로는 데이터 소스에서 가져와야 함)"""
        import random
        from datetime import datetime, timedelta
        
        data = []
        base_price = 150.0 + random.uniform(-50, 50)  # 심볼별로 다른 기본 가격
        
        for i in range(30):
            date = datetime.utcnow() - timedelta(days=29-i)
            
            # 가격 변동 시뮬레이션
            change = random.uniform(-0.05, 0.05)
            base_price *= (1 + change)
            
            high = base_price * random.uniform(1.0, 1.03)
            low = base_price * random.uniform(0.97, 1.0)
            open_price = base_price * random.uniform(0.99, 1.01)
            close = base_price
            volume = random.randint(1000000, 10000000)
            
            data.append(InputSlice(
                symbol=symbol.upper(),
                interval="1d",
                ts=date.isoformat(),
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
    
    def add_symbol_to_watchlist(self, symbol: str):
        """관심 종목 추가"""
        if symbol.upper() not in self.watchlist_symbols:
            self.watchlist_symbols.append(symbol.upper())
            self.logger.info("Symbol added to watchlist", symbol=symbol.upper())
    
    def remove_symbol_from_watchlist(self, symbol: str):
        """관심 종목 제거"""
        if symbol.upper() in self.watchlist_symbols:
            self.watchlist_symbols.remove(symbol.upper())
            self.logger.info("Symbol removed from watchlist", symbol=symbol.upper())
    
    def get_watchlist(self) -> List[str]:
        """관심 종목 리스트 조회"""
        return self.watchlist_symbols.copy()


# 전역 스케줄러 서비스 인스턴스
scheduler_service = SchedulerService()
