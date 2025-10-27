"""
Backtest Light - Hit-rate 계산 및 성과 분석
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
import structlog

from shared.schemas import InputSlice

logger = structlog.get_logger(__name__)


def calculate_hitrate(
    symbol: str,
    signals: List[Dict],
    lookback_days: int = 60
) -> Dict:
    """
    신호별 hit-rate 계산 (다음날 수익률 방향 확인)

    Args:
        symbol: 종목 코드
        signals: [{"date": ..., "signal": "BUY"|"NEUTRAL"|"RISK", "price": ...}, ...]
        lookback_days: 백테스트 기간

    Returns:
        {
            "symbol": str,
            "hit_rate": float (0-1),
            "n_signals": int,
            "n_correct": int,
            "avg_return": float,
            "winning_signals": int,
            "losing_signals": int
        }
    """
    if not signals or len(signals) < 2:
        return {
            "symbol": symbol,
            "hit_rate": 0.5,
            "n_signals": 0,
            "n_correct": 0,
            "avg_return": 0.0,
            "winning_signals": 0,
            "losing_signals": 0
        }

    # 신호별 다음날 수익률 계산
    correct = 0
    winning = 0
    losing = 0

    for i in range(len(signals) - 1):
        current = signals[i]
        next_signal = signals[i + 1]

        current_price = current.get("price", 0)
        next_price = next_signal.get("price", 0)

        if current_price == 0 or next_price == 0:
            continue

        # 수익률
        ret = (next_price - current_price) / current_price

        # 신호별 판단
        signal = current.get("signal", "NEUTRAL")

        # Hit 판정
        if signal == "BUY" and ret > 0:
            correct += 1
            winning += 1
        elif signal == "RISK" and ret < 0:
            correct += 1
            losing += 1
        elif signal == "NEUTRAL" and abs(ret) <= 0.01:  # ±1% 이내
            correct += 1

    n_signals = len(signals) - 1
    hit_rate = correct / n_signals if n_signals > 0 else 0.5

    return {
        "symbol": symbol,
        "hit_rate": round(hit_rate, 3),
        "n_signals": n_signals,
        "n_correct": correct,
        "avg_return": 0.0,  # TODO: 실제 계산
        "winning_signals": winning,
        "losing_signals": losing
    }


def save_backtest_report(
    symbol: str,
    hitrate_data: Dict,
    output_dir: str = "/Users/lee/unslug-city/reports"
) -> str:
    """
    백테스트 리포트 CSV 저장

    Returns:
        파일 경로
    """
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(
        output_dir,
        f"backtest_{symbol}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    )

    # CSV 형식으로 저장
    data_str = "symbol,hit_rate,n_signals,n_correct,winning,losing\n"
    data_str += f"{hitrate_data['symbol']},{hitrate_data['hit_rate']},{hitrate_data['n_signals']},{hitrate_data['n_correct']},{hitrate_data['winning_signals']},{hitrate_data['losing_signals']}\n"

    with open(filename, 'w') as f:
        f.write(data_str)

    logger.info(f"Backtest report saved: {filename}")
    return filename
