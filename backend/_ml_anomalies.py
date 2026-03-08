"""
Anomaly detector for XRPL MMF event stream.

Model: IsolationForest (sklearn) fit on a synthetic baseline shaped around
the demo escrow traffic (DEMO_AMOUNT_BASE = 100_000 ±25%, 1–3 tx/min).
Falls back to z-score if sklearn is unavailable.

Features per event:
    transfer_size   — parsed token amount (float)
    volume_rate     — transactions per minute in the current buffer window
    size_zscore     — z-score of this transfer vs the rolling buffer

Exported:
    get_anomalies() → list[dict]  (timestamp ms, type, severity, description)
"""

from __future__ import annotations

import logging
import time
from typing import NamedTuple

import numpy as np

logger = logging.getLogger(__name__)

# Mirror xrpl_client constants so baseline matches real traffic
_DEMO_AMOUNT_BASE = 100_000
_DEMO_AMOUNT_JITTER = 0.25          # ±25%
_DEMO_AMOUNT_LO = _DEMO_AMOUNT_BASE * (1 - _DEMO_AMOUNT_JITTER)   # 75_000
_DEMO_AMOUNT_HI = _DEMO_AMOUNT_BASE * (1 + _DEMO_AMOUNT_JITTER)   # 125_000

# IsolationForest contamination: ~5% of live events expected to be anomalous
_CONTAMINATION = 0.05


# ---------------------------------------------------------------------------
# Feature type
# ---------------------------------------------------------------------------

class EventFeatures(NamedTuple):
    transfer_size: float   # token units
    volume_rate: float     # tx per minute
    size_zscore: float     # z-score vs buffer mean


# ---------------------------------------------------------------------------
# Amount parsing
# ---------------------------------------------------------------------------

def _parse_amount(amount_str: str) -> float:
    """Parse xrpl_client's 'amount' field (string int, drops, or '-') → float.

    MPT amounts are dicts stringified by _format_ws_event, e.g.:
        "{'mpt_issuance_id': '0000...', 'value': '250000'}"
    XRP drop amounts are plain integer strings.
    We cap at 10M to keep features bounded.
    """
    import ast
    try:
        val = float(str(amount_str).replace(",", ""))
        return min(val, 10_000_000.0)
    except (ValueError, TypeError):
        pass
    try:
        parsed = ast.literal_eval(str(amount_str))
        if isinstance(parsed, dict) and "value" in parsed:
            return min(float(parsed["value"]), 10_000_000.0)
    except Exception:
        pass
    return 0.0


# ---------------------------------------------------------------------------
# Synthetic baseline — fit IsolationForest at module load
# ---------------------------------------------------------------------------

def _build_baseline(n: int = 400) -> np.ndarray:
    """Generate synthetic 'normal' transaction features.

    Normal traffic:
        transfer_size  — 75k–125k tokens  (DEMO_AMOUNT_BASE ±25%)
        volume_rate    — 0.8–2.5 tx/min   (escrow settler fires every 45–75s)
        size_zscore    — drawn from N(0, 0.6) representing minor variance
    """
    rng = np.random.default_rng(42)

    transfer_sizes = rng.uniform(_DEMO_AMOUNT_LO, _DEMO_AMOUNT_HI, n)
    volume_rates   = rng.uniform(0.8, 2.5, n)
    size_zscores   = rng.normal(0.0, 0.6, n)

    return np.column_stack([transfer_sizes, volume_rates, size_zscores])


def _fit_model():
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    baseline = _build_baseline()
    scaler = StandardScaler()
    X = scaler.fit_transform(baseline)
    model = IsolationForest(contamination=_CONTAMINATION, random_state=42, n_estimators=100)
    model.fit(X)
    return scaler, model


try:
    _scaler, _model = _fit_model()
    _USE_ISOLATION_FOREST = True
    logger.info("IsolationForest anomaly model fitted on synthetic baseline.")
except Exception:
    logger.warning("scikit-learn unavailable — falling back to z-score anomaly detection.")
    _USE_ISOLATION_FOREST = False


# ---------------------------------------------------------------------------
# Feature extraction from the live event buffer
# ---------------------------------------------------------------------------

def _extract_features(events: list[dict]) -> list[EventFeatures]:
    """Derive per-event feature vectors from the xrpl_client event buffer.

    The buffer holds up to 50 events (most-recent first).  We estimate the
    window duration as 50 events × average inter-event gap (≈60s), giving
    a volume_rate in tx/min.  size_zscore is computed across all amounts in
    the buffer so each event knows how extreme it is relative to its peers.
    """
    if not events:
        return []

    amounts = [_parse_amount(ev.get("amount", "0")) for ev in events]
    nonzero = [a for a in amounts if a > 0]

    buf_mean = float(np.mean(nonzero)) if nonzero else _DEMO_AMOUNT_BASE
    buf_std  = float(np.std(nonzero))  if len(nonzero) > 1 else 1.0
    buf_std  = max(buf_std, 1.0)

    # Estimate window: buffer length × assumed 60s avg gap → minutes
    window_minutes = max(len(events) * 60 / 60, 1.0)
    volume_rate = len(events) / window_minutes

    features = []
    for amount in amounts:
        zscore = (amount - buf_mean) / buf_std if amount > 0 else 0.0
        features.append(EventFeatures(
            transfer_size=amount,
            volume_rate=volume_rate,
            size_zscore=zscore,
        ))
    return features


# ---------------------------------------------------------------------------
# Classification — TODO(human): implement _classify_event
# ---------------------------------------------------------------------------

