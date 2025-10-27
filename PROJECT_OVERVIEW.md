# UNSLUG City — Project Overview & Strategic Brief

**Version:** 1.5.0
**Last Updated:** 2025-10-27
**Owner:** 이윤구
**Status:** Active Development (Core Infrastructure ✅ | Organism Logic ⚠️ | Integration 🔄)

---

## 1. Project Purpose & Vision

### Core Idea
**UNSLUG City** is a **subscription-based financial signal analysis service** that synthesizes multiple independent AI organisms (analytical engines) to provide Trust-calibrated market insights. It targets retail and semi-pro traders who need actionable, explainable signals rather than black-box predictions.

### User Problem
- **Fragmentation:** Traders juggle multiple signal sources without knowing which to trust.
- **Opacity:** Most trading signals lack explainability—no insight into *why* a signal fired.
- **Noise:** Too many false positives from uncalibrated indicators.

### Intended Value Proposition
1. **Three Equal-Tier Organisms** producing independent signals:
   - **UNSLUG:** Bottom-dip detection & mean-reversion buy signals
   - **FearIndex:** Volatility/drawdown intensity & psychological extremes
   - **MarketFlow:** Liquidity, participation, and directional bias
2. **Trust Score** ∈ [0,1]: Calibrated confidence in each signal (not prediction accuracy, but signal reliability).
3. **Explainability:** Every signal includes factor breakdown showing what drove the Trust score.
4. **Subscription Tiers:** Basic → Premium → Enterprise, with future dynamic pricing based on Trust.
5. **Real-time Delivery:** WebSocket alerts, AI chatbot assistance (GPT-4 / Claude-3), 3D city visualization.

---

## 2. System Overview

### Architecture: Monorepo Structure
```
unslug-city/
├── backend/              (Python FastAPI)
│   ├── src/
│   │   ├── core/        # Organism logic (UNSLUG, FearIndex, MarketFlow)
│   │   ├── api/         # REST endpoints (auth, signals, subscriptions, payments, organisms)
│   │   ├── websocket/   # Real-time notifications & updates
│   │   ├── services/    # AI (OpenAI/Claude), Payments (Toss/Stripe/Crypto), Scheduler
│   │   ├── db/          # SQLAlchemy models + async database connection
│   │   └── config.py    # Settings management (Pydantic)
│   ├── alembic/         # DB migrations (SQLAlchemy)
│   ├── requirements.txt  # Python dependencies
│   └── .env.example     # Environment variable template
├── frontend/             (Next.js 14 + React 19)
│   ├── src/app/         # App Router pages (dashboard, auth, signals, pricing)
│   ├── src/components/  # Reusable React components (Spline, charts, cards)
│   ├── src/lib/         # Utilities (API client, hooks, stock utilities)
│   ├── src/types/       # TypeScript schemas (matching backend)
│   └── public/          # Static assets
├── shared/
│   └── schemas.py       # Pydantic schemas shared between backend & frontend
│                        # (OrganismOutput, InputSlice, CityState, etc.)
└── [README.md, GETTING_STARTED.md, DEPLOYMENT.md]
```

### Data Flow
```
Data Sources (Yahoo Finance / Alpha Vantage)
    ↓
Scheduler Service (APScheduler) [backend]
    ↓
Organism Manager (BaseOrganism + OrganismManager) [backend/core]
    ↓
REST API + WebSocket [backend/api, /websocket]
    ↓
Frontend Dashboard + Real-time Updates [frontend/src/app]
    ↓
Visualization (3D City, Charts, Signal Cards) [frontend/components]
```

