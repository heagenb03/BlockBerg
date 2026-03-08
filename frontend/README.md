# XRPLBlerg Frontend

React-based “Bloomberg-style” terminal UI for tokenized MMFs: resizable panels, fund cards, yield chart with ML forecast, escrow panel, alert feed, event stream, and risk gauges.

---

## Stack

- **React 19** + **Vite 7**
- **Tailwind CSS 4** (via `@tailwindcss/vite`)
- **Recharts** for yield/time-series charts
- **react-resizable-panels** for draggable layout
- **Axios** for API calls
- **lucide-react** for icons

---

## Scripts

| Command       | Description                |
|---------------|----------------------------|
| `npm run dev` | Start dev server (Vite)    |
| `npm run build` | Production build         |
| `npm run preview` | Preview production build |

---

## Development

1. Install dependencies: `npm install`
2. Start the backend on **port 8001** (see repo root or `backend/README.md`).
3. Run the frontend: `npm run dev`.

Vite proxies:

- **`/api`** → `http://localhost:8001`
- **`/ws`** → `http://localhost:8001` (WebSocket)

So all `axios.get('/api/...')` calls hit the FastAPI backend. Default dev URL is **http://localhost:5173**.

---

## Mock mode (no backend)

To run the UI without the backend, use mock data:

```bash
VITE_USE_MOCK=true npm run dev
```

Mock data is defined in `src/lib/mockData.js`. The app will not call the real API.

---

## Main pieces

| Path / area | Purpose |
|------------|--------|
| `src/App.jsx` | Renders the single `Terminal` page |
| `src/pages/terminal.jsx` | Terminal layout, panel slots, command parsing, persistence (localStorage) |
| `src/hooks/useTerminalData.js` | Fetches `/api/funds`, `/api/xrpl/fund`, `/api/ml/yield-forecast`, `/api/ml/anomalies`, `/api/ml/risk-scores`, `/api/xrpl/escrow`, `/api/xrpl/events` and drives loading/error state |
| `src/components/` | `TerminalHeader`, `FundCard`, `YieldChart`, `EscrowPanel`, `AlertFeed`, `EventStream`, `RiskGauge`, `ResizeHandle`, `PanelCommandLine` |
| `src/lib/panelSlots.js` | Panel slot types (e.g. ESCROW, ALERT, EVENTS, RISK), defaults, command parsing (e.g. `ADD RISK BUIDL`) |
| `src/lib/panelTheme.js` | Terminal styling / theme |
| `src/lib/mockData.js` | Mock data when `VITE_USE_MOCK=true` |

---

## Environment

| Variable | Description |
|----------|-------------|
| `VITE_USE_MOCK` | Set to `true` to use mock data and skip backend (default: unset/false) |

No `.env` is required for normal development as long as the backend runs on port 8001 (see `vite.config.js` proxy).
