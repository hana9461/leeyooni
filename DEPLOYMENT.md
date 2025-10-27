# UNSLUG City 배포 가이드

## 배포 환경 구성

### 1. 백엔드 배포 (Railway)

#### 1.1 Railway 프로젝트 생성
1. [Railway](https://railway.app) 계정 생성 및 로그인
2. "New Project" → "Deploy from GitHub repo" 선택
3. GitHub 저장소 연결

#### 1.2 환경 변수 설정
Railway 대시보드에서 다음 환경 변수들을 설정:

```env
# Database
DATABASE_URL=postgresql://username:password@host:port/database
REDIS_URL=redis://username:password@host:port

# JWT
JWT_SECRET=your-super-secret-jwt-key-here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# AI Services
OPENAI_API_KEY=sk-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-api-key

# Payment Services
TOSS_SECRET_KEY=test_sk_your-toss-secret-key
STRIPE_SECRET_KEY=sk_test_your-stripe-secret-key
COINBASE_API_KEY=your-coinbase-api-key

# External APIs
ALPHA_VANTAGE_API_KEY=your-alpha-vantage-key
YAHOO_FINANCE_ENABLED=true

# App Settings
APP_NAME=UNSLUG City
APP_VERSION=1.5.0
DEBUG=false
ENVIRONMENT=production

# CORS
ALLOWED_ORIGINS=https://your-frontend-domain.vercel.app

# WebSocket
WEBSOCKET_CORS_ORIGINS=https://your-frontend-domain.vercel.app
```

#### 1.3 데이터베이스 설정
1. Railway에서 PostgreSQL 서비스 추가
2. Redis 서비스 추가 (선택사항)
3. 환경 변수에 연결 정보 설정

#### 1.4 배포
1. `backend` 폴더를 루트로 설정
2. 자동 배포 활성화
3. 도메인 확인

### 2. 프론트엔드 배포 (Vercel)

#### 2.1 Vercel 프로젝트 생성
1. [Vercel](https://vercel.com) 계정 생성 및 로그인
2. "New Project" → GitHub 저장소 import
3. `frontend` 폴더를 루트로 설정

#### 2.2 환경 변수 설정
Vercel 대시보드에서 다음 환경 변수들을 설정:

```env
NEXT_PUBLIC_API_URL=https://your-backend-domain.railway.app
NEXT_PUBLIC_WS_URL=https://your-backend-domain.railway.app
NEXT_PUBLIC_SPLINE_SCENE_URL=https://prod.spline.design/your-scene-id
NEXT_PUBLIC_TOSS_CLIENT_KEY=test_ck_your-toss-client-key
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-publishable-key
```

#### 2.3 배포 설정
1. Build Command: `npm run build`
2. Output Directory: `.next`
3. Install Command: `npm install`

### 3. 데이터베이스 마이그레이션

#### 3.1 백엔드 배포 후 마이그레이션 실행
```bash
# Railway CLI 사용
railway login
railway link your-project-id
railway run alembic upgrade head
```

또는 Railway 대시보드에서 Shell 접속 후:
```bash
cd backend
alembic upgrade head
```

### 4. 도메인 설정

#### 4.1 커스텀 도메인 (선택사항)
- Vercel: Settings → Domains에서 커스텀 도메인 추가
- Railway: Settings → Domains에서 커스텀 도메인 추가
- SSL 인증서 자동 발급

### 5. 모니터링 설정

#### 5.1 Sentry 설정
1. [Sentry](https://sentry.io) 계정 생성
2. 프로젝트 생성 후 DSN 복사
3. 백엔드 환경 변수에 `SENTRY_DSN` 추가

#### 5.2 로그 모니터링
- Railway: 자동 로그 수집 및 보관
- Vercel: Analytics 및 Functions 로그

### 6. CI/CD 설정

#### 6.1 GitHub Actions (선택사항)
`.github/workflows/deploy.yml`:
```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Railway
        uses: railway-app/railway-deploy@v1
        with:
          railway-token: ${{ secrets.RAILWAY_TOKEN }}
          
  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Vercel
        uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.ORG_ID }}
          vercel-project-id: ${{ secrets.PROJECT_ID }}
```

### 7. 보안 설정

#### 7.1 환경 변수 보안
- 모든 API 키는 환경 변수로 관리
- 프로덕션에서는 `DEBUG=false` 설정
- JWT 시크릿은 충분히 복잡하게 설정

#### 7.2 CORS 설정
- `ALLOWED_ORIGINS`에 허용된 도메인만 포함
- 개발 환경과 프로덕션 환경 분리

### 8. 성능 최적화

#### 8.1 백엔드 최적화
- Redis 캐싱 활용
- 데이터베이스 연결 풀링
- 비동기 처리 최적화

#### 8.2 프론트엔드 최적화
- 이미지 최적화 (Next.js 자동)
- 코드 스플리팅
- CDN 활용 (Vercel Edge Network)

### 9. 백업 및 복구

#### 9.1 데이터베이스 백업
- Railway PostgreSQL 자동 백업 활성화
- 정기적인 백업 다운로드

#### 9.2 코드 백업
- GitHub 저장소에 모든 코드 보관
- 태그를 통한 버전 관리

### 10. 트러블슈팅

#### 10.1 일반적인 문제
- 환경 변수 누락 확인
- CORS 설정 확인
- 데이터베이스 연결 상태 확인

#### 10.2 로그 확인
- Railway: 프로젝트 대시보드 → Deployments → Logs
- Vercel: 프로젝트 대시보드 → Functions → Logs

### 11. 업데이트 및 유지보수

#### 11.1 정기 업데이트
- 의존성 패키지 업데이트
- 보안 패치 적용
- 성능 모니터링

#### 11.2 스케일링
- Railway: 자동 스케일링
- Vercel: Edge Network 활용

---

## 배포 체크리스트

- [ ] 백엔드 Railway 배포 완료
- [ ] 프론트엔드 Vercel 배포 완료
- [ ] 환경 변수 설정 완료
- [ ] 데이터베이스 마이그레이션 완료
- [ ] 도메인 연결 완료
- [ ] SSL 인증서 발급 완료
- [ ] 모니터링 설정 완료
- [ ] 백업 설정 완료
- [ ] 성능 테스트 완료
- [ ] 보안 검토 완료