### Key Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend Runtime** | Python 3.11+ | Primary language |
| **Web Framework** | FastAPI 0.104 | Async REST API & WebSocket |
| **Database** | PostgreSQL + SQLAlchemy 2.0 | Persistent storage (users, subscriptions, signals) |
| **Cache/Queue** | Redis 5.0 | Session management, job queue (optional) |
| **Real-time** | Socket.io 5.10 | WebSocket for alerts & live updates |
| **AI Integration** | OpenAI (GPT-4), Anthropic (Claude-3) | Chat assistance & analysis |
| **Auth** | JWT (python-jose) + bcrypt | Stateless token-based security |
| **Payments** | Toss, Stripe, Coinbase API | Multi-currency subscriptions |
| **Frontend Framework** | Next.js 15 (App Router) | Server/client rendering, routing |
| **UI Library** | React 19 + Tailwind CSS 4 | Component development |
| **3D Graphics** | Spline + Three.js | City visualization |
| **Data Viz** | Chart.js, ECharts | Signal & market charts |
| **Deployment** | Railway (backend), Vercel (frontend) | Managed hosting + CI/CD |

---

## 3. Core Features Implemented So Far

### ✅ Completed

#### Backend Infrastructure
- **Project Structure & Boilerplate**
  - FastAPI app with CORS, TrustedHost, logging (structlog)
  - Async database connection (SQLAlchemy 2.0, Alembic migrations)
  - Configuration management (Pydantic Settings)
  - Lifespan context manager (startup/shutdown hooks)

- **Authentication System**
  - User signup & login (`POST /api/v1/auth/register`, `/api/v1/auth/login`)
  - JWT token generation & refresh
  - Password hashing (SHA256 + bcrypt fallback)
  - HTTPBearer security scheme

- **Database Models** (Fully defined, not all endpoints wired yet)
  - `User`: email, name, password, verification status
  - `Subscription`: plan (basic/premium/enterprise), status, expiration
  - `Payment`: method (toss/stripe/crypto), amount, status, external ID
  - `Signal`: organism, symbol, signal type, trust score, explain JSON
  - `Watchlist`: user's tracked symbols
  - `Notification`: alerts & system messages
  - `ChatSession` & `ChatMessage`: AI conversation history

- **API Endpoints Structure**
  - `/api/v1/auth` → register, login, refresh token
  - `/api/v1/signals` → fetch signals (not fully implemented)
  - `/api/v1/unslug`, `/api/v1/fear-index` → organism-specific endpoints
  - `/api/v1/subscription` → manage plans (stub)
  - `/api/v1/payment` → process payments (stub)
  - `/health` & `/test/*` → health checks & demo endpoints

- **Organism Integration** (Wrapper layer complete)
  - `BaseOrganism` class with async `compute_trust()` method
  - `OrganismManager` orchestrating all three organisms
  - Shared `OrganismOutput` schema (organism, symbol, signal, trust, explain)
  - Basic placeholder logic for UNSLUG, FearIndex, MarketFlow (demo calculations)

- **WebSocket Router**
  - Socket.io integration (socket_manager.py)
  - Router & namespace setup
  - Message broadcasting capability (structure in place)

- **Scheduler Service**
  - APScheduler integration (scheduler.py)
  - Startup/stop hooks
  - Placeholder for periodic signal computation

#### Frontend Infrastructure
- **Next.js 14 Setup**
  - App Router (pages in `/src/app`)
  - TypeScript + Tailwind CSS
  - ESLint configured

- **Core Pages**
  - `/` → Landing page (Planet3D visualization + nav)
  - `/auth/login`, `/auth/register` → Authentication UI
  - `/dashboard` → Main dashboard (stub)
  - `/signals` → Signal feed
  - `/unslug`, `/fear-index` → Organism-specific pages
  - `/pricing` → Subscription plans
  - `/stocks/[ticker]` → Individual stock detail page

- **Key Components**
  - `CityVisualization`, `Planet3D` → 3D city & planet rendering (Spline)
  - `SignalCard`, `FearIndexCard` → Signal display cards
  - `CoreOrb`, `GlassCard` → UI primitives
  - `StatTiles`, `SignalRadar`, `TimelineFlow` → Data visualizations
  - `SubscribeButton`, `ShippingButton` → Action buttons
  - `StockDashboard` + subcomponents (SearchBar, Sidebar, StockChart, etc.)

- **API Client**
  - `lib/api.ts` → Axios wrapper for backend communication
  - Stock utilities (lib/stockUtils.ts, lib/stockApi.ts)
  - Environment variable injection for backend URL & WebSocket URL

