"""
_ml_yield.py — Yield forecast bridge for /api/ml/yield-forecast.

Wraps yield_predictor_2 (LSTM model) to produce the time-series dict that
YieldChart expects.  LSTM training takes 1-2 min, so it runs in a background
daemon thread on module import; the API responds immediately with real
historical data and appends ML predictions once training completes.

Output format
-------------
{"data": [{"time": ms, "actual": float|None,
           "predicted": float|None, "anomaly": bool}, ...]}

Historical actual rows come directly from the daily yields CSV (fast path).
ML-predicted rows (next 3 days) are appended after the background thread
finishes.  If training fails for any reason the endpoint still returns the
10 days of real yield data — the synthetic fallback in main.py will NOT fire
because this function does not raise.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent
_YIELD_CSV = _BACKEND_DIR / "daily_yields_2-19-26_to_3-6-26.csv"
_TOKEN_CSV = _BACKEND_DIR / "rwa-token-timeseries-export-1772849815861.csv"

# Representative fund whose yield proxies MMFXX on the chart.
_TARGET_FUND = "BlackRock BUIDL"

# Fund names that yield_predictor_2.main_pipeline expects as the test set.
# ORDER MATTERS: matches CSV column order (Ondo col 4, WisdomTree col 7,
# BUIDL col 8, USYC col 15, Franklin col 16) so BUIDL ends up at test index 2.
_YIELD_NAMES: list[str] = [
    "BlackRock BUIDL",
    "Circle USYC",
    "Ondo U.S. Dollar Yield",
    "Franklin OnChain",
    "WisdomTree Gov MMF",
]

# ---------------------------------------------------------------------------
# Module-level prediction cache
# ---------------------------------------------------------------------------
_predictions_cache: list[float] | None = None  # 3-day BUIDL yield predictions
_cache_lock = threading.Lock()
_training_started = False


# ---------------------------------------------------------------------------
# Historical data parsing
# ---------------------------------------------------------------------------

def _parse_yield_series(fund: str = _TARGET_FUND) -> list[tuple[int, float]]:
    """
    Read the daily yields CSV and return (unix_ms, yield_pct) pairs for *fund*.

    The CSV format is wide (rows = funds, columns = dates).  "N/A" values and
    the "%" suffix are handled; rows with invalid data are silently skipped.
    Returns an empty list if the fund is not found in the CSV.
    """
    df = pd.read_csv(_YIELD_CSV)
    df = df.set_index("Product")
    if fund not in df.index:
        return []

    row = df.loc[fund]
    result: list[tuple[int, float]] = []
    for date_str, val in row.items():
        if pd.isna(val):
            continue
        try:
            pct = float(str(val).replace("%", ""))
            # e.g. "2/19/26" → Timestamp("2026-02-19")
            ts_ms = int(pd.Timestamp(date_str).timestamp() * 1000)
            result.append((ts_ms, pct))
        except Exception:
            continue
    return sorted(result, key=lambda x: x[0])


# ---------------------------------------------------------------------------
# Background LSTM training
# ---------------------------------------------------------------------------

def _find_test_index(yield_df: pd.DataFrame, counter_list: list[int]) -> int:
    """
    Return the position of _TARGET_FUND in the model.predict() output array.

    counter_list holds cleaned-list indices in CSV column order.  We count
    how many funds (that passed the length check) appear before _TARGET_FUND
    in the column list to find BUIDL's position in counter_list, then map
    that to its index in the test array.
    """
    import yield_predictor_2 as yp2  # noqa: PLC0415

    cnt = 0
    buidl_counter_val: int | None = None
    for token in yield_df.columns:
        ts = yp2.clean_timeseries(yield_df[token].tolist())
        if len(ts) < 7:
            continue
        if token == _TARGET_FUND:
            buidl_counter_val = cnt
            break
        cnt += 1

    if buidl_counter_val is None or buidl_counter_val not in counter_list:
        logger.warning(
            "%s not found in test set counter_list=%s; using index 0.",
            _TARGET_FUND,
            counter_list,
        )
        return 0
    return counter_list.index(buidl_counter_val)


def _run_lstm_in_background() -> None:
    """
    Train the LSTM via yield_predictor_2 and cache 3-day predictions.

    Key fix applied here: yield_predictor_2.make_predictions() calls
    scaler.inverse_transform(predictions) where predictions has shape
    (n_funds, 3) but the StandardScaler was fit on shape (n, 1).  This
    raises a ValueError in the original code.  We bypass make_predictions
    and do the inverse_transform correctly by reshaping each prediction
    row to (-1, 1) before calling inverse_transform.
    """
    global _predictions_cache
    try:
        import yield_predictor_2 as yp2  # noqa: PLC0415

        # ── Prepare yield DataFrame (mirrors yp2.main() logic) ──────────────
        yield_df = pd.read_csv(str(_YIELD_CSV))
        yield_df = yield_df.transpose()
        col_names = yield_df.iloc[0].tolist()
        yield_df = yield_df.iloc[1:]
        yield_df.columns = col_names

        yield_indices = [yield_df.columns.tolist().index(t) for t in _YIELD_NAMES]

        # ── Extract & clean 7-day series ─────────────────────────────────────
        extended, appended, counter_list, name_list = yp2.get_all_timeseries_data(
            yield_df, 7, yield_indices, _YIELD_NAMES
        )
        if not appended:
            logger.warning("No yield timeseries extracted — skipping LSTM.")
            return

        scaled_ext, scaled_app, scaler = yp2.scale_timeseries(extended, appended)

        X_train, y_train, X_test, y_test, _ = yp2.get_train_test_data(
            scaled_app, scaler, counter_list, name_list
        )

        logger.info(
            "LSTM yield training: X_train=%s X_test=%s", X_train.shape, X_test.shape
        )
        model = yp2.build_model(X_train, y_train)

        # ── Predict (model output shape: (n_test_funds, 3)) ─────────────────
        raw_preds = model.predict(X_test)

        # ── Inverse-transform — fix shape mismatch ───────────────────────────
        # scaler was fit on shape (n, 1); we must reshape each row to (-1, 1)
        # then flatten so each fund's 3-day forecast is a 1-D array of floats.
        test_idx = _find_test_index(yield_df, counter_list)
        buidl_raw = raw_preds[test_idx]  # shape (3,)
        buidl_preds: list[float] = (
            scaler.inverse_transform(buidl_raw.reshape(-1, 1)).flatten().tolist()
        )

        with _cache_lock:
            _predictions_cache = buidl_preds

        logger.info("LSTM yield predictions cached (BUIDL, next 3 days): %s", buidl_preds)

    except Exception:
        logger.exception("LSTM yield training failed — ML predictions unavailable.")


def _start_training() -> None:
    """Kick off background LSTM training once (idempotent)."""
    global _training_started
    if _training_started:
        return
    _training_started = True

    if not (_YIELD_CSV.exists() and _TOKEN_CSV.exists()):
        logger.warning(
            "Required CSV files not found — LSTM yield training skipped.\n"
            "  yield: %s\n  token: %s",
            _YIELD_CSV,
            _TOKEN_CSV,
        )
        return

    t = threading.Thread(
        target=_run_lstm_in_background, daemon=True, name="lstm-yield-trainer"
    )
    t.start()
    logger.info("LSTM yield trainer started in background thread.")


# ---------------------------------------------------------------------------
# Public API — called by main.py
# ---------------------------------------------------------------------------

def get_yield_forecast() -> dict:
    """
    Return yield forecast time series for YieldChart.

    Reads real historical yield data for BlackRock BUIDL from the daily yields
    CSV (10 data points, ~2/19/26–3/6/26).  Once LSTM background training
    finishes, appends 3 future predicted data points.

    Raises ValueError if the yield CSV cannot be read or the fund row is
    missing — main.py will catch this and fall back to _synthetic_yield_forecast.
    """
    actuals = _parse_yield_series()
    if not actuals:
        raise ValueError(
            f"Yield series for '{_TARGET_FUND}' not found in {_YIELD_CSV.name}"
        )

    data: list[dict] = [
        {"time": ts_ms, "actual": round(pct, 3), "predicted": None, "anomaly": False}
        for ts_ms, pct in actuals
    ]

    with _cache_lock:
        preds = _predictions_cache

    if preds:
        last_ts = actuals[-1][0]
        day_ms = 86_400_000
        for i, val in enumerate(preds, start=1):
            data.append(
                {
                    "time": last_ts + i * day_ms,
                    "actual": None,
                    "predicted": round(float(val), 3),
                    "anomaly": False,
                }
            )

    return {"data": data}


# Start background training on module import (runs once even if module is
# reloaded, because _training_started is module-level state).
_start_training()
