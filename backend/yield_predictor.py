"""
U.S. Treasury tokenized yield predictor (24–72hr forward).

This module predicts U.S. Treasury tokenized yield 24–72 hours ahead for display
as an overlay on YieldChart. It uses a Ridge regression baseline with features
built from historical yield and optional TVL/transfer data.

Data sources
------------
- **rwa.xyz CSV**: Yield (APY/YTM) time series for treasury tokens. Download
  from app.rwa.xyz/downloads (e.g. Treasury Time Series).
- **rwapipe.com**: Transfer and TVL (total value locked) history for treasury
  tokens. Can be exported to CSV or fetched via API; this code expects CSV
  with date, tvl, and optional transfer_volume. For live snapshots use the
  RWA Pipe API client in rwapipe_client.py:
  - GET https://rwapipe.com/api/market  → all tokens (tvlUsd, change7d, netFlow*).
  - GET https://rwapipe.com/api/tokens/<address>  → one token (yield, TVL, etc.).

Model (baseline)
----------------
- **Features**: lag-1 yield, lag-7 yield, TVL delta (day-over-day change),
  transfer volume.
- **Target**: Next-day yield.
- **Pipeline**: StandardScaler (zero mean, unit variance) + Ridge regression.

Usage
-----
  # From command line (CSV paths):
  python yield_predictor.py yield_data.csv [tvl_transfer.csv]

  # From code:
  from yield_predictor import run_from_csv
  model, metrics, preds_24_72 = run_from_csv("yield_data.csv", "tvl.csv")
  # preds_24_72 has columns: date, yield_pred, horizon_hr (24, 48, 72)
"""

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline


# ---------------------------------------------------------------------------
# Data loading (rwa.xyz CSV yield + rwapipe TVL/transfer history)
# ---------------------------------------------------------------------------

def load_yield_csv(path: str) -> pd.DataFrame:
    """
    Load a yield time-series CSV (e.g. from rwa.xyz exports).

    Automatically detects date and yield columns by common names so you don't
    have to rename columns. Only the date and yield columns are kept; other
    columns (e.g. token id) are dropped.

    Parameters
    ----------
    path : str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Two columns: "date" (datetime, sorted) and "yield" (float).
        Rows with missing date or yield are dropped.

    Raises
    ------
    ValueError
        If no column looks like a yield metric (yield, apy, yield_pct, ytm).

    Notes
    -----
    Accepted date-like column names: date, timestamp, time.
    Accepted yield-like column names: yield, apy, yield_pct, ytm.
    """
    df = pd.read_csv(path)
    # Normalize common column names so rest of code can assume "date" and "yield"
    date_col = next((c for c in df.columns if c.lower() in ("date", "timestamp", "time")), df.columns[0])
    yield_col = next((c for c in df.columns if c.lower() in ("yield", "apy", "yield_pct", "ytm")), None)
    if yield_col is None:
        raise ValueError(f"Yield column not found. Columns: {list(df.columns)}")
    df = df.rename(columns={date_col: "date", yield_col: "yield"})
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "yield"]].sort_values("date").dropna()


def load_tvl_transfer_csv(path: str) -> pd.DataFrame:
    """
    Load a TVL and transfer-volume history CSV (e.g. from rwapipe.com exports).

    TVL (total value locked) and transfer volume are used as features. Column
    names are auto-detected; if no transfer/volume column exists, transfer_volume
    is set to 0.0 for all rows.

    Parameters
    ----------
    path : str
        Path to the CSV file.

    Returns
    -------
    pd.DataFrame
        Three columns: "date" (datetime), "tvl" (float), "transfer_volume" (float).
        Sorted by date; rows with missing TVL are dropped.

    Raises
    ------
    ValueError
        If no column looks like TVL (tvl, total_value_locked).

    Notes
    -----
    Accepted TVL column names: tvl, total_value_locked.
    Accepted volume column names: transfer_volume, transfers, volume.
    """
    df = pd.read_csv(path)
    date_col = next((c for c in df.columns if c.lower() in ("date", "timestamp", "time")), df.columns[0])
    tvl_col = next((c for c in df.columns if c.lower() in ("tvl", "total_value_locked")), None)
    vol_col = next((c for c in df.columns if c.lower() in ("transfer_volume", "transfers", "volume")), None)
    if tvl_col is None:
        raise ValueError(f"TVL column not found. Columns: {list(df.columns)}")
    rename = {date_col: "date", tvl_col: "tvl"}
    if vol_col:
        rename[vol_col] = "transfer_volume"
    df = df.rename(columns=rename)
    df["date"] = pd.to_datetime(df["date"])
    if "transfer_volume" not in df.columns:
        df["transfer_volume"] = 0.0
    return df[["date", "tvl", "transfer_volume"]].sort_values("date").dropna(subset=["tvl"])


