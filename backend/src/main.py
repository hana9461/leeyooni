"""
UNSLUG City Backend - FastAPI Application
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from backend.src.api import auth, signals, subscription, payment, unslug, fear_index
from backend.src.db.database import init_db
from backend.src.websocket.socket_manager import SocketManager
from backend.src.services.scheduler import SchedulerService
from backend.src.config import settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Global socket manager
socket_manager = SocketManager()
scheduler_service = SchedulerService()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager"""
    logger.info("Starting UNSLUG City Backend")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Start scheduler service
    await scheduler_service.start()
    logger.info("Scheduler service started")
    
    yield
    
    # Cleanup
    await scheduler_service.stop()
    logger.info("Scheduler service stopped")
    logger.info("UNSLUG City Backend shutdown complete")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title="UNSLUG City API",
        description="금융 신호 분석 서비스 API",
        version="1.5.0",
        docs_url="/docs" if os.getenv("DEBUG", "false").lower() == "true" else None,
        redoc_url="/redoc" if os.getenv("DEBUG", "false").lower() == "true" else None,
        lifespan=lifespan
    )
    
    # CORS middleware - 모든 localhost 포트 허용
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001"
        ],
        allow_origin_regex=r"http://localhost:\d+",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"]
    )
    
    # Trusted host middleware
    if os.getenv("ENVIRONMENT") == "production":
        trusted_hosts = os.getenv("TRUSTED_HOSTS", "*.your-domain.com").split(",")
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
    
    # Include routers
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
    app.include_router(signals.router, prefix="/api/v1/signals", tags=["signals"])
    app.include_router(subscription.router, prefix="/api/v1/subscription", tags=["subscription"])
    app.include_router(payment.router, prefix="/api/v1/payment", tags=["payment"])
    app.include_router(unslug.router, prefix="/api/v1/unslug", tags=["unslug"])
    app.include_router(fear_index.router, prefix="/api/v1/fear-index", tags=["fear-index"])
    
    # WebSocket endpoint
    from backend.src.websocket.router import router as websocket_router
    app.include_router(websocket_router)
    
    @app.get("/")
    async def root():
        return {"message": "UNSLUG City API", "version": "1.5.0"}
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "unslug-city-api"}
    
    @app.get("/test/signals")
    async def test_signals():
        """Test signals endpoint - no auth required"""
        return {
            "city_state": "thriving",
            "signals": [
                {
                    "organism": "UNSLUG",
                    "symbol": "AAPL",
                    "signal": "BUY",
                    "trust": 0.87,
                    "explain": [
                        {"name": "RSI", "value": 28, "contribution": "increases_trust"},
                        {"name": "Volume Spike", "value": "180%", "contribution": "increases_trust"},
                        {"name": "Support Level", "value": "$150", "contribution": "increases_trust"}
                    ]
                },
                {
                    "organism": "FearIndex",
                    "symbol": "AAPL", 
                    "signal": "NEUTRAL",
                    "trust": 0.65,
                    "explain": [
                        {"name": "News Sentiment", "value": -0.2, "contribution": "decreases_trust"},
                        {"name": "VIX Level", "value": 18.5, "contribution": "neutral"}
                    ]
                },
                {
                    "organism": "MarketFlow",
                    "symbol": "AAPL",
                    "signal": "BUY", 
                    "trust": 0.92,
                    "explain": [
                        {"name": "Liquidity Ratio", "value": 2.3, "contribution": "increases_trust"},
                        {"name": "Flow Direction", "value": "Inflow", "contribution": "increases_trust"}
                    ]
                }
            ]
        }
    
    @app.get("/test/fear-index/{symbol}")
    async def test_fear_index(symbol: str):
        """Test Fear Index endpoint - no auth required"""
        from backend.src.core.fear_index import fear_calculator
        return fear_calculator.calculate_fear_index(symbol.upper())
    
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=os.getenv("DEBUG", "false").lower() == "true",
        log_level="info"
    )

    @app.get("/test/unslug/{symbol}")
    async def test_unslug(symbol: str):
        """Test UNSLUG endpoint - no auth required"""
        import yfinance as yf
        import pandas as pd
        from datetime import datetime
        
        try:
            df = yf.Ticker(symbol).history(period="max", interval="1d", auto_adjust=False)
            if df.empty:
                return {"error": f"No data available for {symbol}"}
            
            covid_period = df.loc["2020-03-01":"2020-03-31"]
            if covid_period.empty:
                covid_period = df.loc["2020-02-15":"2020-04-15"]
            
            if covid_period.empty:
                return {"error": f"No COVID low pattern found for {symbol}"}
            
            low_date = covid_period["Low"].idxmin()
            covid_low = float(covid_period.loc[low_date, "Low"])
            
            after_covid = df.loc[low_date:]
            high_date = after_covid["High"].idxmax()
            covid_high = float(after_covid.loc[high_date, "High"])
            
            fib_23_6 = covid_low + (covid_high - covid_low) * 0.236
            fib_38_2 = covid_low + (covid_high - covid_low) * 0.382
            current_price = float(df["Close"].iloc[-1])
            
            if current_price < covid_low:
                band = "Below 0%"
            elif current_price <= fib_23_6:
                band = "0–23.6%"
            elif current_price <= fib_38_2:
                band = "23.6–38.2%"
            else:
                band = "Above 38.2%"
            
            trust_score = 0.0
            trust_factors = []
            
            if band == "0–23.6%":
                trust_score += 0.4
                trust_factors.append({"factor": "Band Position", "value": "0-23.6%", "contribution": 0.4})
            elif band == "23.6–38.2%":
                trust_score += 0.2
                trust_factors.append({"factor": "Band Position", "value": "23.6-38.2%", "contribution": 0.2})
            
            signal = "BUY" if trust_score >= 0.6 else "NEUTRAL" if trust_score >= 0.3 else "HOLD"
            
            return {
                "symbol": symbol.upper(),
                "date": datetime.now().date(),
                "current_price": current_price,
                "band": band,
                "covid_low": covid_low,
                "covid_low_date": low_date.date().isoformat(),
                "post_covid_high": covid_high,
                "post_covid_high_date": high_date.date().isoformat(),
                "fib_23_6": fib_23_6,
                "fib_38_2": fib_38_2,
                "distance_from_low": (current_price - covid_low) / covid_low * 100,
                "distance_from_23_6": (current_price - fib_23_6) / fib_23_6 * 100,
                "trust_score": trust_score,
                "trust_factors": trust_factors,
                "signal": signal,
                "message": f"{symbol} is currently in {band} band with {trust_score:.2f} trust score"
            }
            
        except Exception as e:
            return {"error": f"Failed to analyze {symbol}: {str(e)}"}

