export const PANEL_ALIASES = {
  ES: 'ESCROW', ESCROW: 'ESCROW',
  AF: 'ALERT',  ALERT: 'ALERT',  ALERTS: 'ALERT',
  EV: 'EVENTS', EVENTS: 'EVENTS', STREAM: 'EVENTS',
  RG: 'RISK',   RISK: 'RISK',
}

export const PANEL_LABELS = {
  ESCROW: 'ESCROW',
  ALERT:  'ALERT FEED',
  EVENTS: 'EVENT STREAM',
  RISK:   'RISK GAUGE',
}

export const PROTECTED_ALIASES = new Set(['MON', 'MONITOR', 'YF', 'YIELD', 'YC'])

export const MAX_DYNAMIC_SLOTS = 4

export const HELP_TEXT = 'ADD/DEL <ES|AF|EV|RG> <TICKER> · MON & YF are permanent'

export const DEFAULT_DYNAMIC_SLOTS = [
  { id: 'default-0', type: 'ESCROW', ticker: 'MMFXX' },
  { id: 'default-1', type: 'ALERT',  ticker: 'MMFXX' },
  { id: 'default-2', type: 'EVENTS', ticker: 'MMFXX' },
  { id: 'default-3', type: 'RISK',   ticker: 'MMFXX', tickers: ['MMFXX'] },
]

let _idSeq = 0
export function makeSlotId() {
  return `slot-${Date.now()}-${_idSeq++}`
}

export function parseCommand(cmd) {
  const parts = cmd.trim().split(/\s+/)
  const action = parts[0]

  if (action === 'HELP') return { action: 'HELP' }

  if (action !== 'ADD' && action !== 'DEL') {
    return { error: `UNKNOWN CMD: ${action} — TRY ADD / DEL / HELP` }
  }

  const alias = parts[1]
  if (!alias) return { error: `USAGE: ${action} <PANEL> <TICKER>` }

  if (PROTECTED_ALIASES.has(alias)) {
    return { error: `${alias} IS PERMANENT — CANNOT ${action}` }
  }

  const type = PANEL_ALIASES[alias]
  if (!type) return { error: `UNKNOWN PANEL: ${alias} — TYPE HELP` }

  const ticker = parts[2]
  if (!ticker) return { error: `USAGE: ${action} ${alias} <TICKER> (e.g. MMFXX)` }

  return { action, type, ticker }
}

// Assigns defaultSize percentages to panels in a row.
// YIELD and EVENTS get 2× weight to stay prominent.
export function computeRowSizes(types) {
  if (!types.length) return []
  const weights = types.map(t => (t === 'YIELD' || t === 'EVENTS') ? 2 : 1)
  const total = weights.reduce((a, b) => a + b, 0)
  const sizes = weights.map(w => Math.round((w / total) * 100))
  // Correct any rounding drift so sizes always sum to 100
  sizes[0] += 100 - sizes.reduce((a, b) => a + b, 0)
  return sizes
}