def merge_yield_and_tvl(
    yield_df: pd.DataFrame,
    tvl_df: pd.DataFrame,
    freq: str = "D",
) -> pd.DataFrame:
    """
    Combine yield and TVL/transfer DataFrames on a common daily time index.

    Both inputs are resampled to the given frequency (default daily). Only dates
    that appear in both datasets are kept (inner join), so you get one row per
    date with yield, tvl, and transfer_volume.

    Parameters
    ----------
    yield_df : pd.DataFrame
        Must have columns "date" and "yield" (e.g. from load_yield_csv).
    tvl_df : pd.DataFrame
        Must have columns "date", "tvl", "transfer_volume" (e.g. from load_tvl_transfer_csv).
    freq : str, optional
        Pandas resample rule; default "D" (calendar day).

    Returns
    -------
    pd.DataFrame
        Columns: date, yield, tvl, transfer_volume. One row per resampled period.
    """
    yield_df = yield_df.set_index("date").resample(freq).mean().dropna(how="all")
    tvl_df = tvl_df.set_index("date").resample(freq).sum()
    # If multiple rows per day: use last TVL, sum transfer volume
    tvl_df = tvl_df.resample(freq).agg({"tvl": "last", "transfer_volume": "sum"})
    merged = yield_df.join(tvl_df, how="inner")
    return merged.reset_index()


# ---------------------------------------------------------------------------
# Features: lag-1 yield, lag-7 yield, TVL delta, transfer volume
# Target: next-day yield
# ---------------------------------------------------------------------------

def build_features_and_target(
    df: pd.DataFrame,
    target_horizon_days: int = 1,
) -> tuple[np.ndarray, np.ndarray, pd.DatetimeIndex]:
    """
    Build the feature matrix (X) and target vector (y) for training the model.

    Each row of X corresponds to one day. The target for that row is the yield
    N days later (default 1 = next-day yield). Rows with missing values after
    computing lags are dropped (e.g. first 7 rows have no yield_lag7).

    Feature definitions
    -------------------
    - yield_lag1 : yield from the previous day (short-term momentum).
    - yield_lag7 : yield from 7 days ago (weekly trend).
    - tvl_delta : change in TVL from previous day (df["tvl"].diff(1)).
    - transfer_volume : raw transfer volume for that day (activity level).

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: date, yield, tvl, transfer_volume (from merge_yield_and_tvl or equivalent).
    target_horizon_days : int, optional
        How many days ahead to predict; default 1 (next-day yield).

    Returns
    -------
    X : np.ndarray
        Shape (n_samples, 4). Each row is [yield_lag1, yield_lag7, tvl_delta, transfer_volume].
    y : np.ndarray
        Shape (n_samples,). Target yield at t + target_horizon_days.
    dates : pd.DatetimeIndex
        Date for each row of X/y (same length as n_samples).
    """
    df = df.copy()
    df["yield_lag1"] = df["yield"].shift(1)
    df["yield_lag7"] = df["yield"].shift(7)
    df["tvl_delta"] = df["tvl"].diff(1)
    if "transfer_volume" not in df.columns:
        df["transfer_volume"] = 0.0
    df["target"] = df["yield"].shift(-target_horizon_days)
    feature_cols = ["yield_lag1", "yield_lag7", "tvl_delta", "transfer_volume"]
    for c in feature_cols:
        if c not in df.columns:
            df[c] = 0.0
    use = df[feature_cols + ["target"]].dropna()
    dates = df.loc[use.index, "date"]
    X = use[feature_cols].values
    y = use["target"].values
    return X, y, dates


