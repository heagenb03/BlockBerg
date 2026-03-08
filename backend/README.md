# BlockBerg Backend

FastAPI service that provides fund watchlists, XRPL (testnet) fund/events/escrow data, and ML endpoints: yield forecast, anomaly detection, and risk scores.

---

## Requirements

- **Python 3.10+**
- Dependencies: `requirements.txt` (FastAPI, uvicorn, xrpl-py, pandas, numpy, scikit-learn, TensorFlow, requests)

---

## Setup and run

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

API docs: **http://localhost:8001/docs**

---

## API overview

| Route | Description |
|-------|-------------|
| `GET /api/funds` | Watchlist of MMFs (metadata, tickers) for FundCard panel |
| `GET /api/xrpl/fund` | Current MPT fund metrics (supply, NAV, yield_7d, TVL, recent txns) |
| `GET /api/xrpl/events` | Recent XRPL transaction stream for the fund wallet |
| `GET /api/xrpl/escrow` | Active token escrow positions (T+1-style settlement demo) |
| `GET /api/ml/yield-forecast` | Yield time series + optional LSTM forecast; `?ticker=` for specific ticker |
| `GET /api/ml/anomalies` | Anomaly detection alerts from event stream |
| `GET /api/ml/risk-scores` | Per-fund risk scores (0–100) from composite model |

CORS is set for `http://localhost:5173` and `http://localhost:5174` so the frontend can call the API.

---

## Main modules

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, lifespan (XRPL init, escrow settler task), CORS, all routes; synthetic yield fallback when ML unavailable |
| `xrpl_client.py` | XRPL testnet connection, MPT issuance, wallet/state, escrow create/finish, event formatting; `state.json` holds wallet (gitignored) |
| `data_fetcher.py` | Fund list and metadata (BUIDL, USYC, USDY, etc.); optional CSV and RWA Pipe API for token data |
| `yield_predictor_2.py` | LSTM yield prediction pipeline: load/clean token & yield CSVs, scale, train/test split, fit model, predict |
| `_ml_yield.py` | Bridge for `/api/ml/yield-forecast`: builds time-series dict for YieldChart; runs LSTM in background thread |
| `_ml_risk.py` | Risk scores from yield volatility (CSV) + fund metadata (TVL, KYC, min investment) |
| `_ml_anomalies.py` | Anomaly detection on XRPL event stream (e.g. Isolation Forest on transfer size / volume features) |
| `rwapipe_client.py` | Optional RWA Pipe API client (market, treasury tokens); see `RWAPIPE_API.md` |

---

## Data files (CSV)

Used for ML and fund metadata; paths are in the modules above.

| File / location | Use |
|-----------------|-----|
| `backend/daily_yields_2-19-26_to_3-6-26.csv` | Daily yields by product/date → yield forecast + risk volatility |
| `backend/rwa-token-timeseries-export-1772849815861.csv` | Token time-series for LSTM (yield_predictor_2) |
| `data/` (repo root) | Optional: `rawxyz_rwa-*.csv`, `defillamma_rwa-*.csv` for data_fetcher |

If a CSV is missing, the corresponding ML endpoint may fall back to defaults or synthetic data (see `main.py` and the `_ml_*` modules).

---

## XRPL and state

- **Network**: XRPL **testnet** (AltNet). URL is in `xrpl_client.py`.
- **state.json**: Generated at runtime; holds wallet/keys and on-chain state. **Do not commit** (in `.gitignore`). Delete it to re-initialize (new faucet wallet, etc.).

---

## Environment

- No required env vars for basic run. Optional: RWA Pipe API key (see `RWAPIPE_API.md` / `rwapipe_client.py`) if you use those endpoints or data sources.
