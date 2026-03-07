# RWA Pipe API — Market & token endpoints

Official docs: **[docs.rwapipe.com/api](https://docs.rwapipe.com/api)**  
Swagger: [rwapipe.com/api/docs/](https://rwapipe.com/api/docs/)

**Note:** The docs state that data endpoints require an **API key** (`X-API-Key` header). Unauthenticated requests may return 401/403 from some environments. Get a free key at [docs.rwapipe.com/register](https://docs.rwapipe.com/register). The live [market](https://rwapipe.com/api/market) JSON is sometimes returned without a key when requested with a browser-like client.

---

## GET /api/market

**URL:** `https://rwapipe.com/api/market`

Market overview with all tokens and optional filters.

### Query parameters (optional)

| Parameter | Type | Description |
|-----------|------|-------------|
| `chain` | string | Filter by blockchain (e.g. ethereum, solana) |
| `category` | string | Filter by category (e.g. us-treasury, stablecoin) |
| `issuer` | string | Filter by issuer name |
| `excludeStablecoins` | boolean | Exclude stablecoin category |
| `minTvl` | number | Minimum TVL per token (USD) |

### Response shape

```json
{
  "success": true,
  "filters": {
    "chain": null,
    "category": null,
    "issuer": null,
    "excludeStablecoins": null,
    "minTvl": null
  },
  "summary": {
    "totalTokens": 217,
    "totalTVL": 334264499469.05,
    "avgApy": 3.26,
    "chains": ["ethereum", "tron", "solana", "bsc", "arbitrum", "base", ...],
    "types": ["stablecoin", "money-market", "us-treasury", "private-credit", ...]
  },
  "data": [
    {
      "address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
      "symbol": "USDT",
      "name": "Tether USD",
      "chain": "ethereum",
      "category": "stablecoin",
      "issuer": "Tether",
      "totalSupply": "96117790049840506",
      "totalSupplyFormatted": 96117790049.84052,
      "tvlUsd": 96117790049.84052,
      "priceUsd": 1,
      "change24h": null,
      "change7d": -0.0035315684169484702,
      "netFlow24h": null,
      "netFlow7d": null,
      "riskScore": 10,
      "holderCount": "0",
      "iconUrl": "",
      "website": "",
      "description": ""
    }
  ]
}
```

### `summary` fields

| Field | Type | Description |
|-------|------|-------------|
| `totalTokens` | int | Number of tokens in the result set |
| `totalTVL` | float | Sum of TVL across all tokens (USD) |
| `avgApy` | float | Average APY (e.g. 3.26) |
| `chains` | string[] | List of chains represented |
| `types` | string[] | Categories present (e.g. us-treasury, stablecoin) |

### Each item in `data`

| Field | Type | Description |
|-------|------|-------------|
| `address` | string | Token contract/account address (chain-specific format) |
| `symbol` | string | Ticker (e.g. BUIDL, USDY, USDT) |
| `name` | string | Full name |
| `chain` | string | Blockchain (ethereum, solana, stellar, …) |
| `category` | string | Category (us-treasury, stablecoin, money-market, …) |
| `issuer` | string | Issuer name (e.g. BlackRock, Ondo Finance) |
| `totalSupply` | string | Raw supply (string for precision) |
| `totalSupplyFormatted` | number | Human-readable supply |
| `tvlUsd` | number | Total value locked in USD |
| `priceUsd` | number | Price in USD |
| `change24h` | number \| null | 24h TVL change % |
| `change7d` | number \| null | 7d TVL change % |
| `netFlow24h` | number \| null | 24h net flow (USD or %) |
| `netFlow7d` | number \| null | 7d net flow |
| `riskScore` | number | Risk score (e.g. 10) |
| `holderCount` | string | Number of holders |
| `iconUrl`, `website`, `description` | string | Optional metadata |

For **U.S. Treasury** tokens only, filter by `category === "us-treasury"` or use the query `?category=us-treasury`.

---

## GET /api/tokens/:address

**URL:** `https://rwapipe.com/api/tokens/<address>`

Single-token details (yield, risk metadata, etc.). Address format is the same as in the market `data[].address` (e.g. `0x7712c34205737192402172409a8f7ccef8aa2aec` for BUIDL on Ethereum).

### Response shape (example)

```json
{
  "success": true,
  "data": {
    "address": "0x7712c34205737192402172409a8f7ccef8aa2aec",
    "chain": "ethereum",
    "chainId": 1,
    "symbol": "BUIDL",
    "name": "BlackRock USD Institutional Digital Liquidity Fund",
    "decimals": 6,
    "type": "us-treasury",
    "lastYieldUpdate": "2026-02-27",
    "issuer": "BlackRock",
    "description": "Tokenized money market fund backed by US Treasuries",
    "website": "https://www.blackrock.com",
    "deployDate": "2024-03-21",
    "riskMetadata": { "contract": {...}, "redemption": {...}, "regulatory": {...}, "custody": {...} },
    "totalSupply": "172020990720349",
    "totalSupplyFormatted": "172020990.72034898",
    "yield": null
  }
}
```

`yield` is the current APY when available; it can be `null` for some tokens.
