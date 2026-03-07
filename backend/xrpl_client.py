"""
XRPL client: wallet setup, MPT issuance, Token Escrow, and API data functions.

On first startup, generates two Testnet wallets (fund + subscriber) via faucet,
issues an MPT with tfMPTCanTransfer|tfMPTCanEscrow, and creates 4 staggered
escrow positions to populate the EscrowPanel. All state is persisted to
state.json so restarts reuse the same wallets/token/escrows.

Delete state.json to start fresh (re-issues everything).
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountTx
from xrpl.models.amounts import MPTAmount
from xrpl.models.transactions import EscrowCreate, MPTokenAuthorize, MPTokenIssuanceCreate, Payment
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

# Escrow positions created on startup for demo (staggered finish times)
_ESCROW_CONFIGS = [
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
    STATE_FILE.write_text(json.dumps(state, indent=2))


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
    active = [e for e in existing if e["finish_after"] > now]
    if active:
        logger.info("Reusing %d active escrow(s) from state.json.", len(active))
        return active

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
            "  Escrow %s: %s tokens, %dhr lock", escrow_id, cfg["amount"], cfg["hours"]
        )

    state["escrows"] = escrows
    _save_state(state)
    return escrows


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
        "supply": str(INITIAL_SUPPLY),
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


def get_events() -> list[dict[str, Any]]:
    """Fetch recent XRPL transactions for GET /api/xrpl/events."""
    client = _new_client()
    req = AccountTx(account=_fund_wallet.classic_address, limit=25)
    resp = client.request(req)
    txns = resp.result.get("transactions", [])

    return [
        {
            "id": t.get("tx", {}).get("hash", "")[:16],
            "time": _fmt_time(t.get("tx", {}).get("date", 0)),
            "type": _TX_TYPE_MAP.get(
                t.get("tx", {}).get("TransactionType", ""), "TRANSFER"
            ),
            "amount": str(t.get("tx", {}).get("Amount", "-")),
            "account": t.get("tx", {}).get("Account", ""),
        }
        for t in txns
    ]


def get_escrow_positions() -> list[dict[str, Any]]:
    """Return current escrow positions for GET /api/xrpl/escrow."""
    now = _ripple_now()
    result = []
    for e in _escrow_positions:
        unix_finish = e["finish_after"] + RIPPLE_EPOCH
        is_active = e["finish_after"] > now
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
                # status values EscrowPanel knows: 'maturing', 'finished', default=pending
                "status": "maturing" if is_active else "finished",
            }
        )
    return result
