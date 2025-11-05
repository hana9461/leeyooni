"""
Scheduler Service - Daily signal calculation + broadcast
P3.1 업데이트: cron (0 22 * * 1-5 UTC) + 5 symbols + DB + Logging
"""
import asyncio
from typing import List
import structlog
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import os
import json

from backend.src.core.organisms import organism_manager
from backend.src.websocket.socket_manager import socket_manager
from backend.src.adapters.data.yahoo import fetch_symbol_daily
from shared.schemas import OrganismType, SignalType

logger = structlog.get_logger(__name__)


class SchedulerService:
    """스케줄러 서비스 (P3.1: Daily Cron + DB + Logging)"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.logger = logger.bind(service="scheduler")
        self.is_running = False

        # P3.1 일일 워치리스트 (5개 심볼)
        self.daily_symbols = ["SPY", "QQQ", "AAPL", "TSLA", "NVDA"]
        self.daily_lookback = 30

        # 로그 디렉토리
        self.logs_dir = "/Users/lee/unslug-city/ops/logs"
        os.makedirs(self.logs_dir, exist_ok=True)

    async def start(self):
        """스케줄러 시작"""
        if self.is_running:
            return

        try:
            # ⭐ P3.1 Daily Cron: 0 22 * * 1-5 (UTC, 주중만)
            # 매일 22:00 UTC (미국 주식시장 종가 후 6시간)
            self.scheduler.add_job(
                self._daily_signal_batch,
                CronTrigger(hour=22, minute=0, day_of_week="0-4"),  # Mon-Fri
                id="daily_signal_batch",
                replace_existing=True
            )
            self.logger.info("Daily cron job registered: 0 22 * * 1-5 UTC")

            # 5분마다 신호 계산 (실시간 업데이트용)
            self.scheduler.add_job(
                self._calculate_and_broadcast_signals,
                CronTrigger(minute="*/5"),
                id="realtime_signal_calculation",
                replace_existing=True
            )

            # 1분마다 도시 상태 업데이트
            self.scheduler.add_job(
                self._update_city_state,
                CronTrigger(minute="*"),
                id="city_state_update",
                replace_existing=True
            )

            self.scheduler.start()
            self.is_running = True

            self.logger.info("Scheduler service started with P3.1 daily cron")

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

    async def _daily_signal_batch(self):
        """
        P3.1 Daily Batch: Calculate signals for 5 symbols
        Target: < 60s total execution time
        Log to: ops/logs/YYYYMMDD_daily_job.txt
        """
        start_time = time.time()
        log_filename = datetime.utcnow().strftime("%Y%m%d")
        log_filepath = os.path.join(self.logs_dir, f"{log_filename}_daily_job.txt")

        try:
            # Initialize log
            log_lines = [
                f"=== DAILY SIGNAL BATCH START ===",
                f"Timestamp: {datetime.utcnow().isoformat()}",
                f"Symbols: {', '.join(self.daily_symbols)}",
                f"Lookback: {self.daily_lookback} days",
                ""
            ]

            self.logger.info(
                "Daily batch started",
                symbols=self.daily_symbols,
                lookback=self.daily_lookback
            )

            signals_summary = []

            # Process each symbol
            for symbol in self.daily_symbols:
                try:
                    symbol_start = time.time()

                    # Fetch data
                    data = fetch_symbol_daily(symbol.upper(), lookback=self.daily_lookback)
                    if not data:
                        log_lines.append(f"⚠️  {symbol}: No data available")
                        self.logger.warning(f"No data for {symbol}")
                        continue

                    # Compute organisms (UNSLUG, Fear&Greed, MarketFlow)
                    organism_outputs = await organism_manager.compute_all_organisms(data)

                    # Extract key scores
                    unslug_output = organism_outputs.get(OrganismType.UNSLUG)
                    fear_output = organism_outputs.get(OrganismType.FEAR_INDEX)

                    unslug_score = unslug_output.trust if unslug_output else 0.5
                    fear_score = fear_output.trust if fear_output else 0.5

                    combined_trust = (unslug_score * fear_score) ** 0.5 if unslug_score > 0 and fear_score > 0 else 0.5

                    # Recommendation logic
                    if unslug_score >= 0.6 and fear_score >= 0.5:
                        recommended = "BUY"
                    elif unslug_score < 0.4 or fear_score < 0.3:
                        recommended = "RISK"
                    else:
                        recommended = "NEUTRAL"

                    # TODO: Save to DB
                    # signal = Signal(
                    #     organism=OrganismType.UNSLUG,
                    #     symbol=symbol,
                    #     ts=datetime.utcnow(),
                    #     unslug_score=unslug_score,
                    #     fear_score=fear_score,
                    #     combined_trust=combined_trust,
                    #     signal=SignalType.NEUTRAL,
                    #     trust=combined_trust,
                    #     status="PENDING_REVIEW",
                    #     recommendation={
                    #         "suggested": recommended,
                    #         "unslug": unslug_score,
                    #         "fear": fear_score
                    #     }
                    # )
                    # db.add(signal)
                    # db.commit()

                    symbol_elapsed = time.time() - symbol_start

                    # Broadcast to WebSocket
                    await socket_manager.broadcast_signal(
                        signal_data={
                            "symbol": symbol,
                            "unslug_score": round(unslug_score, 3),
                            "fear_score": round(fear_score, 3),
                            "combined_trust": round(combined_trust, 3),
                            "recommendation": recommended,
                            "status": "PENDING_REVIEW",
                            "ts": datetime.utcnow().isoformat()
                        },
                        symbol=symbol
                    )

                    log_lines.append(
                        f"✅ {symbol}: unslug={unslug_score:.3f}, fear={fear_score:.3f}, "
                        f"trust={combined_trust:.3f}, recommend={recommended} ({symbol_elapsed:.2f}s)"
                    )

                    signals_summary.append({
                        "symbol": symbol,
                        "unslug": round(unslug_score, 3),
                        "fear": round(fear_score, 3),
                        "trust": round(combined_trust, 3),
                        "recommendation": recommended,
                        "elapsed_s": round(symbol_elapsed, 2)
                    })

                    self.logger.info(
                        f"Signal calculated for {symbol}",
                        unslug_score=unslug_score,
                        fear_score=fear_score,
                        combined_trust=combined_trust,
                        recommendation=recommended,
                        elapsed_s=symbol_elapsed
                    )

                except Exception as e:
                    log_lines.append(f"❌ {symbol}: Failed - {str(e)}")
                    self.logger.error(f"Failed to process {symbol}: {e}")
                    continue

            # Summary
            total_elapsed = time.time() - start_time
            log_lines.extend([
                "",
                f"=== DAILY SIGNAL BATCH COMPLETE ===",
                f"Total Time: {total_elapsed:.2f}s",
                f"Target: <60s ✓" if total_elapsed < 60 else f"Target: <60s ✗",
                f"Signals Processed: {len(signals_summary)}/{len(self.daily_symbols)}",
                "",
                json.dumps(signals_summary, indent=2)
            ])

            # Write log file
            with open(log_filepath, "a") as f:
                f.write("\n".join(log_lines) + "\n")

            self.logger.info(
                "Daily batch completed",
                total_seconds=total_elapsed,
                signals_processed=len(signals_summary),
                log_file=log_filepath
            )

        except Exception as e:
            log_lines.append(f"❌ BATCH ERROR: {str(e)}")
            with open(log_filepath, "a") as f:
                f.write("\n".join(log_lines) + "\n")
            self.logger.error(f"Daily batch failed: {e}")

    async def _calculate_and_broadcast_signals(self):
        """신호 계산 및 브로드캐스트 (실시간 5분마다)"""
        try:
            self.logger.debug("Realtime signal calculation started")

            for symbol in self.daily_symbols[:1]:  # Just first symbol for realtime
                try:
                    data = fetch_symbol_daily(symbol.upper(), lookback=self.daily_lookback)
                    if not data:
                        continue

                    organism_outputs = await organism_manager.compute_all_organisms(data)

                    for organism_type, output in organism_outputs.items():
                        await socket_manager.broadcast_signal(
                            signal_data=output.dict(),
                            symbol=symbol
                        )

                except Exception as e:
                    self.logger.debug(f"Realtime signal update failed for {symbol}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Realtime signal calculation failed: {e}")

    async def _update_city_state(self):
        """도시 상태 업데이트"""
        try:
            symbol = "AAPL"
            data = fetch_symbol_daily(symbol, lookback=self.daily_lookback)
            if not data:
                return

            organism_outputs = await organism_manager.compute_all_organisms(data)

            unslug_trust = organism_outputs[OrganismType.UNSLUG].trust
            fear_trust = organism_outputs[OrganismType.FEAR_INDEX].trust
            flow_trust = organism_outputs[OrganismType.MARKET_FLOW].trust

            avg_trust = (unslug_trust + fear_trust + flow_trust) / 3

            if avg_trust >= 0.7:
                city_state = "thriving"
            elif avg_trust >= 0.4:
                city_state = "stable"
            else:
                city_state = "dim"

            city_visualization = {
                "city_state": city_state,
                "unslug_trust": round(unslug_trust, 3),
                "fear_trust": round(fear_trust, 3),
                "flow_trust": round(flow_trust, 3),
                "notes": f"Based on {symbol} analysis",
                "timestamp": datetime.utcnow().isoformat()
            }

            await socket_manager.broadcast_city_state(city_visualization)

            self.logger.debug("City state updated", city_state=city_state)

        except Exception as e:
            self.logger.debug(f"City state update failed: {e}")

    def get_daily_symbols(self) -> List[str]:
        """관심 종목 리스트 조회"""
        return self.daily_symbols.copy()

    def add_symbol(self, symbol: str):
        """관심 종목 추가"""
        if symbol.upper() not in self.daily_symbols:
            self.daily_symbols.append(symbol.upper())
            self.logger.info(f"Symbol added: {symbol.upper()}")

    def remove_symbol(self, symbol: str):
        """관심 종목 제거"""
        if symbol.upper() in self.daily_symbols:
            self.daily_symbols.remove(symbol.upper())
            self.logger.info(f"Symbol removed: {symbol.upper()}")


# 전역 스케줄러 서비스 인스턴스
scheduler_service = SchedulerService()