# ---------------------------------------------------------------------------
# Model: Ridge + StandardScaler (baseline)
# ---------------------------------------------------------------------------

def build_model(alpha: float = 1.0) -> Pipeline:
    """
    Create the baseline model pipeline: scale features, then Ridge regression.

    StandardScaler centers each feature to mean 0 and scales to unit variance,
    which helps Ridge behave well when features have different units (e.g. yield
    in percent vs. TVL in dollars). Ridge adds L2 regularization to avoid
    overfitting.

    Parameters
    ----------
    alpha : float, optional
        Ridge regularization strength; larger = more regularization. Default 1.0.

    Returns
    -------
    sklearn.pipeline.Pipeline
        Two steps: "scaler" (StandardScaler), "ridge" (Ridge).
    """
    return Pipeline([
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=alpha)),
    ])


def train_predictor(
    X: np.ndarray,
    y: np.ndarray,
    alpha: float = 1.0,
) -> Pipeline:
    """
    Fit the baseline model on feature matrix X and target vector y.

    The pipeline is fit in one go: StandardScaler learns mean/std from X, then
    Ridge is fit on the scaled X and y. Use this fitted pipeline with predict()
    for new data (the scaler will use the training statistics).

    Parameters
    ----------
    X : np.ndarray
        Feature matrix, shape (n_samples, 4). Columns: yield_lag1, yield_lag7, tvl_delta, transfer_volume.
    y : np.ndarray
        Target vector, shape (n_samples,). Next-day (or horizon) yield.
    alpha : float, optional
        Ridge alpha; passed to build_model.

    Returns
    -------
    sklearn.pipeline.Pipeline
        Fitted pipeline (scaler + ridge), ready for model.predict(X_new).
    """
    model = build_model(alpha=alpha)
    model.fit(X, y)
    return model


# ---------------------------------------------------------------------------
# 24–72hr predictions for YieldChart overlay
# ---------------------------------------------------------------------------

def predict_forward(
    model: Pipeline,
    df: pd.DataFrame,
    horizon_days: int = 1,
) -> pd.DataFrame:
    """
    Produce a single yield prediction N days ahead from the latest row in df.

    Features are built from the last row (yield_lag1, yield_lag7, tvl_delta,
    transfer_volume). The model predicts one number; the returned "date" is
    last date in df plus horizon_days (for labeling on the chart). The model
    itself is trained for next-day yield, so 48h/72h here use the same
    next-day prediction but labeled at 2 and 3 days ahead.

    Parameters
    ----------
    model : Pipeline
        Fitted pipeline from train_predictor (StandardScaler + Ridge).
    df : pd.DataFrame
        Merged data with date, yield, tvl, transfer_volume (same format as used for training).
    horizon_days : int, optional
        Label the prediction as this many days after the last date; default 1.

    Returns
    -------
    pd.DataFrame
        One row: columns "date" (prediction date), "yield_pred" (predicted yield).
    """
    df = df.copy()
    df["yield_lag1"] = df["yield"].shift(1)
    df["yield_lag7"] = df["yield"].shift(7)
    df["tvl_delta"] = df["tvl"].diff(1)
    if "transfer_volume" not in df.columns:
        df["transfer_volume"] = 0.0
    feature_cols = ["yield_lag1", "yield_lag7", "tvl_delta", "transfer_volume"]
    last = df[feature_cols].iloc[-1:].fillna(0)
    pred = model.predict(last.values)[0]
    last_date = df["date"].iloc[-1]
    from pandas.tseries.offsets import Day
    pred_date = last_date + Day(horizon_days)
    return pd.DataFrame({"date": [pred_date], "yield_pred": [pred]})


