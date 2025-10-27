"""
Admin 계정 생성 스크립트
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from src.db.database import AsyncSessionLocal
from src.db.models import User
from datetime import datetime

async def create_admin():
    """Admin 계정 생성"""
    async with AsyncSessionLocal() as db:
        try:
            # 이미 존재하는지 확인
            from sqlalchemy import select
            result = await db.execute(select(User).where(User.email == "admin@unslug.city"))
            existing = result.scalar_one_or_none()

            if existing:
                print("✅ Admin 계정이 이미 존재합니다!")
                print(f"   Email: admin@unslug.city")
                return

            # 간단한 해시 (bcrypt 대신 직접 처리)
            import hashlib
            password = "unslug2024"
            hashed = hashlib.sha256(password.encode()).hexdigest()

            # Admin 계정 생성
            admin = User(
                email="admin@unslug.city",
                name="Admin",
                hashed_password=hashed,  # 임시로 SHA256 사용
                is_active=True,
                is_verified=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            db.add(admin)
            await db.commit()
            await db.refresh(admin)

            print("✅ Admin 계정이 생성되었습니다!")
            print(f"   Email: admin@unslug.city")
            print(f"   Password: unslug2024")
            print(f"   User ID: {admin.id}")

        except Exception as e:
            print(f"❌ 에러: {e}")
            await db.rollback()

if __name__ == "__main__":
    asyncio.run(create_admin())
