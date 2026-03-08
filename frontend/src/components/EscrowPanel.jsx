import React, { useState, useEffect, useRef } from 'react'
import { mockEscrow } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'
import {
  usePanelFontSize,
  panelRootStyle, panelHeaderStyle, panelTitleStyle, panelSubtitleStyle,
  panelFooterStyle, colHeaderStyle, dataFontSize,
  TEXT_WHITE, TEXT_MUTED, TEXT_PRIMARY, COLOR_GREEN, COLOR_AMBER, COLOR_BLUE,
} from '../lib/panelTheme.js'

const LIVE_TICKER = 'MMFXX'

function formatEscrowId(id) {
  const [addr, seq] = id.split(':')
  if (!addr || !seq) return id
  return `…${addr.slice(-6)}:${seq}`
}

function formatAmount(n) {
  return n.toLocaleString()
}

function formatSettledAt(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    const mo  = String(d.getUTCMonth() + 1).padStart(2, '0')
    const day = String(d.getUTCDate()).padStart(2, '0')
    const hh  = String(d.getUTCHours()).padStart(2, '0')
    const mm  = String(d.getUTCMinutes()).padStart(2, '0')
    return `${mo}/${day} ${hh}:${mm}`
  } catch {
    return '—'
  }
}

function formatFinishAfter(ts) {
  try {
    const d = new Date(ts)
    const now = new Date()
    const diffMs = d - now
    const diffH = Math.floor(diffMs / 3_600_000)
    const diffM = Math.floor((diffMs % 3_600_000) / 60_000)
    if (diffMs < 0) return 'MATURED'
    return `T+${diffH}h${diffM}m`
  } catch {
    return ts
  }
}

function getStatusColor(status) {
  switch (status) {
    case 'maturing': return COLOR_AMBER
    case 'finished': return COLOR_GREEN
    case 'settled':  return COLOR_BLUE
    default:         return TEXT_MUTED
  }
}

export function EscrowPanel({ selectedTicker, escrow, onTickerChange }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker)
  const containerRef = useRef(null)
  const fontSize = usePanelFontSize(containerRef)
  const df = dataFontSize(fontSize)
  const chStyle = colHeaderStyle(fontSize)

  useEffect(() => {
    setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const positions = hasData ? (escrow?.length ? escrow : mockEscrow) : []

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    if (parts[0] === 'GO' && parts[1]) {
      setLocalTicker(parts[1])
      onTickerChange?.(parts[1])
      return `VIEWING ${parts[1]}`
    }
    return `UNKNOWN CMD: ${parts[0]}`
  }

  // Column layout: [ID 22%, Amount 20%, Settle 18%, Settled At 24%, Status 16%]
  const cols = [
    { label: 'ID',         w: '22%', align: 'left'  },
    { label: 'Amount',     w: '20%', align: 'right' },
    { label: 'Settle',     w: '18%', align: 'right' },
    { label: 'Settled At', w: '24%', align: 'right' },
    { label: 'Status',     w: '16%', align: 'right' },
  ]

  return (
    <div ref={containerRef} style={panelRootStyle()}>
      {/* Header */}
      <div style={panelHeaderStyle()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: `${fontSize * 0.35}px ${fontSize * 0.9}px` }}>
          <h2 style={panelTitleStyle(fontSize)}>
            {localTicker}{' '}
            <span style={panelSubtitleStyle(fontSize)}>ESCROW</span>
          </h2>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <>
          {/* Column headers */}
          <div style={{ display: 'flex', fontFamily: 'monospace', padding: `${fontSize * 0.35}px ${fontSize * 0.9}px`, background: '#0B0F14', borderBottom: `1px solid #1E2530`, flexShrink: 0 }}>
            {cols.map((col) => (
              <div key={col.label} style={{ ...chStyle, width: col.w, textAlign: col.align, flexShrink: 0 }}>
                {col.label}
              </div>
            ))}
          </div>

          {/* Rows */}
          <div style={{ flex: 1, overflowY: 'auto' }} className="scrollbar-hide">
            {positions.map((pos, i) => (
              <div
                key={pos.escrow_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: `${fontSize * 0.4}px ${fontSize * 0.9}px`,
                  fontFamily: 'monospace',
                  fontSize: df,
                  backgroundColor: i % 2 === 0 ? 'transparent' : 'rgba(17,22,29,0.2)',
                  borderBottom: `1px solid rgba(30,37,48,0.3)`,
                  cursor: 'pointer',
                  transition: 'background-color 0.15s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#1E2530'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = i % 2 === 0 ? 'transparent' : 'rgba(17,22,29,0.2)'}
              >
                <div style={{ width: '22%', color: TEXT_PRIMARY, flexShrink: 0 }}>{formatEscrowId(pos.escrow_id)}</div>
                <div style={{ width: '20%', color: TEXT_WHITE, textAlign: 'right', flexShrink: 0 }}>{formatAmount(pos.amount)}</div>
                <div style={{ width: '18%', color: TEXT_MUTED, textAlign: 'right', flexShrink: 0 }}>
                  {pos.status === 'settled' ? 'SETTLED' : formatFinishAfter(pos.finish_after)}
                </div>
                <div style={{ width: '24%', color: TEXT_MUTED, textAlign: 'right', flexShrink: 0 }}>
                  {formatSettledAt(pos.settled_at)}
                </div>
                <div style={{ width: '16%', color: getStatusColor(pos.status), textAlign: 'right', fontWeight: 700, fontSize: chStyle.fontSize, textTransform: 'uppercase', letterSpacing: '0.05em', flexShrink: 0 }}>
                  {pos.status}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: fontSize * 0.5, textAlign: 'center', fontFamily: 'monospace' }}>
          <span style={{ color: TEXT_MUTED, fontSize: df, letterSpacing: '0.1em' }}>{localTicker}</span>
          <span style={{ color: '#1E2530', fontSize: df * 2.5, fontWeight: 700, letterSpacing: '0.1em' }}>N/A</span>
          <span style={{ color: 'rgba(154,164,178,0.5)', fontSize: chStyle.fontSize, textTransform: 'uppercase', letterSpacing: '0.08em' }}>NO ESCROW DATA AVAILABLE</span>
          <span style={{ color: 'rgba(154,164,178,0.3)', fontSize: chStyle.fontSize * 0.9, marginTop: fontSize * 0.3 }}>
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}

      {/* Footer */}
      <div style={panelFooterStyle(fontSize)}>
        <span>XLS-85 MPT Escrow</span>
        <span>Mainnet: 2026-02-12</span>
      </div>
    </div>
  )
}
