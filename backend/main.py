from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import xrpl_client
import asyncio
import math
import time
from data_fetcher import get_fund_list
from _ml_anomalies import get_anomalies
from _ml_yield import get_yield_forecast
from _ml_risk import get_risk_scores
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize XRPL state (wallets, MPT, escrows) on startup.

    xrpl-py's generate_faucet_wallet uses asyncio.run() internally, which
    raises RuntimeError when called from a running event loop (FastAPI/uvicorn).
    Running initialize() in a thread pool executor gives it its own event loop.
    """
    logger.info("Initializing XRPL connection and state...")
    settler_task = None
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, xrpl_client.initialize)
        # Start escrow settler — finishes matured escrows every 60s
        settler_task = asyncio.create_task(xrpl_client.run_escrow_settler())
        logger.info("Escrow settler task started.")
    except Exception:
        logger.exception("XRPL initialization failed — XRPL endpoints will return 503.")
    yield
    if settler_task:
        settler_task.cancel()
        try:
            await settler_task
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
        return get_yield_forecast()
    except Exception:
        logger.warning("ML yield forecast unavailable, returning synthetic data.")
        return _synthetic_yield_forecast()


@app.get("/api/ml/anomalies")
def anomalies() -> list:
    """Anomaly detection alerts from the XRPL event stream."""
    try:
        return get_anomalies()
    except Exception:
        logger.warning("ML anomaly detector unavailable")
        return []


@app.get("/api/ml/risk-scores")
def risk_scores() -> list:
    """Per-fund risk scores (0–100) from weighted composite model."""
    try:
        return get_risk_scores()
    except Exception:
        logger.warning("ML risk scores unavailable")
        return []


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