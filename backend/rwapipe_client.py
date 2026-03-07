"""
RWA Pipe API client (rwapipe.com).

Wraps the public REST endpoints for market overview and token details.
Use these to get current TVL, yield (when available), and flows for
treasury tokens—e.g. to combine with historical CSV data in the yield predictor.

Endpoints
---------
  GET https://rwapipe.com/api/market
    → Market overview: all tokens with tvlUsd, change7d, netFlow24h/netFlow7d, etc.

  GET https://rwapipe.com/api/tokens/<address>
    → Single token: address, chain, symbol, name, type (e.g. us-treasury),
      yield, totalSupply, riskMetadata, lastYieldUpdate, etc.

No API key required (free tier). Token address can be Ethereum (0x...), or
chain-specific (e.g. Solana, Stellar). Use the same address format as in
the market response.
"""

from typing import Any, Optional

import json
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://rwapipe.com/api"

# Request like a browser to avoid 403 (many APIs block default Python User-Agent)
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get(url: str, timeout: float = 30.0) -> dict[str, Any]:
    """GET a JSON URL; raises on HTTP or parse errors."""
    req = urllib.request.Request(url, headers=_DEFAULT_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status != 200:
            raise urllib.error.HTTPError(url, resp.status, resp.reason, resp.headers, resp)
        return json.loads(resp.read().decode("utf-8"))


def fetch_market(timeout: float = 30.0) -> dict[str, Any]:
    """
    Get market overview with all tokens.

    Equivalent to: curl https://rwapipe.com/api/market

    Returns
    -------
    dict
        - success : bool
        - filters : dict (chain, category, issuer, etc.)
        - summary : dict
            - totalTokens : int
            - totalTVL : float
            - avgApy : float
            - chains : list[str]
            - types : list[str] (e.g. "us-treasury", "stablecoin")
        - data : list[dict]
            Each token has: address, symbol, name, chain, category, issuer,
            totalSupply, totalSupplyFormatted, tvlUsd, priceUsd, change24h,
            change7d, netFlow24h, netFlow7d, riskScore, holderCount, etc.
    """
    return _get(f"{BASE_URL}/market", timeout=timeout)


def fetch_token(
    address: str,
    base_url: str = BASE_URL,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Get details for a single token by address.

    Equivalent to: curl https://rwapipe.com/api/tokens/<address>

    Parameters
    ----------
    address : str
        Token address (e.g. Ethereum 0x7712c34205737192402172409a8f7ccef8aa2aec
        for BlackRock BUIDL). Use the same format as in the market response.
    base_url : str, optional
        API base URL; default https://rwapipe.com/api.
    timeout : float, optional
        Request timeout in seconds.

    Returns
    -------
    dict
        - success : bool
        - data : dict
            - address, chain, chainId, symbol, name, decimals, type (e.g. us-treasury)
            - issuer, description, website, deployDate
            - lastYieldUpdate : str or null
            - yield : float or null  (APY when available)
            - totalSupply, totalSupplyFormatted
            - riskMetadata : dict (contract, redemption, regulatory, custody)
    """
    url = f"{base_url}/tokens/{urllib.parse.quote(address, safe='')}"
    return _get(url, timeout=timeout)


def get_treasury_tokens_from_market(timeout: float = 30.0) -> list[dict[str, Any]]:
    """
    Fetch market and return only tokens with category/type us-treasury.

    Useful for listing all U.S. Treasury tokenized products (BUIDL, USDY, etc.)
    with their current tvlUsd, change7d, and netFlow fields.

    Returns
    -------
    list[dict]
        Subset of market["data"] where category == "us-treasury".
    """
    out = fetch_market(timeout=timeout)
    if not out.get("success") or "data" not in out:
        return []
    return [t for t in out["data"] if (t.get("category") or "").lower() == "us-treasury"]
