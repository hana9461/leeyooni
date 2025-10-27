# UNSLUG — City of Signals v1.5 (Claude Implementation Guide)
**Date:** 2025-10-12  
**Owner:** 이윤구  
**Scope:** Finance Layer only (Economic Layer / City of Signals). Bio-Health & Growth/Food are locked (not opened).

---

## 0) Executive Summary
- Three equal-tier organisms: **UNSLUG**, **Fear Index**, **Market Flow**.
- Each organism outputs a **Trust Score** ∈ [0,1]. Early phase: **no City-wide aggregation**.
- Subscription model; dynamic pricing **by Trust** is planned (function TBD; do not invent numbers).
- Visualization: City thrives/dims based on per-organism Trust (token mapping, no numeric styles here).

This guide fixes decisions already made and avoids arbitrary constants. Any missing choices must be surfaced as `REQUIRED_DECISION` (not assumed).

---

## 1) Entities
- **Organism**: independent module producing signal + trust.
  - `UNSLUG`: bottom-dip detection buy-signal engine.
  - `FearIndex`: per-ticker fear/psychology intensity.
  - `MarketFlow`: liquidity/participation flow direction/strength.
- **Trust Score**: calibrated confidence for the organism’s current output (not accuracy).

---

## 2) Data Contracts

### 2.1 Inputs (provider-agnostic)
- OHLCV (daily & intraday), corporate actions, turnover/liquidity proxies.
- Optional for FearIndex: sentiment/news features.

### 2.2 Input slice (per symbol, per time)
{
  "symbol": "string",
  "interval": "1d | 1h | 5m",
  "ts": "ISO-8601",
  "open": number, "high": number, "low": number, "close": number,
  "volume": number, "adj_close": number|null,
  "features": {
    "rsi": number|null,
    "vwap_deviation": number|null,
    "rolling_vol": number|null,
    "liquidity_ratio": number|null,
    "sentiment": number|null
  }
}

### 2.3 Organism output
{
  "organism": "UNSLUG | FearIndex | MarketFlow",
  "symbol": "string",
  "ts": "ISO-8601",
  "signal": "BUY | NEUTRAL | RISK",
  "trust": number (0..1),
  "explain": [{"name": "...","value": number|string,"contribution":"increases_trust|decreases_trust|neutral"}]
}

---

## 3) Trust Factor Model (no arbitrary weights)
- Normalize each factor to [0,1] using monotone transforms (percentiles or rolling min-max).
- Aggregate with a **monotone** method (choose & document): geometric mean / harmonic mean / min-mean hybrid / logistic calibrated on linear score.
- If weights/configs are needed → load from `config/*.json`; if missing → emit `REQUIRED_DECISION`.

### 3.1 Factor whitelist
**UNSLUG**
- Rebound evidence (structure/divergence)
- Distance-to-mean (VWAP/rolling mean z-score)
- Liquidity floor met?
- Regime context (trend/range)
- Signal consistency (stability across lookbacks)

**FearIndex**
- Realized volatility percentile
- Drawdown depth percentile
- Gap/limit frequency
- Sentiment polarity/variance (optional)

**MarketFlow**
- Turnover acceleration (Δ turnover)
- Breadth proxy (adv/dec ratio)
- Directional bias (cum delta proxy)
- MR vs MOM signature (regime tags)

---

## 4) Evaluation & Calibration
- Walk-forward/rolling-origin backtest.
- Metrics: directional hit-rate, drawdown impact, AAE/AFE.
- Reliability diagrams for trust calibration (deciles vs precision).
- Export JSON reports; optional PNG plots.

---

## 5) API & CLI
**Local function**
```
def compute_trust(organism: str, series: list[InputSlice]) -> OrganismOutput:
    """Return signal & trust for the last slice with explain entries.
    Must not assume weights. If missing configs, return REQUIRED_DECISION.
    """
```

**Optional HTTP**
- POST /v1/trust/{organism} → OrganismOutput
- GET  /v1/health
- GET  /v1/version

---

## 6) City Visualization Contract (backend → frontend tokens)
Back-end sends only **tokens**:
{
  "city_state": "dim|stable|thriving",
  "unslug_trust": 0..1,
  "fear_trust": 0..1,
  "flow_trust": 0..1,
  "notes": "optional string"
}
Front-end maps tokens to visuals; no numeric styling in this spec.

---

## 7) Open Decisions (must be explicit)
- Dynamic pricing function by trust.
- Future City-wide aggregation function.
- Provider selection & refresh cadence.
- Universe selection (tickers) & cold-start policy.
- Sentiment source availability.

---

## 8) Deliverables for Claude
- `core/organisms/unslug.py`, `fear.py`, `flow.py`
- `core/calibration/` (reliability & calibration utilities)
- `adapters/data/` (provider adapters, pluggable)
- `contracts/` (JSON schemas in this package)
- `cli/run_once.py` (demo run)
- `out/{organism}/last_signal.json` (with explain)
- `REQUIRED_DECISION.md` for any undefined constant

**Rule:** If a numeric choice is unknown → do not guess; request decision with rationale.
