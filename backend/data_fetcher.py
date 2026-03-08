from __future__ import annotations
import csv
import logging
from pathlib import Path
from typing import Any
import requests

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent / "data"
_RWA_CSV = next(_DATA_DIR.glob("rawxyz_rwa-token-timeseries-export-*.csv"), None)
_DEFILLAMA_CSV = next(_DATA_DIR.glob("defillamma_rwa-*.csv"), None)

RWAPIPE_BASE = "https://rwapipe.com/api"
RWAPIPE_TIMEOUT = 10

# yield_apy: rwa.xyz 7-day APY column, sourced 2026-03-07

_FUND_META: dict[str, dict] = {
    "BUIDL": {
        "name": "BlackRock USD Institutional Digital Liquidity Fund",
        "csv_col": "BlackRock USD Institutional Digital Liquidity Fund",
        "rwapipe_issuer": "blackrock",
        "yield_apy": 3.47,
        "kyc_required": True,
        "min_investment": 5_000_000,
        "network_count": 6,
    },
    "USYC": {
        "name": "Circle USYC",
        "csv_col": "Circle USYC",
        "rwapipe_issuer": "circle",
        "yield_apy": 3.14,
        "kyc_required": False,
        "min_investment": 1_000,
        "network_count": 2,
    },
    "USDY": {
        "name": "Ondo U.S. Dollar Yield",
        "csv_col": "Ondo U.S. Dollar Yield",
        "rwapipe_issuer": "ondo",
        "yield_apy": 5.05,
        "kyc_required": False,
        "min_investment": 500,
        "network_count": 4,
    },
    "BENJI": {
        "name": "Franklin OnChain U.S. Government Money Fund",
        "csv_col": "Franklin OnChain U.S. Government Money Fund",
        "rwapipe_issuer": "franklin",
        "yield_apy": 3.03,
        "kyc_required": True,
        "min_investment": 20,
        "network_count": 2,
    },
    "WTGXX": {
        "name": "WisdomTree Government Money Market Digital Fund",
        "csv_col": "WisdomTree Government Money Market Digital Fund",
        "rwapipe_issuer": "wisdomtree",
        "yield_apy": 3.49,
        "kyc_required": True,
        "min_investment": 1_000,
        "network_count": 1,
    },
    "MMFXX": {
        "name": "Simulated Treasury Money Market Fund",
        "csv_col": None,
        "rwapipe_issuer": None,
        "yield_apy": 4.85,
        "kyc_required": True,
        "min_investment": 100_000,
        "network_count": 1,
    },
}

FUND_TICKERS = ["MMFXX", "BUIDL", "USYC", "USDY", "BENJI", "WTGXX"]


