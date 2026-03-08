# XRPLBlerg

**Bloomberg Terminal 4 Tokenized MMF** — Midwest Blockathon '26

A terminal-style dashboard for tokenized money market funds (MMFs) and real-world assets (RWA). Displays fund watchlists, XRPL-based MPT (Multi-Purpose Token) fund metrics, escrow positions, event streams, and ML-powered yield forecasts, risk scores, and anomaly detection.

---

## Project structure

```
XRPLBlerg/
├── frontend/          # React + Vite terminal UI (see frontend/README.md)
├── backend/            # FastAPI + XRPL + ML (see backend/README.md)
├── data/               # Optional CSV time-series (RWA/token data)
├── README.md           # This file
└── LICENSE
```

- **Frontend**: Resizable panels (fund cards, yield chart, escrow, alerts, events, risk gauges). Proxies `/api` and `/ws` to the backend.
- **Backend**: REST API for funds, XRPL fund/events/escrow, and ML endpoints (yield forecast, anomalies, risk scores). Uses XRPL testnet for MPT and escrow demos.

---

## Quick start

1. **Backend** (Python 3.10+):

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8001
   ```

2. **Frontend** (Node 18+):

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. Open **http://localhost:5173** (or the port Vite prints). The frontend proxies `/api` to `http://localhost:8001`.

---

## Tech stack

| Layer    | Stack |
|----------|--------|
| Frontend | React 19, Vite 7, Tailwind CSS 4, Recharts, react-resizable-panels, Axios |
| Backend  | FastAPI, xrpl-py (XRPL testnet), pandas, scikit-learn, TensorFlow/Keras |
| Data     | CSV time-series (tokens/yields), optional [RWA Pipe](https://rwapipe.com) API |

---

## Data and configuration

- **CSV files**: The backend can use token and yield CSVs in `backend/` or `data/` for ML (yield predictor, risk, anomalies). See `backend/README.md` for paths and formats.
- **XRPL**: Backend uses XRPL **testnet** (AltNet). Wallet/state is stored in `backend/state.json` (gitignored); do not commit secrets.
- **Mock mode**: Frontend can run without the backend by setting `VITE_USE_MOCK=true` (see `frontend/README.md`).

---

## License

See [LICENSE](LICENSE).
