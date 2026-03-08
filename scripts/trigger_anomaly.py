"""
Demo trigger: inject anomalous XRPL transactions to fire the AlertFeed.

Reads backend/state.json for wallet seeds and MPT issuance ID, then sends
transactions that the IsolationForest will flag as anomalous.

Usage
-----
    # From repo root, with the backend .venv active:
    python scripts/trigger_anomaly.py --type large
    python scripts/trigger_anomaly.py --type burst
    python scripts/trigger_anomaly.py --type subscribe

Modes
-----
    large      — one transfer of 250,000 tokens (2× normal ceiling of 125k)
                 subscriber → fund; triggers "Large Transfer" alert; appears as REDEMPTION
    burst      — 6 rapid transfers of 100,000 tokens each (~10s apart)
                 subscriber → fund; activity spike in the event buffer; appears as REDEMPTION
    subscribe  — one fund → subscriber payment of 100,000 tokens
                 fund delivering tokens to investor; appears as SUBSCRIPTION in EventStream
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Resolve backend/ relative to this script's location
REPO_ROOT = Path(__file__).parent.parent
STATE_FILE = REPO_ROOT / "backend" / "state.json"

TESTNET_URL = "https://s.altnet.rippletest.net:51234"
RIPPLE_EPOCH = 946684800

LARGE_TRANSFER_AMOUNT     = 250_000   # 2× normal ceiling — triggers "Large Transfer"
BURST_AMOUNT              = 100_000   # normal size, just sent many times quickly
BURST_COUNT               = 6
BURST_DELAY_SECONDS       = 8         # gap between burst transfers
SUBSCRIBE_AMOUNT          = 100_000   # fund → subscriber, simulates token issuance/subscription


def load_state() -> dict:
    if not STATE_FILE.exists():
        print(f"ERROR: {STATE_FILE} not found. Start the backend first to generate state.")
        sys.exit(1)
    return json.loads(STATE_FILE.read_text())


def send_mpt_transfer(
    client,
    sender_wallet,
    destination_address: str,
    mpt_issuance_id: str,
    amount: int,
    label: str,
) -> str:
    """Submit an MPT Payment and return the transaction hash."""
    from xrpl.models.transactions import Payment
    from xrpl.transaction import submit_and_wait

    tx = Payment(
        account=sender_wallet.classic_address,
        destination=destination_address,
        amount={
            "mpt_issuance_id": mpt_issuance_id,
            "value": str(amount),
        },
    )
    result = submit_and_wait(tx, client, sender_wallet)
    tx_hash = result.result.get("hash", "unknown")[:16]
    print(f"  [{label}] {amount:>10,} tokens  →  hash {tx_hash}  ✓")
    return tx_hash


def trigger_large(state: dict) -> None:
    """Send one oversized transfer to trigger 'Large Transfer' alert.

    Sends subscriber → fund wallet (investor returning tokens = redemption).
    Appears as REDEMPTION ↓ in the EventStream panel.
    """
    from xrpl.clients import JsonRpcClient
    from xrpl.wallet import Wallet

    print(f"\nTriggering LARGE TRANSFER ({LARGE_TRANSFER_AMOUNT:,} tokens)...")
    client = JsonRpcClient(TESTNET_URL)
    subscriber_wallet = Wallet.from_seed(state["subscriber_seed"])
    fund_address = state.get("fund_address") or Wallet.from_seed(state["wallet_seed"]).classic_address
    mpt_id = state["mpt_issuance_id"]

    send_mpt_transfer(
        client, subscriber_wallet, fund_address, mpt_id,
        LARGE_TRANSFER_AMOUNT, "LARGE"
    )
    print("\nDone. Wait ~5s for the AlertFeed to poll /api/ml/anomalies.")
    print("Expected alert: 'Large Transfer' — Critical or Warning severity.")


def trigger_burst(state: dict) -> None:
    """Send several normal-sized transfers in quick succession."""
    from xrpl.clients import JsonRpcClient
    from xrpl.wallet import Wallet

    print(f"\nTriggering BURST ({BURST_COUNT} transfers × {BURST_AMOUNT:,} tokens, {BURST_DELAY_SECONDS}s apart)...")
    client = JsonRpcClient(TESTNET_URL)
    subscriber_wallet = Wallet.from_seed(state["subscriber_seed"])
    fund_address = state.get("fund_address") or Wallet.from_seed(state["wallet_seed"]).classic_address
    mpt_id = state["mpt_issuance_id"]

    for i in range(BURST_COUNT):
        send_mpt_transfer(
            client, subscriber_wallet, fund_address, mpt_id,
            BURST_AMOUNT, f"BURST {i + 1}/{BURST_COUNT}"
        )
        if i < BURST_COUNT - 1:
            time.sleep(BURST_DELAY_SECONDS)

    print("\nDone. The event buffer now contains a dense cluster of recent transfers.")
    print("Check the EventStream panel for live activity.")


def trigger_subscribe(state: dict) -> None:
    """Send one fund → subscriber payment to simulate MMF token subscription issuance.

    This is the fund distributing newly-subscribed tokens to an investor.
    Appears as REDEMPTION in EventStream (fund paying tokens OUT to subscriber).
    """
    from xrpl.clients import JsonRpcClient
    from xrpl.wallet import Wallet

    print(f"\nTriggering SUBSCRIBE ({SUBSCRIBE_AMOUNT:,} tokens fund → subscriber)...")
    client = JsonRpcClient(TESTNET_URL)
    fund_wallet = Wallet.from_seed(state["wallet_seed"])
    subscriber_address = Wallet.from_seed(state["subscriber_seed"]).classic_address
    mpt_id = state["mpt_issuance_id"]

    send_mpt_transfer(
        client, fund_wallet, subscriber_address, mpt_id,
        SUBSCRIBE_AMOUNT, "SUBSCRIBE"
    )
    print("\nDone. Check the EventStream panel — should appear as SUBSCRIPTION ↑ (fund delivering tokens to investor).")
    print("Use --type large or --type burst to show REDEMPTION ↓ (investor returning tokens to fund).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Trigger MMF Terminal demo anomalies")
    parser.add_argument(
        "--type",
        choices=["large", "burst", "subscribe"],
        default="large",
        help=(
            "large: single oversized transfer (subscriber→fund, shows as SUBSCRIPTION) | "
            "burst: rapid succession of transfers (subscriber→fund, shows as SUBSCRIPTION) | "
            "subscribe: single fund→subscriber payment (shows as REDEMPTION)"
        ),
    )
    args = parser.parse_args()

    state = load_state()
    print(f"Loaded state.json — fund wallet: {state.get('wallet_seed', '?')[:8]}...")
    print(f"MPT issuance ID: {state.get('mpt_issuance_id', 'NOT FOUND')}")

    if args.type == "large":
        trigger_large(state)
    elif args.type == "burst":
        trigger_burst(state)
    else:
        trigger_subscribe(state)


if __name__ == "__main__":
    main()
