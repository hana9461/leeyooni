# UNSLUG City 시작 가이드

## 🚀 프로젝트 개요

UNSLUG City는 3개의 독립적인 AI organism(UNSLUG, FearIndex, MarketFlow)을 통해 금융 신호를 분석하고 Trust Score를 제공하는 구독 기반 서비스입니다.

## 📋 구현된 기능

### ✅ 완료된 기능들

1. **프로젝트 구조**
   - 모노레포 구조 (backend/frontend/shared)
   - Next.js 14 + TypeScript + Tailwind CSS
   - Python FastAPI + PostgreSQL + Redis

2. **백엔드 시스템**
   - JWT 기반 인증 (회원가입/로그인)
   - Organism 로직 통합 (UNSLUG, FearIndex, MarketFlow)
   - REST API 엔드포인트
   - WebSocket 실시간 통신
   - AI 서비스 통합 (GPT-4, Claude-3)
   - 다중 결제 시스템 (토스, Stripe, 암호화폐)
   - 스케줄러 서비스 (주기적 신호 계산)

3. **프론트엔드 시스템**
   - 반응형 웹 대시보드
   - Spline 3D 도시 시각화
   - 실시간 신호 알림
   - AI 챗봇 인터페이스
   - 인증 시스템 (로그인/회원가입)

4. **배포 환경**
   - Vercel (프론트엔드)
   - Railway (백엔드)
   - 환경 변수 설정
   - CI/CD 설정

## 🛠️ 개발 환경 설정

### 1. 저장소 클론
```bash
git clone <repository-url>
cd unslug-city
```

### 2. 백엔드 설정
```bash
cd backend

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일을 편집하여 실제 값 입력

# 데이터베이스 마이그레이션
alembic upgrade head

# 서버 실행
uvicorn src.main:app --reload
```

### 3. 프론트엔드 설정
```bash
cd frontend

# 의존성 설치
npm install

# 환경 변수 설정
cp .env.example .env.local
# .env.local 파일을 편집하여 실제 값 입력

# 개발 서버 실행
npm run dev
```

## 🔑 필요한 API 키

### 필수 API 키들
1. **OpenAI API Key** - GPT-4 사용
2. **Anthropic API Key** - Claude-3 사용
3. **토스페이먼츠 키** - 한국 결제
4. **Stripe 키** - 해외 결제
5. **Coinbase API Key** - 암호화폐 결제

### 선택적 API 키들
1. **Alpha Vantage API Key** - 주식 데이터
2. **Spline Scene URL** - 3D 시각화
3. **Sentry DSN** - 에러 모니터링

## 📁 프로젝트 구조

```
unslug-city/
├── backend/                 # Python FastAPI 백엔드
│   ├── src/
│   │   ├── core/           # Organism 로직
│   │   ├── api/            # REST API 엔드포인트
│   │   ├── websocket/      # WebSocket 서버
│   │   ├── services/       # AI, 결제 서비스
│   │   └── db/             # 데이터베이스 모델
│   ├── alembic/            # DB 마이그레이션
│   ├── requirements.txt    # Python 의존성
│   └── .env.example        # 환경 변수 예시
├── frontend/               # Next.js 프론트엔드
│   ├── src/
│   │   ├── app/            # App Router 페이지
│   │   ├── components/     # React 컴포넌트
│   │   ├── lib/            # 유틸리티
│   │   └── types/          # TypeScript 타입
│   ├── package.json        # Node.js 의존성
│   └── .env.example        # 환경 변수 예시
├── shared/                 # 공통 스키마
└── DEPLOYMENT.md           # 배포 가이드
```

## 🚀 실행 방법

### 로컬 개발 환경
1. **백엔드 실행**
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn src.main:app --reload
   ```
   - API: http://localhost:8000
   - 문서: http://localhost:8000/docs

2. **프론트엔드 실행**
   ```bash
   cd frontend
   npm run dev
   ```
   - 웹사이트: http://localhost:3000

### 프로덕션 배포
1. **Railway (백엔드)**
   - GitHub 저장소 연결
   - 환경 변수 설정
   - 자동 배포

2. **Vercel (프론트엔드)**
   - GitHub 저장소 연결
   - 환경 변수 설정
   - 자동 배포

## 🔧 주요 기능 사용법

### 1. 회원가입/로그인
- `/auth/register` - 회원가입
- `/auth/login` - 로그인
- 데모 계정: `demo@unslug.city` / `demo123!`

### 2. 대시보드
- `/dashboard` - 메인 대시보드
- 실시간 신호 확인
- 3D 도시 시각화
- 종목별 신호 분석

### 3. AI 챗봇
- `/chat` - AI 어시스턴트
- GPT-4 또는 Claude-3 선택
- 시장 분석 및 투자 조언

### 4. API 사용
- 인증: JWT 토큰 기반
- WebSocket: 실시간 신호 수신
- REST API: 신호 조회, 결제 처리

## 🐛 문제 해결

### 일반적인 문제들

1. **백엔드 실행 오류**
   - Python 버전 확인 (3.11+)
   - 가상환경 활성화 확인
   - 의존성 설치 확인

2. **프론트엔드 실행 오류**
   - Node.js 버전 확인 (18+)
   - npm install 재실행
   - 환경 변수 설정 확인

3. **데이터베이스 연결 오류**
   - DATABASE_URL 확인
   - PostgreSQL 서버 실행 확인
   - 마이그레이션 실행

4. **API 키 오류**
   - 환경 변수 파일 확인
   - API 키 유효성 확인
   - 권한 설정 확인

### 로그 확인
- 백엔드: 터미널 출력 또는 Railway 로그
- 프론트엔드: 브라우저 개발자 도구
- 데이터베이스: PostgreSQL 로그

## 📚 추가 자료

- [배포 가이드](./DEPLOYMENT.md)
- [API 문서](http://localhost:8000/docs) (로컬 실행 시)
- [UNSLUG City 가이드](./backend/src/core/UNSLUG_City_v1_5_Claude_Guide.md)

## 🤝 기여하기

1. Fork 저장소
2. Feature 브랜치 생성
3. 변경사항 커밋
4. Pull Request 생성

## 📞 지원

문제가 발생하거나 질문이 있으시면:
- GitHub Issues 생성
- 개발팀에 문의

---

**UNSLUG City** - 금융 시장의 신호를 읽어내는 도시 🏙️
