# UNSLUG City - 금융 신호 분석 서비스

UNSLUG City는 3개의 독립적인 Organism(UNSLUG, FearIndex, MarketFlow)을 통해 금융 신호를 분석하고 Trust Score를 제공하는 구독 기반 서비스입니다.

## 프로젝트 구조

```
unslug-city/
├── backend/              # Python FastAPI
│   ├── src/
│   │   ├── core/         # organism 로직 (기존 코드)
│   │   ├── api/          # REST API endpoints
│   │   ├── websocket/    # 실시간 알림
│   │   ├── services/     # AI, 결제 서비스
│   │   └── db/           # 데이터베이스 모델
│   ├── requirements.txt
│   └── .env.example
├── frontend/             # Next.js 14
│   ├── app/              # App Router
│   ├── components/       # React 컴포넌트
│   ├── lib/              # 유틸리티
│   └── public/
└── shared/               # 공통 타입/스키마
```

## 기술 스택

- **백엔드**: Python FastAPI, PostgreSQL, Redis, Socket.io
- **프론트엔드**: Next.js 14, TypeScript, Tailwind CSS, Spline 3D
- **AI**: OpenAI GPT-4, Anthropic Claude
- **결제**: 토스페이먼츠, Stripe, 암호화폐
- **배포**: Vercel (프론트), Railway (백엔드)

## 주요 기능

- 실시간 금융 신호 분석 (UNSLUG, FearIndex, MarketFlow)
- Trust Score 기반 신호 신뢰도 측정
- 구독 기반 서비스 (다중 결제 수단)
- 실시간 알림 (WebSocket)
- AI 챗봇 (GPT/Claude 통합)
- 3D City 시각화 (Spline)

## 개발 시작

### 백엔드
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 프론트엔드
```bash
cd frontend
npm install
npm run dev
```