- **Styling & Tokens**
  - Tailwind CSS 4 with custom tokens
  - Dark mode optimized (dark theme throughout)
  - Gradient branding (cyan → violet)

### ⚠️ Partial / Incomplete

- **Organism Logic**
  - Current implementation: placeholder formulas (simple price % change, volatility calculation, volume ratio)
  - **Required:** Actual UNSLUG dip-detection algorithm, FearIndex volatility metrics, MarketFlow liquidity analysis
  - No real factor calibration or weight configuration

- **Data Integration**
  - Test endpoints exist (`/test/signals`, `/test/unslug/{symbol}`, `/test/fear-index/{symbol}`)
  - Real data sources (Alpha Vantage, Yahoo Finance) not integrated into scheduler yet
  - No cold-start or Universe selection strategy

- **Subscription & Payment Flow**
  - Models defined; endpoints not fully wired
  - Toss/Stripe/Crypto integrations: scaffolding only

- **Frontend-Backend Integration**
  - API routes defined; many endpoints not consuming real data
  - WebSocket alerts: infrastructure ready, not actively broadcasting

- **UI/UX Refinement**
  - Components exist; user flows not fully tested
  - Responsive behavior on mobile incomplete

---

## 4. Key Design & Architecture Decisions

### Why This Stack?

| Decision | Rationale |
|----------|-----------|
| **FastAPI over Django** | Async-first, minimal overhead, excellent for real-time (WebSocket) patterns. |
| **PostgreSQL + SQLAlchemy** | Type-safe ORM, strong ACID guarantees for financial data integrity. |
| **JWT over Session Cookies** | Stateless, scalable; aligns with API-first architecture & potential future mobile apps. |
| **Socket.io for WebSocket** | Fallback support (long-polling), room management, built-in namespacing. |
| **Next.js + React** | Server-side rendering, API routes, incremental adoption of React Server Components. |
| **Spline 3D** | No-code 3D asset management; lowers dev friction for creative visualization. |
| **Three.js for Interactivity** | Custom 3D effects where Spline limitations appear; full control over animations. |
| **Monorepo Structure** | Single repository eases shared schema iteration (shared/schemas.py). Type safety across boundaries. |

### Organism Design Philosophy

**Three Equal Organisms, Independent Logic**
- No built-in voting/aggregation at the "city-wide" level (v1.5).
- Each organism outputs independent Trust score (0–1).
- Frontend maps Trust → visual state (dim/stable/thriving).
- **Future:** City-wide aggregation function TBD (weighted average, geometric mean, Bayesian fusion, etc.).

**Trust Score Calibration (Not Accuracy)**
- Trust = *How confident is this signal right now?* (not *How often was it correct in backtest?*)
- Factors normalized to [0,1] using percentile transforms or rolling min-max.
- Monotone aggregation (geometric mean, harmonic mean, or logistic) to avoid arbitrary weightings.
- Reliability diagrams (decile analysis) inform calibration post-backtest.

### Configuration & Open Decisions

Per the Claude Guide (v1.5), **any missing numeric choice must be surfaced as REQUIRED_DECISION, not assumed.**