def get_predictions_24_72hr(
    model: Pipeline,
    df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build 24h, 48h, and 72h ahead yield predictions for YieldChart overlay.

    Calls predict_forward for horizon_days 1, 2, and 3 and stacks the results.
    Each row has the prediction date, predicted yield, and horizon_hr (24, 48, 72)
    so the chart can plot all three points or show a range.

    Parameters
    ----------
    model : Pipeline
        Fitted pipeline from train_predictor.
    df : pd.DataFrame
        Merged data (date, yield, tvl, transfer_volume) up to the latest date.

    Returns
    -------
    pd.DataFrame
        Three rows. Columns: date, yield_pred, horizon_hr (24, 48, 72).
    """
    rows = []
    for days in (1, 2, 3):
        pred_df = predict_forward(model, df, horizon_days=days)
        pred_df["horizon_hr"] = 24 * days
        rows.append(pred_df)
    return pd.concat(rows, ignore_index=True)


# ---------------------------------------------------------------------------
# End-to-end: load CSVs → train → return predictions
# ---------------------------------------------------------------------------

def run_from_csv(
    yield_csv_path: str,
    tvl_csv_path: Optional[str] = None,
    alpha: float = 1.0,
    target_horizon_days: int = 1,
) -> tuple[Pipeline, pd.DataFrame, pd.DataFrame]:
    """
    Run the full pipeline: load CSVs, build features, train model, return predictions.

    This is the main entry point when you have a yield CSV and optionally a
    TVL/transfer CSV. If tvl_csv_path is missing or the file doesn't exist,
    TVL and transfer_volume are set to 0 (model uses only yield lags).

    Parameters
    ----------
    yield_csv_path : str
        Path to rwa.xyz-style yield CSV (date + yield columns).
    tvl_csv_path : str or None, optional
        Path to rwapipe-style TVL/transfer CSV. If None or missing file, TVL/volume set to 0.
    alpha : float, optional
        Ridge regularization strength; default 1.0.
    target_horizon_days : int, optional
        Training target: yield this many days ahead; default 1 (next-day).

    Returns
    -------
    model : Pipeline
        Fitted StandardScaler + Ridge pipeline.
    metrics : pd.DataFrame
        In-sample results: columns date, yield_actual, yield_pred (for sanity checks).
    preds_24_72 : pd.DataFrame
        Out-of-sample 24/48/72h predictions: date, yield_pred, horizon_hr (for YieldChart overlay).

    Raises
    ------
    ValueError
        If there are fewer than 10 samples after building lags (need enough history).
    """
    yield_df = load_yield_csv(yield_csv_path)
    if tvl_csv_path and Path(tvl_csv_path).exists():
        tvl_df = load_tvl_transfer_csv(tvl_csv_path)
        df = merge_yield_and_tvl(yield_df, tvl_df)
    else:
        df = yield_df.copy()
        df["tvl"] = 0.0
        df["transfer_volume"] = 0.0

    X, y, dates = build_features_and_target(df, target_horizon_days=target_horizon_days)
    if len(X) < 10:
        raise ValueError("Not enough samples after building lags (need at least 10).")

    model = train_predictor(X, y, alpha=alpha)
    preds_24_72 = get_predictions_24_72hr(model, df)

    y_pred_train = model.predict(X)
    metrics = pd.DataFrame({
        "date": dates,
        "yield_actual": y,
        "yield_pred": y_pred_train,
    })

    return model, metrics, preds_24_72


def main():
    """
    Command-line entry point: run predictor from CSV paths and print results.

    Expects one or two CSV paths (yield required, TVL optional). If the yield
    file doesn't exist, prints usage and example. Otherwise trains the model
    and prints 24–72hr predictions plus the last 5 in-sample rows.
    """
    import sys
    # Default paths when run with no args; second arg is optional TVL CSV
    yield_path = sys.argv[1] if len(sys.argv) > 1 else "yield_data.csv"
    tvl_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not Path(yield_path).exists():
        print("Usage: python yield_predictor.py <yield_csv> [tvl_transfer_csv]")
        print("  yield_csv: rwa.xyz-style CSV with date + yield (apy) columns")
        print("  tvl_transfer_csv: rwapipe-style CSV with date, tvl, transfer_volume")
        print("Example (no TVL): create yield_data.csv with columns: date,yield")
        return

    model, metrics, preds = run_from_csv(yield_path, tvl_csv_path=tvl_path)
    print("24–72hr yield predictions (for YieldChart overlay):")
    print(preds.to_string(index=False))
    print("\nLast 5 training rows (actual vs predicted):")
    print(metrics.tail().to_string(index=False))


if __name__ == "__main__":
    main()
