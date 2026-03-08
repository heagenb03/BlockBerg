"""
XRPL client: wallet setup, MPT issuance, Token Escrow, and API data functions.

On first startup, generates two Testnet wallets (fund + subscriber) via faucet,
issues an MPT with tfMPTCanTransfer|tfMPTCanEscrow, and creates 4 staggered
escrow positions to populate the EscrowPanel. All state is persisted to
state.json so restarts reuse the same wallets/token/escrows.

Delete state.json to start fresh (re-issues everything).
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import os
import random
import threading
import time
from pathlib import Path
from typing import Any

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountTx
from xrpl.models.amounts import MPTAmount
from xrpl.models.transactions import EscrowCreate, EscrowFinish, MPTokenAuthorize, MPTokenIssuanceCreate, Payment
from xrpl.models.transactions.mptoken_issuance_create import MPTokenIssuanceCreateFlag
from xrpl.transaction import submit_and_wait
from xrpl.wallet import Wallet, generate_faucet_wallet

logger = logging.getLogger(__name__)

TESTNET_URL = "https://s.altnet.rippletest.net:51234"
STATE_FILE = Path(__file__).parent / "state.json"

# Seconds between Unix epoch (1970) and Ripple epoch (2000-01-01)
RIPPLE_EPOCH = 946684800

# MPTokenIssuanceCreate flags (from xrpl-py MPTokenIssuanceCreateFlag enum)
TF_MPT_CAN_TRANSFER = MPTokenIssuanceCreateFlag.TF_MPT_CAN_TRANSFER  # 0x20
TF_MPT_CAN_ESCROW = MPTokenIssuanceCreateFlag.TF_MPT_CAN_ESCROW      # 0x08

INITIAL_SUPPLY = 10_000_000  # 10M fund tokens
NAV_PER_TOKEN = 1.00         # MMF NAV always $1
SIMULATED_YIELD_7D = 4.85    # placeholder until ML yield model is wired

# XLS-89 metadata as hex-encoded JSON
_METADATA_JSON = json.dumps(
    {
        "ticker": "MMFXX",
        "name": "Simulated Treasury Money Market Fund",
        "desc": "Tokenized MMF backed by short-term U.S. Treasuries",
        "asset_class": "rwa",
        "asset_subclass": "money_market_fund",
    },
    separators=(",", ":"),
)
METADATA_HEX = _METADATA_JSON.encode().hex().upper()

# Variability constants for escrow lifecycle
DEMO_AMOUNT_BASE = 100_000
DEMO_AMOUNT_JITTER = 0.25          # ±25%
DEMO_DURATION_BASE = 300           # 5 min in seconds
DEMO_DURATION_JITTER = 0.15        # ±15%
BURST_CHANCE = 0.20                # 20% per settler cycle
BURST_COUNT_RANGE = (2, 3)
BURST_AMOUNT_RANGE = (200_000, 1_200_000)
BURST_DURATION_HOURS = (1, 18)
SETTLER_INTERVAL_RANGE = (45, 75)  # seconds
FINISH_DELAY_RANGE = (30, 90)      # seconds of visible "finished" state before on-chain settle
MAX_ESCROW_ENTRIES = 15

# Escrow positions created on startup for demo (staggered finish times)
_ESCROW_CONFIGS = [
    {"amount": "100000",  "label": "Demo (5min)",    "hours": 0.0833},  # 5 min — full lifecycle visible live
    {"amount": "500000",  "label": "Subscription A", "hours": 2},
    {"amount": "250000",  "label": "Subscription B", "hours": 6},
    {"amount": "1000000", "label": "Subscription C", "hours": 12},
    {"amount": "750000",  "label": "Subscription D", "hours": 24},
]

# ---------------------------------------------------------------------------
# Module-level state (populated by initialize())
# ---------------------------------------------------------------------------
_state: dict = {}
_fund_wallet: Wallet | None = None
_subscriber_wallet: Wallet | None = None
_mpt_issuance_id: str = ""
_escrow_positions: list[dict] = []

# Thread lock protecting _escrow_positions from concurrent access
_escrow_lock = threading.Lock()



# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _new_client() -> JsonRpcClient:
    return JsonRpcClient(TESTNET_URL)


def _ripple_now() -> int:
    return int(time.time()) - RIPPLE_EPOCH


def _load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def _save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    os.replace(tmp, STATE_FILE)


def _setup_wallets(
    client: JsonRpcClient, state: dict
) -> tuple[Wallet, Wallet]:
    if "wallet_seed" in state:
        logger.info("Loading existing wallets from state.json.")
        return (
            Wallet.from_seed(state["wallet_seed"]),
            Wallet.from_seed(state["subscriber_seed"]),
        )

    logger.info("Generating Testnet wallets via faucet (takes ~30s)...")
    fund_wallet = generate_faucet_wallet(client, debug=True)
    subscriber_wallet = generate_faucet_wallet(client, debug=True)

    state.update(
        {
            "wallet_seed": fund_wallet.seed,
            "wallet_address": fund_wallet.classic_address,
            "subscriber_seed": subscriber_wallet.seed,
            "subscriber_address": subscriber_wallet.classic_address,
        }
    )
    _save_state(state)
    logger.info("Fund wallet:       %s", fund_wallet.classic_address)
    logger.info("Subscriber wallet: %s", subscriber_wallet.classic_address)
    return fund_wallet, subscriber_wallet


def _issue_mpt(
    client: JsonRpcClient, state: dict, fund_wallet: Wallet
) -> str:
    if "mpt_issuance_id" in state:
        logger.info("Reusing existing MPT: %s", state["mpt_issuance_id"])
        return state["mpt_issuance_id"]

    logger.info("Issuing MPT on Testnet...")
    tx = MPTokenIssuanceCreate(
        account=fund_wallet.classic_address,
        flags=TF_MPT_CAN_TRANSFER | TF_MPT_CAN_ESCROW,
        maximum_amount=str(INITIAL_SUPPLY),
        mptoken_metadata=METADATA_HEX,
    )
    result = submit_and_wait(tx, client, fund_wallet)
    mpt_id = _extract_mpt_id(result.result)
    if not mpt_id:
        raise RuntimeError(f"MPT issuance failed — no MPTokenIssuance node in result: {result.result}")

    state["mpt_issuance_id"] = mpt_id
    _save_state(state)
    logger.info("MPT issued: %s", mpt_id)
    return mpt_id


def _extract_mpt_id(result: dict) -> str | None:
    """Extract the 192-bit MPTokenIssuanceID from MPTokenIssuanceCreate tx metadata.

    xrpl-py returns the ID directly in meta.mpt_issuance_id (48 hex chars).
    Fall back to scanning AffectedNodes for older response shapes.
    """
    meta = result.get("meta", {})
    # Primary: top-level field added by xrpl-py / rippled for this tx type
    if mpt_id := meta.get("mpt_issuance_id"):
        return mpt_id
    # Fallback: scan CreatedNode entries
    for node in meta.get("AffectedNodes", []):
        created = node.get("CreatedNode", {})
        if created.get("LedgerEntryType") == "MPTokenIssuance":
            return created.get("NewFields", {}).get("MPTokenIssuanceID")
    return None


def _authorize_and_fund_subscriber(
    client: JsonRpcClient,
    state: dict,
    mpt_id: str,
    fund_wallet: Wallet,
    subscriber_wallet: Wallet,
) -> None:
    """Opt the subscriber into the MPT and send tokens from the fund wallet.

    MPT holders must submit MPTokenAuthorize before they can receive or escrow
    tokens.  Without this ledger object, EscrowCreate returns tecOBJECT_NOT_FOUND.
    """
    if state.get("subscriber_authorized"):
        logger.info("Subscriber already authorized for MPT %s.", mpt_id)
        return

    logger.info("Authorizing subscriber wallet for MPT %s...", mpt_id)
    auth_tx = MPTokenAuthorize(
        account=subscriber_wallet.classic_address,
        mptoken_issuance_id=mpt_id,
    )
    submit_and_wait(auth_tx, client, subscriber_wallet)

    # Total escrow demand: sum of all configured amounts
    total_needed = str(sum(int(c["amount"]) for c in _ESCROW_CONFIGS))
    logger.info("Transferring %s tokens to subscriber wallet...", total_needed)
    pay_tx = Payment(
        account=fund_wallet.classic_address,
        destination=subscriber_wallet.classic_address,
        amount=MPTAmount(mpt_issuance_id=mpt_id, value=total_needed),
    )
    submit_and_wait(pay_tx, client, fund_wallet)

    state["subscriber_authorized"] = True
    _save_state(state)
    logger.info("Subscriber funded with %s MPT tokens.", total_needed)


def _create_escrows(
    client: JsonRpcClient,
    state: dict,
    mpt_id: str,
    fund_wallet: Wallet,
    subscriber_wallet: Wallet,
) -> list[dict]:
    now = _ripple_now()
    existing = state.get("escrows", [])

    active = [e for e in existing if e["finish_after"] > now and e.get("status") != "settled"]
    expired_unsettled = [e for e in existing if e["finish_after"] <= now and e.get("status") != "settled"]
    settled = [e for e in existing if e.get("status") == "settled"]

    # Finish any orphaned escrows left over from a previous server session
    if expired_unsettled:
        logger.info("Finishing %d orphaned escrow(s) from previous session...", len(expired_unsettled))
        for escrow in expired_unsettled:
            if _finish_escrow(client, escrow, fund_wallet):
                settled.append(escrow)
        state["escrows"] = active + settled
        _save_state(state)

    if active:
        logger.info("Reusing %d active escrow(s) from state.json.", len(active))
        return active + settled

    # Re-fund subscriber: EscrowFinish releases tokens to fund wallet (destination),
    # so the subscriber needs tokens transferred back before creating new escrows.
    total_needed = str(sum(int(c["amount"]) for c in _ESCROW_CONFIGS))
    if expired_unsettled or not existing:
        logger.info("Re-funding subscriber with %s tokens for new escrows...", total_needed)
        pay_tx = Payment(
            account=fund_wallet.classic_address,
            destination=subscriber_wallet.classic_address,
            amount=MPTAmount(mpt_issuance_id=mpt_id, value=total_needed),
        )
        submit_and_wait(pay_tx, client, fund_wallet)

    logger.info("Creating %d escrow positions...", len(_ESCROW_CONFIGS))
    escrows: list[dict] = []
    for cfg in _ESCROW_CONFIGS:
        finish_after = now + int(cfg["hours"] * 3600)
        tx = EscrowCreate(
            account=subscriber_wallet.classic_address,
            destination=fund_wallet.classic_address,
            amount=MPTAmount(mpt_issuance_id=mpt_id, value=cfg["amount"]),
            finish_after=finish_after,
        )
        result = submit_and_wait(tx, client, subscriber_wallet)
        seq = result.result.get("tx_json", {}).get("Sequence")
        escrow_id = f"{subscriber_wallet.classic_address}:{seq}"
        escrows.append(
            {
                "escrow_id": escrow_id,
                "subscriber": subscriber_wallet.classic_address,
                "amount": cfg["amount"],
                "label": cfg["label"],
                "finish_after": finish_after,
                "sequence": seq,
                "status": "active",
            }
        )
        logger.info(
            "  Escrow %s: %s tokens, %.4ghr lock", escrow_id, cfg["amount"], cfg["hours"]
        )

    all_escrows = settled + escrows
    state["escrows"] = all_escrows
    _save_state(state)
    return all_escrows


# ---------------------------------------------------------------------------
# Escrow settlement helpers
# ---------------------------------------------------------------------------

def _finish_escrow(client: JsonRpcClient, escrow: dict, fund_wallet: Wallet) -> bool:
    """Submit EscrowFinish on-chain for a single matured escrow.

    Returns True if settled (including already-settled on-chain).
    Mutates escrow["status"] to "settled" on success.
    """
    try:
        seq = int(escrow["sequence"])
        if seq <= 0:
            raise ValueError(f"Invalid sequence: {seq}")
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("Invalid escrow sequence for %s: %s", escrow.get("escrow_id"), exc)
        return False

    try:
        tx = EscrowFinish(
            account=fund_wallet.classic_address,
            owner=escrow["subscriber"],
            offer_sequence=seq,
        )
        result = submit_and_wait(tx, client, fund_wallet)
        tx_result = result.result.get("meta", {}).get("TransactionResult", "")
        if tx_result != "tesSUCCESS":
            logger.warning(
                "EscrowFinish for %s returned %s", escrow.get("escrow_id"), tx_result
            )
            return False
        escrow["status"] = "settled"
        escrow["settled_at"] = int(time.time())
        logger.info("Settled escrow %s (%s tokens)", escrow.get("escrow_id"), escrow.get("amount"))
        return True
    except Exception as exc:
        if "tecNO_TARGET" in str(exc):
            logger.info(
                "Escrow %s already settled on-chain (tecNO_TARGET) — marking settled",
                escrow.get("escrow_id"),
            )
            escrow["status"] = "settled"
            escrow.setdefault("settled_at", int(time.time()))
            return True
        logger.warning("EscrowFinish error for %s: %s", escrow.get("escrow_id"), exc)
        return False


def _finish_expired_escrows() -> int:
    """Finish all matured, unsettled escrows. Returns count of newly settled.

    Newly matured escrows are first marked 'finished' with a random 30-90s delay
    before on-chain EscrowFinish is submitted, so the UI shows the 'finished'
    status briefly before transitioning to 'settled'.
    """
    client = _new_client()
    now = _ripple_now()

    with _escrow_lock:
        # Mark newly matured active escrows as "finished" with a random settle delay
        for e in _escrow_positions:
            if (
                e["finish_after"] <= now
                and e.get("status") == "active"
                and "_settle_eligible_at" not in e
            ):
                delay = random.randint(*FINISH_DELAY_RANGE)
                e["_settle_eligible_at"] = now + delay
                e["status"] = "finished"
                logger.info(
                    "Escrow %s matured; will settle in %ds",
                    e.get("escrow_id"), delay,
                )

        to_settle = [
            e for e in _escrow_positions
            if e.get("status") == "finished"
            and now >= e.get("_settle_eligible_at", 0)
        ]

    settled_count = 0
    for escrow in to_settle:
        if _finish_escrow(client, escrow, _fund_wallet):
            settled_count += 1
            with _escrow_lock:
                _state["escrows"] = list(_escrow_positions)
                _save_state(_state)

    return settled_count


def _maybe_recreate_demo_escrow() -> None:
    """If the demo escrow is settled, re-fund subscriber and create a fresh 5-min escrow."""
    demo_label = "Demo (5min)"
    with _escrow_lock:
        demo = next((e for e in _escrow_positions if e.get("label") == demo_label), None)
        if demo is None or demo.get("status") != "settled":
            return

    # Randomize amount ±25% and duration ±15%
    amount = int(DEMO_AMOUNT_BASE * random.uniform(1 - DEMO_AMOUNT_JITTER, 1 + DEMO_AMOUNT_JITTER))
    duration = int(DEMO_DURATION_BASE * random.uniform(1 - DEMO_DURATION_JITTER, 1 + DEMO_DURATION_JITTER))

    client = _new_client()
    # Re-fund subscriber (settled tokens went to fund wallet as destination)
    try:
        pay_tx = Payment(
            account=_fund_wallet.classic_address,
            destination=_subscriber_wallet.classic_address,
            amount=MPTAmount(mpt_issuance_id=_mpt_issuance_id, value=str(amount)),
        )
        submit_and_wait(pay_tx, client, _fund_wallet)
    except Exception as exc:
        logger.warning("Demo escrow re-fund failed: %s", exc)
        return

    # Create a new demo escrow with jittered duration
    now = _ripple_now()
    finish_after = now + duration
    try:
        tx = EscrowCreate(
            account=_subscriber_wallet.classic_address,
            destination=_fund_wallet.classic_address,
            amount=MPTAmount(mpt_issuance_id=_mpt_issuance_id, value=str(amount)),
            finish_after=finish_after,
        )
        result = submit_and_wait(tx, client, _subscriber_wallet)
        seq = result.result.get("tx_json", {}).get("Sequence")
        new_demo: dict = {
            "escrow_id": f"{_subscriber_wallet.classic_address}:{seq}",
            "subscriber": _subscriber_wallet.classic_address,
            "amount": str(amount),
            "label": demo_label,
            "finish_after": finish_after,
            "sequence": seq,
            "status": "active",
        }
        with _escrow_lock:
            # Append new demo entry instead of replacing — keeps settlement history visible
            _escrow_positions.append(new_demo)
            # Cap total entries at MAX_ESCROW_ENTRIES: trim oldest settled demo escrows first
            settled_demos = [
                e for e in _escrow_positions
                if e.get("label") == demo_label and e.get("status") == "settled"
            ]
            while len(_escrow_positions) > MAX_ESCROW_ENTRIES and settled_demos:
                oldest = settled_demos.pop(0)
                _escrow_positions.remove(oldest)
            _state["escrows"] = list(_escrow_positions)
            _save_state(_state)
        logger.info("Demo escrow recreated: %d tokens, %ds lock", amount, duration)
    except Exception as exc:
        logger.warning("Demo escrow recreation failed: %s", exc)


_burst_counter: itertools.count = itertools.count(1)  # thread-safe label counter


def _maybe_create_burst_escrows() -> None:
    """20% chance per settler cycle to spawn 2-3 random subscription escrows."""
    if random.random() > BURST_CHANCE:
        return

    count = random.randint(*BURST_COUNT_RANGE)

    # Re-check cap under the lock before proceeding
    with _escrow_lock:
        active_count = len([e for e in _escrow_positions if e.get("status") != "settled"])
        if active_count + count > MAX_ESCROW_ENTRIES:
            return

    client = _new_client()
    for _ in range(count):
        amount = random.randint(*BURST_AMOUNT_RANGE)
        hours = random.uniform(*BURST_DURATION_HOURS)
        label = f"Subscription {next(_burst_counter)}"
        try:
            pay_tx = Payment(
                account=_fund_wallet.classic_address,
                destination=_subscriber_wallet.classic_address,
                amount=MPTAmount(mpt_issuance_id=_mpt_issuance_id, value=str(amount)),
            )
            submit_and_wait(pay_tx, client, _fund_wallet)

            now = _ripple_now()
            finish_after = now + int(hours * 3600)
            tx = EscrowCreate(
                account=_subscriber_wallet.classic_address,
                destination=_fund_wallet.classic_address,
                amount=MPTAmount(mpt_issuance_id=_mpt_issuance_id, value=str(amount)),
                finish_after=finish_after,
            )
            result = submit_and_wait(tx, client, _subscriber_wallet)
            seq = result.result.get("tx_json", {}).get("Sequence")
            with _escrow_lock:
                _escrow_positions.append({
                    "escrow_id": f"{_subscriber_wallet.classic_address}:{seq}",
                    "subscriber": _subscriber_wallet.classic_address,
                    "amount": str(amount),
                    "label": label,
                    "finish_after": finish_after,
                    "sequence": seq,
                    "status": "active",
                })
                # Trim oldest settled entries if over cap
                while len(_escrow_positions) > MAX_ESCROW_ENTRIES:
                    settled = [e for e in _escrow_positions if e.get("status") == "settled"]
                    if not settled:
                        break
                    _escrow_positions.remove(settled[0])
                _state["escrows"] = list(_escrow_positions)
                _save_state(_state)
            logger.info("Burst escrow created: %d tokens, %.1fhr lock (%s)", amount, hours, label)
        except Exception as exc:
            logger.warning("Burst escrow creation failed (%s): %s", label, exc)


def _settle_and_refresh() -> None:
    """Blocking: finish expired escrows and recreate demo escrow if needed. Run in executor."""
    settled = _finish_expired_escrows()
    if settled:
        logger.info("Escrow settler: settled %d escrow(s).", settled)
    _maybe_recreate_demo_escrow()
    _maybe_create_burst_escrows()


async def run_escrow_settler() -> None:
    """Background task: settle matured escrows every 60s and refresh the demo escrow.

    Mirrors run_xrpl_stream() pattern — retries on error, cancels cleanly.
    All blocking XRPL calls run in an executor to avoid blocking the event loop.
    """
    while True:
        try:
            await asyncio.sleep(random.randint(*SETTLER_INTERVAL_RANGE))
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _settle_and_refresh)
        except asyncio.CancelledError:
            logger.info("Escrow settler task cancelled.")
            raise
        except Exception as exc:
            logger.warning("Escrow settler error: %s — retrying next cycle", exc)


# ---------------------------------------------------------------------------
# Public: called at FastAPI lifespan startup
# ---------------------------------------------------------------------------

def initialize() -> None:
    """Load or create all XRPL state. Call once at app startup."""
    global _state, _fund_wallet, _subscriber_wallet, _mpt_issuance_id, _escrow_positions

    client = _new_client()
    _state = _load_state()
    _fund_wallet, _subscriber_wallet = _setup_wallets(client, _state)
    _mpt_issuance_id = _issue_mpt(client, _state, _fund_wallet)
    _authorize_and_fund_subscriber(
        client, _state, _mpt_issuance_id, _fund_wallet, _subscriber_wallet
    )
    _escrow_positions = _create_escrows(
        client, _state, _mpt_issuance_id, _fund_wallet, _subscriber_wallet
    )
    logger.info("XRPL initialization complete.")


# ---------------------------------------------------------------------------
# Public: API data functions (called by FastAPI route handlers)
# ---------------------------------------------------------------------------

def get_fund_data() -> dict[str, Any]:
    """Fetch live fund metrics for GET /api/xrpl/fund."""
    client = _new_client()
    req = AccountTx(account=_fund_wallet.classic_address, limit=10)
    resp = client.request(req)
    txns = resp.result.get("transactions", [])

    recent = [
        {
            "id": t.get("tx", {}).get("hash", "")[:16],
            "type": t.get("tx", {}).get("TransactionType", "Unknown"),
            "amount": str(t.get("tx", {}).get("Amount", "")),
            "account": t.get("tx", {}).get("Account", ""),
        }
        for t in txns[:5]
    ]

    return {
        "mpt_issuance_id": _mpt_issuance_id,
        "supply": INITIAL_SUPPLY,
        "nav": NAV_PER_TOKEN,
        "yield_7d": SIMULATED_YIELD_7D,
        "tvl_usd": INITIAL_SUPPLY * NAV_PER_TOKEN,
        "recent_txns": recent,
    }


_TX_TYPE_MAP = {
    "EscrowCreate": "ESCROW_CREATE",
    "EscrowFinish": "ESCROW_FINISH",
    "EscrowCancel": "ESCROW_CANCEL",
    "MPTokenIssuanceCreate": "MPT_ISSUE",
    "MPTokenIssuanceDestroy": "MPT_DESTROY",
    "MPTokenAuthorize": "MPT_AUTH",
    "Payment": "PAYMENT",
    "TrustSet": "TRUST_SET",
    "OfferCreate": "OFFER_CREATE",
    "OfferCancel": "OFFER_CANCEL",
}


def _fmt_time(ripple_date: int) -> str:
    """Format a Ripple epoch timestamp as HH:MM:SS for the EventStream table."""
    unix_ts = (ripple_date or 0) + RIPPLE_EPOCH
    t = time.gmtime(unix_ts)
    return f"{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"


def _extract_amount(raw: Any) -> str:
    """Return a plain numeric string from an XRPL Amount field.

    MPT amounts arrive as {"mpt_issuance_id": "...", "value": "123456"}.
    XRP drops arrive as a plain string/int. Return "-" for missing/empty.
    """
    if isinstance(raw, dict):
        return raw.get("value", "-")
    val = str(raw) if raw else "-"
    return val if val else "-"


def _classify_event(
    tx_type: str, account: str, destination: str, fund_addr: str, sub_addr: str
) -> tuple[str, str]:
    """Return (direction, display_label) for an XRPL transaction.

    Directions:
      SUB — subscription / investment in (subscriber → fund)
      RDM — redemption / payout out (fund → subscriber)
      CLR — settlement clearance (EscrowFinish)
      —   — neutral / administrative
    """
    if tx_type == "Payment":
        if account == fund_addr and destination == sub_addr:
            # Fund delivers tokens to investor = subscription issuance
            return "SUB", "SUBSCRIPTION"
        if account == sub_addr and destination == fund_addr:
            # Investor returns tokens to fund = redemption request
            return "RDM", "REDEMPTION"
        return "—", "PAYMENT"

    if tx_type == "EscrowCreate":
        if account == sub_addr:
            return "SUB", "ESCROW_CREATE"
        return "—", "ESCROW_CREATE"

    if tx_type == "EscrowFinish":
        return "CLR", "ESCROW_FINISH"

    return "—", _TX_TYPE_MAP.get(tx_type, "TRANSFER")


def get_events() -> list[dict[str, Any]]:
    """Fetch recent XRPL transactions for GET /api/xrpl/events.

    Queries both fund and subscriber wallets, deduplicates by hash, sorts
    newest-first, and annotates each event with a ``direction`` field so the
    frontend can distinguish subscriptions (SUB), redemptions (RDM), and
    settlement clearances (CLR).
    """
    if _fund_wallet is None or _subscriber_wallet is None:
        return []

    fund_addr = _fund_wallet.classic_address
    sub_addr = _subscriber_wallet.classic_address
    client = _new_client()

    # Collect unique transactions from both wallets keyed by hash
    seen: dict[str, dict] = {}
    for account in (fund_addr, sub_addr):
        req = AccountTx(account=account, limit=25)
        try:
            resp = client.request(req)
        except Exception:
            continue
        for t in resp.result.get("transactions", []):
            tx = t.get("tx_json") or t.get("tx") or {}
            # Hash may live at the envelope level or inside tx_json
            h = tx.get("hash") or t.get("hash") or ""
            if h and h not in seen:
                seen[h] = tx

    # Sort newest-first by Ripple date
    sorted_txns = sorted(seen.values(), key=lambda x: x.get("date", 0), reverse=True)

    result = []
    for tx in sorted_txns[:30]:
        tx_type = tx.get("TransactionType", "")
        account = tx.get("Account", "")
        destination = tx.get("Destination", "")
        direction, label = _classify_event(tx_type, account, destination, fund_addr, sub_addr)
        result.append(
            {
                "id": (tx.get("hash") or "")[:16],
                "time": _fmt_time(tx.get("date", 0)),
                "type": label,
                "amount": _extract_amount(tx.get("Amount") or tx.get("DeliverMax") or "-"),
                "account": account,
                "direction": direction,
            }
        )

    return result



def get_escrow_positions() -> list[dict[str, Any]]:
    """Return current escrow positions for GET /api/xrpl/escrow."""
    now = _ripple_now()
    with _escrow_lock:
        positions = list(_escrow_positions)

    result = []
    for e in positions:
        unix_finish = e["finish_after"] + RIPPLE_EPOCH
        persisted_status = e.get("status", "active")
        if persisted_status == "settled":
            display_status = "settled"
        elif persisted_status == "finished":
            display_status = "finished"
        elif e["finish_after"] > now:
            display_status = "maturing"
        else:
            display_status = "finished"
        result.append(
            {
                "escrow_id": e["escrow_id"],
                "subscriber": e["subscriber"],
                # int so EscrowPanel formatAmount() works (calls .toLocaleString())
                "amount": int(e["amount"]),
                "label": e.get("label", ""),
                # ISO string so new Date(finish_after) works in formatFinishAfter()
                "finish_after": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(unix_finish)
                ),
                # status: settled (on-chain finished) > maturing (active) > finished (expired, pending settle)
                "status": display_status,
                # ISO string when settled on-chain, null otherwise
                "settled_at": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(e["settled_at"])
                ) if e.get("settled_at") else None,
            }
        )
    return result
