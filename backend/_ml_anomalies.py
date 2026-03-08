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

# Redemption-specific thresholds (mirrors xrpl_client SELL_AMOUNT_RANGE = 25k–100k)
_RDM_AMOUNT_LO = 25_000
_RDM_AMOUNT_HI = 100_000
_RDM_LARGE_THRESHOLD = 150_000 # 1.5x normal ceiling → "Large Redemption"

# Burst detection: 4+ redemptions within a 2-minute window is unusual
_RDM_BURST_COUNT = 4
_RDM_BURST_WINDOW_SEC = 120


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


def _build_redemption_baseline(n: int = 300) -> np.ndarray:
    """Generate synthetic 'normal' redemption features.

    Normal redemptions (xrpl_client SELL_AMOUNT_RANGE):
        transfer_size  — 25k–100k tokens
        volume_rate    — 0.3–1.5 tx/min (less frequent than escrow)
        size_zscore    — drawn from N(0, 0.5) — tighter variance than escrows
    """
    rng = np.random.default_rng(99)
    transfer_sizes = rng.uniform(_RDM_AMOUNT_LO, _RDM_AMOUNT_HI, n)
    volume_rates   = rng.uniform(0.3, 1.5, n)
    size_zscores   = rng.normal(0.0, 0.5, n)
    return np.column_stack([transfer_sizes, volume_rates, size_zscores])


def _fit_redemption_model():
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    baseline = _build_redemption_baseline()
    scaler = StandardScaler()
    X = scaler.fit_transform(baseline)
    model = IsolationForest(contamination=_CONTAMINATION, random_state=99, n_estimators=100)
    model.fit(X)
    return scaler, model


try:
    _scaler, _model = _fit_model()
    _USE_ISOLATION_FOREST = True
    logger.info("IsolationForest anomaly model fitted on synthetic baseline.")
except Exception:
    logger.warning("scikit-learn unavailable — falling back to z-score anomaly detection.")
    _USE_ISOLATION_FOREST = False

try:
    _rdm_scaler, _rdm_model = _fit_redemption_model()
    _USE_RDM_MODEL = True
    logger.info("Redemption IsolationForest model fitted on synthetic baseline.")
except Exception:
    _USE_RDM_MODEL = False


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
# Redemption feature extraction
# ---------------------------------------------------------------------------

def _extract_redemption_features(
    events: list[dict],
) -> tuple[list[EventFeatures], list[dict], list[int]]:
    """Filter to RDM events and compute features + per-event burst counts.

    Returns (features, rdm_events, burst_counts).
    burst_counts[i] = number of redemptions within _RDM_BURST_WINDOW_SEC of event i.
    """
    rdm_events = [
        ev for ev in events
        if ev.get("direction") == "RDM" or ev.get("type") == "REDEMPTION"
    ]
    if not rdm_events:
        return [], [], []

    features = _extract_features(rdm_events)

    # Compute burst proximity using parsed timestamps
    timestamps_ms = [_event_timestamp_ms(ev, i) for i, ev in enumerate(rdm_events)]
    window_ms = _RDM_BURST_WINDOW_SEC * 1000
    burst_counts = [
        sum(1 for other_ts in timestamps_ms if abs(ts - other_ts) <= window_ms)
        for ts in timestamps_ms
    ]
    return features, rdm_events, burst_counts


# ---------------------------------------------------------------------------
# Classification — TODO(human): implement _classify_redemption
# ---------------------------------------------------------------------------

def _classify_redemption(
    amount: float,
    volume_rate: float,
    score: float,
    burst_count: int,
) -> tuple[str, str, str] | None:
    """Map redemption anomaly features to (alert_type, severity, description).

    Parameters
    ----------
    amount       : redemption token amount
    volume_rate  : transactions per minute in the current buffer window
    score        : IsolationForest decision score — more negative = more anomalous
    burst_count  : number of redemptions within _RDM_BURST_WINDOW_SEC of this event

    Returns
    -------
    (alert_type, severity, description) or None if the event is not anomalous.
        alert_type : "Large Redemption" | "Redemption Burst"
        severity   : "Critical" | "Warning"
        description: investor-facing sentence

    Guidance
    --------
    - Check `amount` against _RDM_LARGE_THRESHOLD for oversized redemptions
    - Check `burst_count` >= _RDM_BURST_COUNT for coordinated exit signals
    - Use `score` to escalate severity (more negative → Critical)
    - Return None for normal events (no alert)

    TODO(human): implement the classification logic below.
    """
    if amount > _RDM_LARGE_THRESHOLD:
        severity = "Critical" if score < -0.3 or amount > _RDM_LARGE_THRESHOLD * 2 else "Warning"
        return (
            "Large Redemption",
            severity,
            f"Redemption of {amount:,.0f} tokens is unusually large — "
            "monitor settlement queue for potential liquidity impact."
        )
    elif burst_count >= _RDM_BURST_COUNT:
        severity = "Critical" if score < -0.3 else "Warning"
        return (
            "Redemption Burst",
            severity,
            f"{burst_count} redemptions within 2 minutes is unusual — "
            "possible coordinated exit activity; monitor settlement queue closely."
        )
    return None