def _load_rwa_csv() -> list[dict]:
    """Load rwa.xyz CSV rows. Returns [] on missing file."""
    if not _RWA_CSV or not _RWA_CSV.exists():
        logger.warning("rwa.xyz CSV not found in data/")
        return []
    with open(_RWA_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _latest_tvl_m(rows: list[dict], col: str) -> float | None:
    """Most recent non-empty TVL value for a column, in millions."""
    for row in reversed(rows):
        val = row.get(col, "").strip()
        if val:
            try:
                return round(float(val) / 1_000_000, 2)
            except ValueError:
                pass
    return None


def _prev_tvl_m(rows: list[dict], col: str) -> float | None:
    """Second-to-last non-empty TVL value for a column, in millions."""
    hits = 0
    for row in reversed(rows):
        val = row.get(col, "").strip()
        if val:
            hits += 1
            if hits == 2:
                try:
                    return round(float(val) / 1_000_000, 2)
                except ValueError:
                    pass
    return None


# RWAPIPE

def _rwapipe_money_market_tvl() -> dict[str, float]:
    """
    Fetch category=money-market tokens from rwapipe.com.
    Returns {issuer_name_lower: tvl_in_millions}.
    """
    try:
        r = requests.get(
            f"{RWAPIPE_BASE}/tokens",
            params={"category": "money-market", "limit": 50, "sortBy": "tvl", "order": "desc"},
            timeout=RWAPIPE_TIMEOUT,
        )
        r.raise_for_status()
        tokens = r.json().get("data", [])
        result: dict[str, float] = {}
        for t in tokens:
            issuer = (t.get("issuer") or "").lower()
            tvl = t.get("tvl")
            if issuer and tvl:
                result[issuer] = round(float(tvl) / 1_000_000, 2)
        return result
    except Exception as exc:
        logger.warning("rwapipe.com unavailable: %s", exc)
        return {}

# API

def get_fund_list() -> list[dict[str, Any]]:
    """
    Watchlist rows for FundCard panel.

    Each row: { ticker, name, tvl (M$), yld (%), chg (%), vol,
                kyc_required, min_investment, network_count }

    TVL: rwapipe live → rwa.xyz CSV fallback.
    24h chg: derived from last two CSV rows (rwapipe has no history).
    MMFXX: fixed $10M synthetic fund on XRPL Testnet.
    """
    csv_rows = _load_rwa_csv()
    live_tvl = _rwapipe_money_market_tvl()

    result = []
    for ticker in FUND_TICKERS:
        meta = _FUND_META[ticker]
        col = meta["csv_col"]
        issuer = meta["rwapipe_issuer"] or ""

        if ticker == "MMFXX":
            result.append(_build_row(ticker, meta, tvl=10.0, chg=0.0))
            continue

        # Live TVL from rwapipe — match by issuer keyword
        tvl_live: float | None = None
        for key, val in live_tvl.items():
            if issuer and issuer in key:
                tvl_live = val
                break

        tvl_csv = _latest_tvl_m(csv_rows, col) if col else None
        tvl_prev = _prev_tvl_m(csv_rows, col) if col else None
        tvl = tvl_live if tvl_live is not None else (tvl_csv or 0.0)

        if tvl_csv and tvl_prev and tvl_prev > 0:
            chg = round((tvl_csv - tvl_prev) / tvl_prev * 100, 3)
        else:
            chg = 0.0

        result.append(_build_row(ticker, meta, tvl=tvl, chg=chg))

    return result


def _build_row(ticker: str, meta: dict, tvl: float, chg: float) -> dict[str, Any]:
    return {
        "ticker": ticker,
        "name": meta["name"],
        "tvl": tvl,
        "yld": meta["yield_apy"],
        "chg": chg,
        "vol": round(tvl * 0.02, 2),
        "kyc_required": meta["kyc_required"],
        "min_investment": meta["min_investment"],
        "network_count": meta["network_count"],
    }


def get_tvl_history(ticker: str) -> list[dict[str, Any]]:
    """
    Daily TVL history for a single fund — used by _ml_yield.py as input features.
    Returns: [{ date, timestamp_ms, tvl_usd, tvl_m }]
    """
    meta = _FUND_META.get(ticker)
    if not meta or not meta.get("csv_col"):
        return []
    col = meta["csv_col"]
    csv_rows = _load_rwa_csv()
    history = []
    for row in csv_rows:
        val = row.get(col, "").strip()
        if val:
            try:
                tvl_usd = float(val)
                history.append({
                    "date": row.get("Date", ""),
                    "timestamp_ms": int(row.get("Timestamp", 0)),
                    "tvl_usd": tvl_usd,
                    "tvl_m": round(tvl_usd / 1_000_000, 4),
                })
            except ValueError:
                pass
    return history


def get_market_tvl() -> list[dict[str, Any]]:
    """
    Aggregate RWA market TVL time series from DefiLlama CSV.
    Returns: [{ date, timestamp_ms, tokenized_funds_usd }]
    Used by YieldChart for macro TVL overlay context.
    """
    if not _DEFILLAMA_CSV or not _DEFILLAMA_CSV.exists():
        logger.warning("DefiLlama CSV not found in data/")
        return []
    col = "Tokenized Funds (T-Bills, Bonds, MMFs)"
    result = []
    with open(_DEFILLAMA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            val = row.get(col, "").strip()
            if val:
                try:
                    result.append({
                        "date": row.get("Date", ""),
                        "timestamp_ms": int(row.get("Timestamp", 0)),
                        "tokenized_funds_usd": float(val),
                    })
                except ValueError:
                    pass
    return result