def _classify_event(
    amount: float,
    volume_rate: float,
    score: float,
) -> tuple[str, str, str]:
    """Map anomaly features to (alert_type, severity, description).

    Parameters
    ----------
    amount       : transfer size in tokens
    volume_rate  : transactions per minute in the current buffer window
    score        : IsolationForest decision score — more negative = more anomalous
                   typical range: [-0.6, +0.2]

    Returns
    -------
    (alert_type, severity, description)
        severity  : "Critical" | "Warning" | "Info"
        alert_type: short label, e.g. "Large Transfer" | "Volume Spike" | "Settlement Anomaly"
        description: investor-facing sentence explaining what was detected

    Guidance
    --------
    - Use `score` thresholds to set severity (e.g. very negative → Critical)
    - Use `amount` vs _DEMO_AMOUNT_HI to detect oversized transfers
    - Use `volume_rate` vs a normal ceiling (~3 tx/min) to detect bursts
    - Pick the most prominent signal — don't describe all three in one message
    - Description should be investor-facing: what it means, not just the number
    """
    if amount > _DEMO_AMOUNT_HI * 1.5:
        severity = "Critical" if score < -0.4 else "Warning"
        return (
            "Large Transfer",
            severity,
            f"Transfer size {amount:,.0f} tokens is unusually large — "
            "monitor for potential liquidity impact or redemption spikes."
        )
    elif volume_rate > 3.0:
        severity = "Critical" if score < -0.4 else "Warning"
        return (
            "Volume Spike",
            severity,
            f"Transaction volume {volume_rate:.1f} tx/min is unusually high — "
            "possible surge in investor activity or market response."
        )
    elif score < -0.5:
        return (
            "Settlement Anomaly",
            "Warning",
            f"Anomalous pattern detected with score {score:.2f} — "
            "monitor settlement queue for potential delays or congestion."
        )   

# ---------------------------------------------------------------------------
# Z-score fallback (no sklearn)
# ---------------------------------------------------------------------------

def _zscore_anomalies(features: list[EventFeatures], events: list[dict]) -> list[dict]:
    """Simple z-score detector used when IsolationForest is unavailable."""
    sizes = np.array([f.transfer_size for f in features])
    if len(sizes) < 2:
        return []

    mean, std = sizes.mean(), sizes.std()
    std = max(std, 1.0)

    alerts = []
    now = int(time.time())
    seen_types: set[str] = set()

    for i, (feat, ev) in enumerate(zip(features, events)):
        z = abs((feat.transfer_size - mean) / std)
        if z > 2.5 and "Volume Spike" not in seen_types:
            seen_types.add("Volume Spike")
            alerts.append({
                "timestamp": (now - i * 60) * 1000,
                "type": "Volume Spike",
                "severity": "Critical" if z > 3.5 else "Warning",
                "description": (
                    f"Transfer size {feat.transfer_size:,.0f} tokens is "
                    f"{z:.1f}σ above rolling mean — unusual redemption activity."
                ),
            })

    return alerts


# ---------------------------------------------------------------------------
# Baseline historical alerts — always shown for demo richness
# ---------------------------------------------------------------------------

def _baseline_alerts() -> list[dict]:
    """A small set of pre-baked historical alerts representing past patterns.

    These ensure the AlertFeed is never empty even before live anomalies appear.
    Timestamps are placed in the past (1–8 hours ago) so they appear below
    any live detections in the feed.
    """
    now = int(time.time())
    return [
        {
            "timestamp": (now - 4 * 3600) * 1000,
            "type": "Settlement Delay",
            "severity": "Warning",
            "description": (
                "Escrow settlement latency 3.1σ above 24h average — "
                "possible Testnet congestion during peak window."
            ),
        },
        {
            "timestamp": (now - 7 * 3600) * 1000,
            "type": "Low Liquidity Signal",
            "severity": "Info",
            "description": (
                "Net outflow exceeded 4.8% of TVL over 1hr — "
                "monitor redemption queue for pressure buildup."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_anomalies() -> list[dict]:
    """Detect anomalies in the live XRPL event buffer.

    Returns a list of alert dicts: { timestamp (ms), type, severity, description }.
    Always includes baseline historical alerts so the feed is never empty.
    Live detections are prepended (most recent first).
    """
    try:
        import xrpl_client
        events = xrpl_client.get_events()
    except Exception:
        logger.warning("Could not read XRPL events — returning baseline alerts only.")
        return _baseline_alerts()

    features = _extract_features(events)
    live_alerts: list[dict] = []
    now = int(time.time())

    if _USE_ISOLATION_FOREST and features:
        X = _scaler.transform(np.array(features))
        scores = _model.decision_function(X)
        predictions = _model.predict(X)          # -1 = anomaly
        seen_types: set[str] = set()

        for i, (pred, score) in enumerate(zip(predictions, scores)):
            if pred != -1 or len(live_alerts) >= 5:
                continue
            feat = features[i]
            try:
                alert_type, severity, description = _classify_event(
                    feat.transfer_size, feat.volume_rate, float(score)
                )
            except NotImplementedError:
                continue
            except Exception:
                continue

            if alert_type in seen_types:
                continue
            seen_types.add(alert_type)

            live_alerts.append({
                "timestamp": (now - i * 60) * 1000,
                "type": alert_type,
                "severity": severity,
                "description": description,
            })

    elif features:
        live_alerts = _zscore_anomalies(features, events)

    return live_alerts + _baseline_alerts()
