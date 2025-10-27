"""
설정 관리
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # App
    app_name: str = "UNSLUG City"
    app_version: str = "1.5.0"
    debug: bool = False
    environment: str = "development"
    
    # Database
    database_url: str
    redis_url: str
    
    # JWT
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    # AI Services
    openai_api_key: str
    anthropic_api_key: str
    
    # Payment Services
    toss_secret_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    coinbase_api_key: Optional[str] = None
    
    # External APIs
    alpha_vantage_api_key: Optional[str] = None
    yahoo_finance_enabled: bool = True
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:3001"

    # WebSocket
    websocket_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    
    # File Storage
    upload_dir: str = "uploads"
    max_file_size: int = 10485760  # 10MB
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60  # seconds
    
    # Monitoring
    sentry_dsn: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