**Examples of Open Decisions:**
- Dynamic pricing function by Trust (placeholder TBD).
- City-wide aggregation algorithm.
- Data provider refresh cadence (daily? hourly? real-time?).
- Universe selection (which tickers? how many?).
- Sentiment source availability & integration.
- Factor weights & calibration constants (→ config/*.json).

**File:** `backend/src/core/REQUIRED_DECISION.md` (to be created as decisions are reached).

---

## 5. Unresolved Items & Pending Work

### Critical Path Issues

| Issue | Impact | Priority |
|-------|--------|----------|
| **Organism Logic Not Production-Ready** | Signals unreliable; users lose trust | **🔴 HIGH** |
| **Data Refresh Schedule Undefined** | Users see stale signals | **🔴 HIGH** |
| **No Cold-Start Strategy** | New tickers won't have history | **🟡 MEDIUM** |
| **Payment Flow Incomplete** | Can't process real subscriptions | **🟡 MEDIUM** |
| **Trust Calibration Not Validated** | Trust scores may be meaningless | **🟡 MEDIUM** |
| **WebSocket Broadcast Inactive** | Real-time alerts don't trigger | **🟡 MEDIUM** |
| **Mobile Responsiveness** | Frontend breaks on small screens | **🟡 MEDIUM** |

### Detailed Blockers

1. **Organism Implementation**
   - UNSLUG: Needs actual mean-reversion detection, Fibonacci retracement, liquidity floor checks.
   - FearIndex: Needs realized volatility percentile, drawdown intensity, gap/limit detection.
   - MarketFlow: Needs turnover acceleration, breadth proxy (advance/decline), directional bias.
   - Current: Placeholder formulas (simple moving avg, price % change, volume ratio).

2. **Data Pipeline**
   - No live data fetch from Alpha Vantage / Yahoo Finance into scheduler.
   - Backtest harness missing (walk-forward, rolling-origin evaluation).
   - No JSON reports or PNG plots for calibration review.

3. **Dynamic Pricing**
   - Pricing function by Trust score not defined (e.g., Premium starts at 0.7 Trust? Enterprise at 0.85?).
   - No pricing tier differentiation strategy.

4. **API Completeness**
   - Many endpoints return stubs or hardcoded test data.
   - Missing `/v1/organisms/backtest`, `/v1/signals/history/{symbol}`, `/v1/trust/calibration`.

5. **Frontend Integration**
   - Many API calls stubbed or returning mock data.
   - No real subscription flow (UI only).
   - Stock dashboard queries external `/api/stocks/*` (Next.js API routes); not connected to FastAPI backend.

6. **Environment Variables & Secrets**
   - `.env.example` exists; production secrets not fully documented.
   - Some API keys optional (Alpha Vantage, Coinbase) but usage unclear.

### Deferred (Not Urgent)

- City-wide aggregation algorithm (scoped for post-v1.5).
- Sentiment integration (requires news API + LLM processing).
- Cryptocurrency data sources (Coinbase integration scaffolded).
- Bio-Health & Growth/Food layers (locked; finance-only in v1.5).
- Advanced backtest metrics (Sharpe, max drawdown, Calmar ratio).

---

## 6. Next Steps & Priorities

### Phase 1: Foundation (Weeks 1–2)
**Goal:** Validate core organism logic & establish reliable data pipeline.

**Tasks:**
1. **Implement Real Organism Logic**
   - [ ] UNSLUG: Dip-detection algorithm (VWAP z-score, Fibonacci bands, liquidity floor).
   - [ ] FearIndex: Realized volatility percentile, drawdown intensity, gap frequency.
   - [ ] MarketFlow: Turnover acceleration, breadth proxy, directional bias.
   - [ ] Create `backend/src/core/factor_calculations.py` (normalized factor functions).
   - [ ] Create `backend/src/core/trust_aggregation.py` (monotone aggregation logic).
   - [ ] Add config files: `backend/config/organisms.json`, `backend/config/factors.json`.

2. **Data Pipeline Setup**
   - [ ] Integrate Alpha Vantage / Yahoo Finance API calls into scheduler.
   - [ ] Define data refresh cadence (e.g., 5min intraday, 1day daily).
   - [ ] Create `backend/src/adapters/data/` (pluggable data provider abstraction).
   - [ ] Build backtest harness: `backend/src/core/calibration/backtest.py`.
   - [ ] Create `backend/src/core/calibration/reliability.py` (decile analysis, calibration plots).

3. **Test & Validate**
   - [ ] Unit tests for each organism (test/organisms/test_unslug.py, etc.).
   - [ ] Integration test: fetch real data → compute signals → validate output schema.
   - [ ] Backtest on historical data (2020–2025); check hit-rate, drawdown protection.
   - [ ] Export calibration report (JSON + PNG).

**Deliverable:** `REQUIRED_DECISION.md` updated with resolved numeric choices.

---

### Phase 2: Backend Integration (Weeks 2–3)
**Goal:** Wire up API endpoints & activate real-time flow.

**Tasks:**
1. **Complete API Endpoints**
   - [ ] `GET /api/v1/signals/{symbol}` → fetch latest signals for ticker.
   - [ ] `GET /api/v1/signals/history/{symbol}?days=30` → historical signals.
   - [ ] `POST /api/v1/signals/backtest` → run organism backtest on ticker.
   - [ ] `GET /api/v1/organisms/{organism_type}/latest` → latest signal per organism.
   - [ ] `GET /api/v1/trust/calibration/{organism}` → reliability diagram + metrics.

2. **Activate Scheduler**
   - [ ] Wire scheduler → organism computation → database storage.
   - [ ] Broadcast signals via WebSocket to connected clients.
   - [ ] Emit notifications for high-confidence signals.

3. **Subscription & Payment** (MVP)
   - [ ] Wire `/api/v1/subscription/create` → POST to Toss/Stripe.
   - [ ] Webhook handlers for payment confirmation.
   - [ ] Subscription status check before signal access.

**Deliverable:** All API endpoints functional; backtest report published.

---

### Phase 3: Frontend Integration & Refinement (Weeks 3–4)
**Goal:** Connect frontend to real backend data; polish UX.

**Tasks:**
1. **Frontend Data Integration**
   - [ ] Update `lib/api.ts` to call real backend endpoints (not mocked).
   - [ ] Replace hardcoded test data in `/dashboard`, `/signals`, `/unslug`, `/fear-index` pages.
   - [ ] Connect `/stocks/[ticker]` to real signal data (backend `/api/v1/signals/{symbol}`).
   - [ ] Implement real-time WebSocket listeners (socket.io-client).

2. **Subscription Flow**
   - [ ] Build subscription purchase page (`/pricing` → payment form → webhook).
   - [ ] Display subscription status in dashboard.
   - [ ] Hide signals behind paywall (basic tier: limited access).

3. **Visualization & UX**
   - [ ] City visualization responds to real Trust scores (dim/stable/thriving).
   - [ ] Signal cards update real-time via WebSocket.
   - [ ] Mobile responsiveness pass (breakpoints at 640px, 1024px).
   - [ ] Dark mode validation (already default; ensure contrast).

**Deliverable:** Full frontend-backend integration; live demo with real signals.

---

### Phase 4: Launch Prep (Week 4–5)
**Goal:** Production readiness & deployment.

**Tasks:**
1. **Testing & QA**
   - [ ] End-to-end tests (Playwright): signup → subscribe → view signals → backtest.
   - [ ] Load testing (Locust): 100+ concurrent users, signal requests.
   - [ ] Security review: JWT expiry, CORS misconfiguration, SQL injection, XSS.

2. **Deployment**
   - [ ] Railway: PostgreSQL + Redis setup, environment variables, database migrations.
   - [ ] Vercel: environment variables, API route proxying (optional).
   - [ ] SSL certificates, custom domain.
   - [ ] CI/CD: GitHub Actions for automated testing + deployment.

3. **Monitoring & Logging**
   - [ ] Sentry integration (error tracking).
   - [ ] Structured logging review (structlog + JSON output).
   - [ ] Uptime monitoring (Railway/Vercel dashboards).

4. **Documentation**
   - [ ] API documentation (FastAPI `/docs`).
   - [ ] User onboarding guide (how to read Trust scores, interpret signals).
   - [ ] Admin manual (how to tune factors, run backtest).

**Deliverable:** Live on Railway + Vercel; public beta or MVP launch.

---

### Phase 5+: Growth & Iteration (Post-Launch)
- **City-Wide Aggregation:** Implement multi-organism consensus algorithm.
- **Dynamic Pricing:** Tie subscription cost to average Trust scores.
- **Sentiment Integration:** Add news/sentiment features to FearIndex & MarketFlow.
- **Mobile App:** React Native or Flutter app.
- **Advanced Backtesting:** Sharpe, max drawdown, Calmar ratio, parameter optimization.

---

## 7. Strategic Insights & Learning Points

### What's Working

1. **Architecture is Sound**
   - Monorepo + shared schemas reduces friction across backend/frontend.
   - Async FastAPI + SQLAlchemy 2.0 is performant and scalable.
   - Spline + Three.js enables creative 3D visualization without major dev overhead.

2. **Organism Design is Smart**
   - Independent engines reduce single-point-of-failure risk.
   - Trust score (not prediction accuracy) is the right framing for "should I listen?"
   - Explainability (factors) builds user confidence vs. black-box signals.

3. **Market Positioning is Unique**
   - Three-organism approach differentiates from typical single-indicator services.
   - Trust calibration + city metaphor are memorable (not just another dashboard).
   - Subscription tiers align with user segments (retail → pro → enterprise).

### What Needs Care

1. **Organism Logic is the Core Differentiator**
   - If algorithms are just placeholder math, Trust scores are meaningless.
   - **Investment required:** Real factor research, backtesting, calibration rigor.
   - Without this, no competitive moat.

2. **Data Quality & Freshness Are Make-or-Break**
   - Stale signals = lose users fast.
   - Scheduler + data pipeline must be bulletproof (handle outages, delays gracefully).
   - Consider fallback to different data sources (Alpha Vantage → IEX → Polygon).

3. **User Trust is Fragile**
   - One bad signal or outage damages credibility disproportionately.
   - Transparency (show factor breakdown, backtest results, known limitations) is essential.
   - Consider in-app education: "Why this signal fired" with explainer videos.

4. **Scale Challenges Ahead**
   - Real-time computation for 1000+ tickers + multiple organisms = CPU-intensive.
   - Consider: GPU-accelerated compute, distributed calculation (Dask/Ray), caching layer.
   - WebSocket broadcasting to 10K+ users may need Redis Pub/Sub or dedicated message queue.

### Potential Pivots or Focus Shifts

1. **B2B Over B2C?**
   - Current model targets retail traders (B2C).
   - Pivot to **sell signals to hedge funds** (B2B API) = higher LTV, less churn.
   - Requires: white-label dashboard, SLA guarantees, compliance audits.

2. **Narrow Universe?**
   - Trying to cover all tickers is resource-heavy.
   - Focus on **specific sectors** (e.g., tech, biotech, commodities) = deeper signals, easier marketing.

3. **Gamification / Leaderboards?**
   - "Trust score" is abstract for retail users.
   - Add **portfolio simulation**: "Follow UNSLUG's Buy signals in a paper account; compare returns to S&P 500."
   - Leaderboards (top traders using UNSLUG signals) = viral growth + retention.

4. **Open-Source the Algorithms?**
   - Publish UNSLUG/FearIndex/MarketFlow as open-source Python libraries.
   - Monetize via: premium API, hosted compute, training courses.
   - Community contributions improve algorithms; users trust more.

### Key Metrics to Track

Once live:
- **Signal Hit-Rate:** % of Buy signals that see +X% gain within Y days.
- **Trust vs. Accuracy:** Decile analysis—do high-Trust signals outperform low-Trust?
- **Subscription Churn:** Monthly churn rate by plan tier.
- **Data Freshness:** P99 latency for signal computation (target: <5 min from new OHLCV bar).
- **User Engagement:** Daily/weekly active users, signals viewed per user, backtest runs.
- **API Uptime:** Target 99.5% (not 99.9% for early stage; 99.95% post-scale).

---

## 8. Immediate Action Items (Next 1 Week)

### Must-Do
1. [ ] **Decision Checkpoint:** Agree on organism factor weights & calibration method.
   - Schedule 30min sync with quant/trading advisor (if applicable).
   - Document in `REQUIRED_DECISION.md`.

2. [ ] **Data Pipeline Design:**
   - Choose data source (Alpha Vantage API keys ready?).
   - Sketch scheduler job: `every 5 minutes → fetch OHLCV → compute organisms → store → broadcast`.

3. [ ] **Real Organism Logic Skeleton:**
   - Implement placeholder → actual algorithm per organism.
   - Bonus: Run backtest on SPY 2020–2025, show hit-rate.

4. [ ] **Backend API Wiring:**
   - Add `GET /api/v1/signals/{symbol}` endpoint (real DB query).
   - Test in Postman or curl.

### Nice-to-Have
- [ ] Create `REQUIRED_DECISION.md` template.
- [ ] Set up GitHub Actions for CI/CD skeleton.
- [ ] Document database schema diagram (or Mermaid ERD).

---

## 9. File Organization & Roadmap

### Backend `/src` Structure (Current vs. Needed)

```
src/
├── core/
│   ├── organisms.py          ✅ (wrapper; needs logic)
│   ├── unslug.py             ⚠️ (placeholder)
│   ├── fear_index.py         ⚠️ (placeholder)
│   ├── market_flow.py        🔴 (missing; in organisms.py)
│   ├── factor_calculations.py 🔴 (NEW: normalized factors)
│   ├── trust_aggregation.py  🔴 (NEW: monotone aggregation)
│   └── calibration/
│       ├── backtest.py       🔴 (NEW: walk-forward backtester)
│       ├── reliability.py    🔴 (NEW: decile analysis & plots)
│       └── metrics.py        🔴 (NEW: hit-rate, Sharpe, etc.)
├── adapters/
│   └── data/                 🔴 (NEW: pluggable data providers)
│       ├── base.py           (abstract DataProvider)
│       ├── alpha_vantage.py  (Alpha Vantage implementation)
│       ├── yahoo.py          (Yahoo Finance implementation)
│       └── iex.py            (optional: IEX Cloud)
├── api/
│   ├── auth.py               ✅
│   ├── signals.py            ⚠️ (stub)
│   ├── subscription.py       ⚠️ (stub)
│   ├── payment.py            ⚠️ (stub)
│   ├── unslug.py             ⚠️ (test endpoint only)
│   └── fear_index.py         ⚠️ (test endpoint only)
├── websocket/
│   ├── socket_manager.py     ✅
│   └── router.py             ⚠️ (needs broadcast logic)
├── services/
│   ├── ai_service.py         ⚠️ (placeholder)
│   ├── payment_service.py    ⚠️ (stub)
│   └── scheduler.py          ⚠️ (needs wiring)
├── db/
│   ├── database.py           ✅
│   └── models.py             ✅
└── main.py                   ✅
```

### Frontend `/src` Structure (Current vs. Needed)

```
src/
├── app/
│   ├── page.tsx              ✅
│   ├── layout.tsx            ✅
│   ├── auth/
│   │   ├── login/page.tsx    ✅
│   │   └── register/page.tsx ✅
│   ├── dashboard/page.tsx    ⚠️ (stub → real data)
│   ├── signals/page.tsx      ⚠️ (stub → real data)
│   ├── unslug/page.tsx       ⚠️ (stub → real data)
│   ├── fear-index/page.tsx   ⚠️ (stub → real data)
│   ├── pricing/page.tsx      ✅
│   └── stocks/[ticker]/page.tsx ⚠️ (needs backend integration)
├── components/
│   ├── CityVisualization.tsx ✅ (Spline 3D)
│   ├── SignalCard.tsx        ✅
│   └── ... (40+ components, mostly ✅ but need real data)
├── lib/
│   ├── api.ts                ⚠️ (mocked → real)
│   └── ...
└── types/
    └── schemas.ts            ✅
```

---

## Conclusion

**UNSLUG City** has solid foundational infrastructure. The real value creation happens now:

1. **Transform placeholder algorithms into production-grade organism logic.**
2. **Validate Trust calibration through rigorous backtesting.**
3. **Build the data pipeline that keeps signals fresh & reliable.**
4. **Connect frontend to backend and achieve full end-to-end integration.**

Success depends on **execution rigor**—especially in organism logic and data pipeline reliability. The architecture is ready; the domain expertise (quantitative finance, signal calibration) is the bottleneck.

**Next 2 weeks:** Organism logic + data pipeline. **Weeks 3–4:** Integration & launch.

---

**Questions or clarifications?** File an issue in the codebase or sync with the team.
