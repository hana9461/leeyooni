# P3.1 Setup Guide

## 개요

P3.1에서 추가되는 기능:
- 🔧 **Daily Cron Scheduler**: `0 22 * * 1-5` (UTC) - 5개 심볼 (SPY, QQQ, AAPL, TSLA, NVDA)
- 🗄️ **Database Persistence**: PostgreSQL `signals` + `signal_approvals` 테이블
- ✋ **Team Approval Workflow**: `POST /api/v1/signals/{symbol}/approve`
- 📊 **Daily Logging**: `ops/logs/YYYYMMDD_daily_job.txt`

---

## 1. 데이터베이스 설정

### 1.1 PostgreSQL 설치 (MacOS/Homebrew)

```bash
brew install postgresql@16
brew services start postgresql@16
```

### 1.2 데이터베이스 & 사용자 생성

```bash
createdb unslug_city
psql -d unslug_city
```

```sql
CREATE USER unslug_app WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE unslug_city TO unslug_app;
```

### 1.3 .env 파일 업데이트

```bash
# backend/.env (또는 환경변수 설정)
DATABASE_URL=postgresql://unslug_app:your_secure_password@localhost:5432/unslug_city
ENVIRONMENT=development
```

---

## 2. 마이그레이션 실행

### 2.1 Alembic 초기화 (이미 완료됨)

```bash
cd backend
alembic init alembic
```

### 2.2 P3.1 마이그레이션 생성

```bash
# 자동 마이그레이션 생성 (모델 변경 감지)
alembic revision --autogenerate -m "P3.1: Add Signal scores + approvals"
```

생성된 마이그레이션 파일: `backend/alembic/versions/XXX_p3_1_add_signal_scores_approvals.py`

### 2.3 마이그레이션 적용

```bash
alembic upgrade head
```

검증:

```bash
psql -d unslug_city -c "\d signals"
psql -d unslug_city -c "\d signal_approvals"
```

---

## 3. 마이그레이션 스크립트 (SQL)

만약 Alembic을 직접 사용하고 싶으면, 다음 SQL을 실행하세요:

```sql
-- ALTER signals table (P3.1)
ALTER TABLE signals ADD COLUMN ts TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW();
ALTER TABLE signals ADD COLUMN unslug_score FLOAT;
ALTER TABLE signals ADD COLUMN fear_score FLOAT;
ALTER TABLE signals ADD COLUMN combined_trust FLOAT;
ALTER TABLE signals ADD COLUMN status VARCHAR(50) DEFAULT 'PENDING_REVIEW';
ALTER TABLE signals ADD COLUMN recommendation JSONB;
ALTER TABLE signals ADD COLUMN meta JSONB;
ALTER TABLE signals ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
CREATE INDEX idx_signals_symbol_ts ON signals(symbol, ts DESC);

-- CREATE signal_approvals table
CREATE TABLE signal_approvals (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    approved_status VARCHAR(50) NOT NULL,
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_user FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_signal_approvals_signal_id ON signal_approvals(signal_id);
CREATE INDEX idx_signal_approvals_symbol ON signal_approvals(symbol);
```

---

## 4. 애플리케이션 실행

### 4.1 백엔드 시작

```bash
cd backend
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

### 4.2 Daily Scheduler 확인

매일 22:00 UTC (월-금)에 자동으로 실행됩니다.

수동으로 테스트하려면:

```bash
python3 << 'EOF'
import asyncio
from backend.src.services.scheduler import scheduler_service

async def test():
    await scheduler_service._daily_signal_batch()

asyncio.run(test())
EOF
```

로그 확인:

```bash
cat ops/logs/$(date +%Y%m%d)_daily_job.txt
```

---

## 5. API 엔드포인트

### 5.1 단건 신호 조회

```bash
curl http://localhost:8000/api/v1/signals/AAPL
```

응답:

```json
{
  "symbol": "AAPL",
  "ts": "2025-10-28T22:00:00Z",
  "unslug_score": 0.75,
  "fear_score": 0.65,
  "combined_trust": 0.70,
  "status": "PENDING_REVIEW",
  "recommendation": {
    "suggested": "BUY",
    "unslug": 0.75,
    "fear": 0.65
  },
  "awaiting_approval": true
}
```

### 5.2 신호 승인 (팀)

```bash
curl -X POST http://localhost:8000/api/v1/signals/AAPL/approve \
  -H "Content-Type: application/json" \
  -d '{
    "status": "BUY",
    "user_id": "team-member-001",
    "note": "분석 검토 완료. 매수 추천"
  }'
```

응답:

```json
{
  "symbol": "AAPL",
  "approved_status": "BUY",
  "approved_by": "team-member-001",
  "approved_at": "2025-10-28T22:15:00Z",
  "note": "분석 검토 완료. 매수 추천"
}
```

### 5.3 승인 이력 조회

```bash
curl http://localhost:8000/api/v1/signals/AAPL/approvals
```

---

## 6. 성능 목표 (Kill Gate)

| 항목 | 목표 | 상태 |
|------|------|------|
| Daily batch (5 tickers) | < 60s | ✅ |
| API response P99 | < 200ms | ✅ (DB index) |
| Signal score range | [0,1] | ✅ |
| Status values | PENDING_REVIEW, APPROVED_* | ✅ |
| Approval latency | < 100ms | ✅ (direct update) |

---

## 7. 트러블슈팅

### PostgreSQL 연결 오류

```bash
# 연결 테스트
psql -d unslug_city -c "SELECT NOW();"

# 없으면 설정 확인
env | grep DATABASE_URL
```

### 마이그레이션 실패

```bash
# 현재 상태 확인
alembic current

# 이전 버전으로 롤백
alembic downgrade -1

# 다시 시도
alembic upgrade head
```

### 스케줄러 미작동

```bash
# 로그 확인
tail -f ops/logs/$(date +%Y%m%d)_daily_job.txt

# 수동 실행 (디버그)
python3 -c "from backend.src.services.scheduler import scheduler_service; import asyncio; asyncio.run(scheduler_service._daily_signal_batch())"
```

---

## 다음 단계 (P3.2+)

- [ ] 실시간 신호 계산 (WebSocket broadcast)
- [ ] 프론트엔드 승인 UI (React 컴포넌트)
- [ ] 더 많은 데이터 소스 (FRED, Cboe, FINRA)
- [ ] 신호 히스토리 & 성과 분석
- [ ] 자동 포지션 관리 (실제 거래 연동)

---

**최종 확인**:

```bash
# 1. 데이터베이스 상태
psql -d unslug_city -c "SELECT COUNT(*) FROM signals;"

# 2. 스케줄러 실행 로그
ls -la ops/logs/ | head -5

# 3. API 응답
curl http://localhost:8000/api/v1/signals/AAPL | jq '.status'
```

모두 OK면 P3.1 완료! 🎉
