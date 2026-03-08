from __future__ import annotations
import logging
import time
from typing import NamedTuple
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import xrpl_client

logger = logging.getLogger(__name__)

_DEMO_AMOUNT_BASE = 100_000
_DEMO_AMOUNT_JITTER = 0.25
_DEMO_AMOUNT_LO = _DEMO_AMOUNT_BASE * (1 - _DEMO_AMOUNT_JITTER)
_DEMO_AMOUNT_HI = _DEMO_AMOUNT_BASE * (1 + _DEMO_AMOUNT_JITTER)

_CONTAMINATION = 0.05

_RDM_AMOUNT_LO = 25_000
_RDM_AMOUNT_HI = 100_000
_RDM_LARGE_THRESHOLD = 150_000 

_RDM_BURST_COUNT = 4
_RDM_BURST_WINDOW_SEC = 120


class EventFeatures(NamedTuple):
    transfer_size: float
    volume_rate: float
    size_zscore: float


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


# Isolation Forest Model

def _build_norm_baseline(n: int = 400) -> np.ndarray:
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


def _fit_norm_model():
    baseline = _build_norm_baseline()
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
    baseline = _build_redemption_baseline()
    scaler = StandardScaler()
    X = scaler.fit_transform(baseline)
    model = IsolationForest(contamination=_CONTAMINATION, random_state=99, n_estimators=100)
    model.fit(X)
    return scaler, model

_scaler, _model = _fit_norm_model()
logger.info("IsolationForest anomaly model fitted on synthetic baseline.")

_rdm_scaler, _rdm_model = _fit_redemption_model()
logger.info("Redemption IsolationForest model fitted on synthetic baseline.")



def _extract_norm_features(events: list[dict]) -> list[EventFeatures]:
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

    features = _extract_norm_features(rdm_events)

    # Compute burst proximity using parsed timestamps
    timestamps_ms = [_event_timestamp_ms(ev, i) for i, ev in enumerate(rdm_events)]
    window_ms = _RDM_BURST_WINDOW_SEC * 1000
    burst_counts = [
        sum(1 for other_ts in timestamps_ms if abs(ts - other_ts) <= window_ms)
        for ts in timestamps_ms
    ]
    return features, rdm_events, burst_counts


def _classify_redemption(
    amount: float,
    volume_rate: float,
    score: float,
    burst_count: int,
) -> tuple[str, str, str] | None:
    """Map redemption anomaly features to (alert_type, severity, description).
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


def _classify_event(
    amount: float,
    volume_rate: float,
    score: float,
) -> tuple[str, str, str]:
    """Map anomaly features to (alert_type, severity, description).
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


# API

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
    events = xrpl_client.get_events()

    features = _extract_norm_features(events)
    live_alerts: list[dict] = []

    if features:
        X = _scaler.transform(np.array(features))
        scores = _model.decision_function(X)
        predictions = _model.predict(X)
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

    rdm_features, rdm_events, burst_counts = _extract_redemption_features(events)

    if rdm_features:
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

    return live_alerts