# ---------------------------------------------------------------------------
# Classification — existing general classifier
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
        severity = "Critical" if score < -0.3 or amount > _DEMO_AMOUNT_HI * 7 else "Warning"
        return (
            "Large Transfer",
            severity,
            f"Transfer of {amount:,.0f} tokens is unusually large — "
            "monitor settlement queue for potential delays or congestion."
        )
    elif volume_rate > 3.0:
        severity = "Critical" if score < -0.3 else "Warning"
        return (
            "Volume Spike",
            severity,
            f"Transaction volume {volume_rate:.1f} tx/min is unusually high — "
            "possible surge in investor activity or market response."
        )
    elif score < -0.4:
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
    seen_types: set[str] = set()

    for i, (feat, ev) in enumerate(zip(features, events)):
        z = abs((feat.transfer_size - mean) / std)
        if z > 2.5 and "Volume Spike" not in seen_types:
            seen_types.add("Volume Spike")
            alerts.append({
                "timestamp": _event_timestamp_ms(ev, i),
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
    Timestamps are anchored to today's UTC midnight so they are stable across
    polls and do not trigger the frontend dedup on every cycle.
    """
    import datetime
    today_midnight = int(datetime.datetime.combine(
        datetime.datetime.utcnow().date(),
        datetime.time.min,
        tzinfo=datetime.timezone.utc,
    ).timestamp())
    return [
        {
            "timestamp": (today_midnight + 19 * 3600) * 1000,  # 19:00 UTC today
            "type": "Settlement Delay",
            "severity": "Warning",
            "description": (
                "Escrow settlement latency 3.1σ above 24h average — "
                "possible Testnet congestion during peak window."
            ),
        },
        {
            "timestamp": (today_midnight + 14 * 3600) * 1000,  # 14:00 UTC today
            "type": "Redemption Burst",
            "severity": "Info",
            "description": (
                "4 redemptions within 90s window at 14:00 UTC — "
                "correlated with Treasury yield announcement; no liquidity impact."
            ),
        },
        {
            "timestamp": (today_midnight + 16 * 3600) * 1000,  # 16:00 UTC today
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

def _event_timestamp_ms(event: dict, fallback_index: int) -> int:
    """Derive a stable millisecond timestamp from an event's ``time`` field.

    Events carry ``time`` as ``"HH:MM:SS"`` (UTC).  We anchor it to today's
    UTC date so the value is deterministic across polls for the same event.
    If parsing fails, fall back to ``now - index * 60s``.
    """
    import datetime

    time_str = event.get("time", "")
    try:
        parts = time_str.split(":")
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        today = datetime.datetime.now(datetime.timezone.utc).date()
        dt = datetime.datetime(today.year, today.month, today.day, h, m, s,
                               tzinfo=datetime.timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return int((time.time() - fallback_index * 60) * 1000)


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
                "timestamp": _event_timestamp_ms(events[i], i),
                "type": alert_type,
                "severity": severity,
                "description": description,
            })

    elif features:
        live_alerts = _zscore_anomalies(features, events)

    # --- Redemption-specific detection (runs in addition to general model) ---
    # A large redemption may also appear as "Large Transfer" from the general model;
    # we allow both since they carry different type strings and provide richer context.
    rdm_features, rdm_events, burst_counts = _extract_redemption_features(events)

    if _USE_RDM_MODEL and rdm_features:
        X_rdm = _rdm_scaler.transform(np.array(rdm_features))
        rdm_scores = _rdm_model.decision_function(X_rdm)
        rdm_preds = _rdm_model.predict(X_rdm)
        rdm_seen: set[str] = set()

        for i, (pred, score) in enumerate(zip(rdm_preds, rdm_scores)):
            if len(live_alerts) >= 8:
                break
            # Flag if the model flags anomaly OR burst threshold is met independently
            is_model_anomaly = pred == -1
            is_burst = burst_counts[i] >= _RDM_BURST_COUNT
            if not is_model_anomaly and not is_burst:
                continue
            try:
                result = _classify_redemption(
                    rdm_features[i].transfer_size,
                    rdm_features[i].volume_rate,
                    float(score),
                    burst_counts[i],
                )
            except NotImplementedError:
                continue
            except Exception:
                continue
            if result is None:
                continue
            alert_type, severity, description = result
            if alert_type in rdm_seen:
                continue
            rdm_seen.add(alert_type)
            live_alerts.append({
                "timestamp": _event_timestamp_ms(rdm_events[i], i),
                "type": alert_type,
                "severity": severity,
                "description": description,
            })

    elif rdm_features:
        # z-score fallback for redemptions when sklearn is unavailable
        rdm_sizes = np.array([f.transfer_size for f in rdm_features])
        if len(rdm_sizes) >= 2:
            mean, std = rdm_sizes.mean(), max(rdm_sizes.std(), 1.0)
            rdm_seen_fb: set[str] = set()
            for i, feat in enumerate(rdm_features):
                z = abs((feat.transfer_size - mean) / std)
                if z > 2.5 and "Large Redemption" not in rdm_seen_fb:
                    rdm_seen_fb.add("Large Redemption")
                    live_alerts.append({
                        "timestamp": _event_timestamp_ms(rdm_events[i], i),
                        "type": "Large Redemption",
                        "severity": "Critical" if z > 3.5 else "Warning",
                        "description": (
                            f"Redemption of {feat.transfer_size:,.0f} tokens is "
                            f"{z:.1f}σ above rolling mean — unusual outflow activity."
                        ),
                    })

    return live_alerts + _baseline_alerts()
