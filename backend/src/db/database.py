"""
데이터베이스 연결 및 초기화
"""
import structlog
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.config import settings

logger = structlog.get_logger(__name__)

# Async engine for SQLite
engine = create_async_engine(
    settings.database_url.replace("sqlite://", "sqlite+aiosqlite://"),
    echo=settings.debug,
    future=True
)

# Sync engine for Alembic migrations
sync_engine = create_engine(
    settings.database_url,
    echo=settings.debug
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Sync session factory for migrations
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=sync_engine
)

# Base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they are registered
            from src.db import models
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
