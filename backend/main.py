"""
MMF Terminal — FastAPI backend.

Startup:
    uvicorn main:app --reload

Routes:
    GET /api/xrpl/fund          → fund metrics (MPT supply, NAV, yield, TVL)
    GET /api/xrpl/events        → recent XRPL transactions
    GET /api/xrpl/escrow        → active Token Escrow positions

    GET /api/ml/yield-forecast  → yield time series + ML forecast overlay
    GET /api/ml/anomalies       → anomaly detection alerts
    GET /api/ml/risk-scores     → per-fund risk scores (0–100)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import xrpl_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize XRPL state (wallets, MPT, escrows) on startup.

    xrpl-py's generate_faucet_wallet uses asyncio.run() internally, which
    raises RuntimeError when called from a running event loop (FastAPI/uvicorn).
    Running initialize() in a thread pool executor gives it its own event loop.
    """
    import asyncio

    logger.info("Initializing XRPL connection and state...")
    stream_task = None
    settler_task = None
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, xrpl_client.initialize)
        # Start live WebSocket stream as background task (after wallet is ready)
        stream_task = asyncio.create_task(xrpl_client.run_xrpl_stream())
        logger.info("XRPL event stream task started.")
        # Start escrow settler — finishes matured escrows every 60s
        settler_task = asyncio.create_task(xrpl_client.run_escrow_settler())
        logger.info("Escrow settler task started.")
    except Exception:
        logger.exception("XRPL initialization failed — XRPL endpoints will return 503.")
    yield
    for task in (stream_task, settler_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="MMF Terminal API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Fund watchlist route
# ---------------------------------------------------------------------------

@app.get("/api/funds")
def fund_list() -> list:
    """Watchlist of real MMFs + MMFXX synthetic fund for the FundCard panel."""
    try:
        from data_fetcher import get_fund_list
        return get_fund_list()
    except Exception as exc:
        logger.exception("Error fetching fund list")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# XRPL routes
# ---------------------------------------------------------------------------

@app.get("/api/xrpl/fund")
def fund() -> dict:
    """Current MPT fund metrics: supply, NAV, yield_7d, TVL, recent txns."""
    try:
        return xrpl_client.get_fund_data()
    except Exception as exc:
        logger.exception("Error fetching fund data")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/xrpl/events")
def events() -> list:
    """Recent XRPL transaction stream for the fund wallet."""
    try:
        return xrpl_client.get_events()
    except Exception as exc:
        logger.exception("Error fetching events")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/xrpl/escrow")
def escrow() -> list:
    """Active Token Escrow positions (T+1 settlement simulation)."""
    try:
        return xrpl_client.get_escrow_positions()
    except Exception as exc:
        logger.exception("Error fetching escrow positions")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.websocket("/ws/xrpl/events")
async def ws_events(websocket: WebSocket):
    """Live XRPL event stream via WebSocket.

    On connect: sends the buffered event history (up to 50 events).
    Then streams new events in real time as they arrive on the XRPL Testnet.
    """
    await websocket.accept()
    # Send buffer snapshot so the client sees recent history immediately
    for event in xrpl_client.get_event_buffer():
        await websocket.send_json(event)

    q = xrpl_client.subscribe_events()
    try:
        while True:
            event = await q.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        xrpl_client.unsubscribe_events(q)


# ---------------------------------------------------------------------------
# ML routes
# ---------------------------------------------------------------------------

@app.get("/api/ml/yield-forecast")
def yield_forecast() -> dict:
    """
    Yield time series with ML forecast overlay.

    Returns actual yield data points plus ML-predicted forward values.
    Falls back to synthetic data when no CSV files are available.
    """
    try:
        from _ml_yield import get_yield_forecast
        return get_yield_forecast()
    except Exception:
        logger.warning("ML yield forecast unavailable, returning synthetic data.")
        return _synthetic_yield_forecast()


@app.get("/api/ml/anomalies")
def anomalies() -> list:
    """Anomaly detection alerts from the XRPL event stream."""
    try:
        from _ml_anomalies import get_anomalies
        return get_anomalies()
    except Exception:
        logger.warning("ML anomaly detector unavailable, returning synthetic data.")
        return _synthetic_anomalies()


@app.get("/api/ml/risk-scores")
def risk_scores() -> list:
    """Per-fund risk scores (0–100) from weighted composite model."""
    try:
        from _ml_risk import get_risk_scores
        return get_risk_scores()
    except Exception:
        logger.warning("ML risk scorer unavailable, returning synthetic data.")
        return _synthetic_risk_scores()


# ---------------------------------------------------------------------------
# Synthetic fallbacks (used when ML CSV data is not yet loaded)
# ---------------------------------------------------------------------------

import math
import time


def _synthetic_yield_forecast() -> dict:
    """Generate 30 days of plausible yield data + 3-day ML forecast."""
    import random
    random.seed(42)
    now = int(time.time())
    day = 86400
    base = 4.85
    data = []
    y = base
    for i in range(30):
        ts = now - (29 - i) * day
        y += random.uniform(-0.05, 0.05)
        y = max(4.0, min(5.5, y))
        data.append(
            {
                "time": ts * 1000,  # ms for recharts
                "actual": round(y, 3),
                "predicted": None,
                "anomaly": False,
            }
        )
    # Inject 2 anomaly points
    data[10]["anomaly"] = True
    data[22]["anomaly"] = True
    # Append 3-day forecast
    pred_y = y
    for i in range(1, 4):
        pred_y += random.uniform(-0.03, 0.04)
        data.append(
            {
                "time": (now + i * day) * 1000,
                "actual": None,
                "predicted": round(pred_y, 3),
                "anomaly": False,
            }
        )
    return {"data": data}


def _synthetic_anomalies() -> list:
    now = int(time.time())
    return [
        {
            "timestamp": (now - 3600) * 1000,
            "type": "Settlement Delay",
            "severity": "Critical",
            "description": "Transfer latency 4.2σ above rolling mean — escrow batch delayed.",
        },
        {
            "timestamp": (now - 7200) * 1000,
            "type": "Volume Spike",
            "severity": "Warning",
            "description": "Transfer volume 2.8σ above 7d average — unusual redemption activity.",
        },
        {
            "timestamp": (now - 14400) * 1000,
            "type": "Low Liquidity",
            "severity": "Info",
            "description": "Net outflow exceeded 5% of TVL in 1hr window.",
        },
    ]


def _synthetic_risk_scores() -> list:
    return [
        {
            "fund_id": "MMFXX",
            "score": 28,
            "nw_stress": 24,
            "vol_index": 31,
            "components": {
                "yield_volatility": 0.12,
                "tvl_size": 10_000_000,
                "kyc_required": True,
                "min_investment": 100_000,
                "network_count": 1,
            },
        },
        {
            "fund_id": "BUIDL",
            "score": 19,
            "nw_stress": 15,
            "vol_index": 22,
            "components": {
                "yield_volatility": 0.08,
                "tvl_size": 520_000_000,
                "kyc_required": True,
                "min_investment": 5_000_000,
                "network_count": 5,
            },
        },
        {
            "fund_id": "USDY",
            "score": 44,
            "nw_stress": 51,
            "vol_index": 38,
            "components": {
                "yield_volatility": 0.21,
                "tvl_size": 75_000_000,
                "kyc_required": False,
                "min_investment": 500,
                "network_count": 3,
            },
        },
    ]
