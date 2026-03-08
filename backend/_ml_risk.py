"""
Risk scorer for MMF Terminal.

Model: weighted composite (MinMaxScaler, 0–100). No supervised ML — pure
heuristic scoring on fund metadata + yield-history volatility.

Sub-scores
----------
nw_stress   — net-worth / structural risk
                 features: tvl_size (inv), kyc_required (penalty), min_investment (inv)
vol_index   — yield volatility risk
                 features: yield_volatility, network_count (inv)

Composite score = 0.50 * nw_stress + 0.50 * vol_index

Exported
--------
get_risk_scores() → list[dict]
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_YIELD_CSV = Path(__file__).parent / "daily_yields_2-19-26_to_3-6-26.csv"

# Map CSV product name prefix → ticker (short names used in the actual CSV)
_CSV_PRODUCT_MAP: dict[str, str] = {
    "BlackRock BUIDL": "BUIDL",
    "Circle USYC": "USYC",
    "Ondo U.S. Dollar Yield": "USDY",
    "Franklin OnChain": "BENJI",
    "WisdomTree Gov MMF": "WTGXX",
}

_DEFAULT_YIELD_VOL: float = 0.15   # fallback when CSV is missing or ticker not found
_MMFXX_YIELD_VOL: float = 0.12    # synthetic XRPL fund — low volatility by design

# Scoring weights
_NW_WEIGHTS = (0.55, 0.30, 0.15)   # tvl_inv, kyc_penalty, min_inv_inv
_VOL_WEIGHTS = (0.60, 0.40)         # yield_vol, net_inv
_COMPOSITE_WEIGHTS = (0.50, 0.50)   # nw_stress, vol_index


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_yield_volatility() -> dict[str, float]:
    """Parse daily_yields CSV → per-ticker std-dev of yield (as decimal, not %).

    CSV layout: rows = products, columns = dates.
    First column is "Product"; date columns hold values like "3.47%" or "N/A".
    Returns {ticker: std_dev_float}. MMFXX always gets _MMFXX_YIELD_VOL.
    """
    vols: dict[str, float] = {"MMFXX": _MMFXX_YIELD_VOL}

    if not _YIELD_CSV.exists():
        logger.warning("Yield CSV not found at %s — using defaults.", _YIELD_CSV)
        return vols

    try:
        with _YIELD_CSV.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                product = row[0].strip()
                ticker = next(
                    (t for prefix, t in _CSV_PRODUCT_MAP.items()
                     if product.startswith(prefix)),
                    None,
                )
                if ticker is None:
                    continue

                values: list[float] = []
                for cell in row[1:]:
                    cell = cell.strip()
                    if cell and cell.upper() != "N/A" and cell != "":
                        try:
                            values.append(float(cell.rstrip("%")) / 100.0)
                        except ValueError:
                            pass

                if len(values) >= 2:
                    vols[ticker] = float(np.std(values))
                elif values:
                    vols[ticker] = 0.0
    except Exception:
        logger.exception("Error parsing yield CSV.")

    return vols


def _load_fund_features() -> list[dict[str, Any]]:
    """Merge live fund metadata with yield volatility into a unified feature list.

    Falls back to _FUND_META from data_fetcher if the live API call fails.
    """
    from data_fetcher import FUND_TICKERS, _FUND_META  # noqa: PLC0415

    vols = _load_yield_volatility()

    try:
        from data_fetcher import get_fund_list  # noqa: PLC0415
        live = {f["ticker"]: f for f in get_fund_list()}
    except Exception:
        logger.warning("data_fetcher unavailable — using hardcoded _FUND_META.")
        live = {}

    features: list[dict[str, Any]] = []
    for ticker in FUND_TICKERS:
        meta = _FUND_META[ticker]
        live_row = live.get(ticker, {})

        features.append({
            "ticker":           ticker,
            "tvl":              live_row.get("tvl") or 0.0,
            "kyc_required":     live_row.get("kyc_required", meta["kyc_required"]),
            "min_investment":   live_row.get("min_investment", meta["min_investment"]),
            "network_count":    live_row.get("network_count", meta["network_count"]),
            "yield_volatility": vols.get(ticker, _DEFAULT_YIELD_VOL),
        })

    return features


# ---------------------------------------------------------------------------
# MinMaxScaler helper
# ---------------------------------------------------------------------------

def _safe_minmax(arr: np.ndarray) -> np.ndarray:
    """MinMaxScale arr to [0, 1]; if all values are identical return 0.5 array."""
    lo, hi = arr.min(), arr.max()
    if hi - lo < 1e-12:
        return np.full_like(arr, 0.5, dtype=float)
    return (arr - lo) / (hi - lo)


# ---------------------------------------------------------------------------
# Sub-score computation
# ---------------------------------------------------------------------------

def _compute_nw_stress(features: list[dict[str, Any]]) -> np.ndarray:
    """Compute net-worth stress scores (0–100) for each fund.

    Higher score = more structural risk.

    Parameters
    ----------
    features : list of fund feature dicts with keys:
        tvl (float, USD), kyc_required (bool), min_investment (float)

    Returns
    -------
    np.ndarray of shape (n_funds,) with values in [0, 100].

    """
    net_worth = np.array([f["tvl"] for f in features], dtype=float)
    kyc = np.array([f["kyc_required"] for f in features], dtype=bool)
    min_inv = np.array([f["min_investment"] for f in features], dtype=float)
    
    tvl_inv = 1 / (net_worth + 1)
    kyc_penalty = np.where(kyc, 0.0, 1.0)
    min_inv_inv = 1 / (min_inv + 1)
    
    tvl_score = _safe_minmax(tvl_inv)
    kyc_score = kyc_penalty
    min_inv_score = _safe_minmax(min_inv_inv)
    
    w_tvl, w_kyc, w_min_inv = _NW_WEIGHTS
    composite = w_tvl * tvl_score + w_kyc * kyc_score + w_min_inv * min_inv_score
    return composite * 100.0
    


def _compute_vol_index(features: list[dict[str, Any]]) -> np.ndarray:
    """Compute volatility index scores (0–100) for each fund.

    Higher score = more volatile / concentrated-chain risk.

    Parameters
    ----------
    features : list of fund feature dicts with keys:
        yield_volatility (float, std dev as decimal), network_count (int)

    Returns
    -------
    np.ndarray of shape (n_funds,) with values in [0, 100].

    """
    yield_vol = np.array([f["yield_volatility"] for f in features], dtype=float)
    network_count = np.array([f["network_count"] for f in features], dtype=int)
    
    network_inv = 1 / (network_count + 1)
    
    yield_vol_score = _safe_minmax(yield_vol)
    network_score = _safe_minmax(network_inv)
    
    w_yield_vol, w_network = _VOL_WEIGHTS
    composite = w_yield_vol * yield_vol_score + w_network * network_score
    return composite * 100.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_risk_scores() -> list[dict[str, Any]]:
    """Compute per-fund risk scores for all FUND_TICKERS.

    Returns list of dicts matching the contract expected by main.py and RiskGauge.jsx:
        fund_id, score, nw_stress, vol_index, components
    Raises on failure so main.py's synthetic fallback is triggered.
    """
    features = _load_fund_features()

    nw = _compute_nw_stress(features)
    vi = _compute_vol_index(features)

    w_nw, w_vi = _COMPOSITE_WEIGHTS
    composite = w_nw * nw + w_vi * vi

    results: list[dict[str, Any]] = []
    for i, f in enumerate(features):
        results.append({
            "fund_id":   f["ticker"],
            "score":     round(float(composite[i]), 1),
            "nw_stress": round(float(nw[i]), 1),
            "vol_index": round(float(vi[i]), 1),
            "components": {
                "yield_volatility": round(f["yield_volatility"], 4),
                "tvl_size":         f["tvl"],
                "kyc_required":     f["kyc_required"],
                "min_investment":   f["min_investment"],
                "network_count":    f["network_count"],
            },
        })

    return results
