import React, { useState, useEffect, useRef } from 'react'
import { mockEvents } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'
import {
  usePanelFontSize,
  panelRootStyle, panelHeaderStyle, panelTitleStyle, panelSubtitleStyle,
  panelFooterStyle, colHeaderStyle, dataFontSize,
  TEXT_WHITE, TEXT_MUTED, TEXT_PRIMARY, COLOR_GREEN,
} from '../lib/panelTheme.js'

const LIVE_TICKER = 'MMFXX'

// Column definitions: flex weight determines proportional width
const COLS = [
  { key: 'time',    label: 'TIME',    flex: 1.4, align: 'left'  },
  { key: 'type',    label: 'TYPE',    flex: 2.0, align: 'left'  },
  { key: 'amount',  label: 'AMOUNT',  flex: 1.8, align: 'center' },
  { key: 'account', label: 'ACCOUNT', flex: 2.0, align: 'left'  },
]

// Glyph prefix (▲/▼) + color per transaction type. TRUST_SET has no glyph.
const TYPE_META = {
  SUBSCRIPTION:  { glyph: '▲', color: '#00C853' },
  ESCROW_CREATE: { glyph: '▲', color: '#FFC107' },
  ESCROW_FINISH: { glyph: '▲', color: '#00C853' },
  REDEMPTION:    { glyph: '▼', color: '#FF5252' },
  TRUST_SET:     { glyph: null, color: null },
}
function getTypeMeta(type) {
  return TYPE_META[type] ?? { glyph: null, color: null }
}

// ACCOUNT col is flex 2.0 out of 7.2 total (~27.7% of panel width).
// At ~7px per monospace char, compute how many chars fit on each side.
function formatAccount(account, panelWidth = 0) {
  if (!account) return account
  const len = account.length
  const colPx = Math.max(60, panelWidth * 0.277 - 10)
  const half = Math.max(4, Math.floor((Math.floor(colPx / 7) - 3) / 2))
  if (len <= half * 2 + 3) return account
  return `${account.slice(0, half)}...${account.slice(-half)}`
}

function EventRow({ event, fontSize, isOdd, panelWidth }) {
  const [hovered, setHovered] = useState(false)
  const df = dataFontSize(fontSize)
  const pad = `${fontSize * 0.4}px ${fontSize * 0.9}px`
  const cellBase = { minWidth: 0, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', fontFamily: 'monospace', fontSize: df }
  const typeMeta = getTypeMeta(event.type)

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: pad,
        gap: `${fontSize * 0.8}px`,
        minHeight: fontSize * 2.2,
        backgroundColor: hovered ? '#1E2530' : isOdd ? 'rgba(17,22,29,0.3)' : 'transparent',
        transition: 'background-color 0.15s',
        cursor: 'default',
        borderBottom: '1px solid rgba(30,37,48,0.4)',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <span style={{ ...cellBase, flex: COLS[0].flex, color: TEXT_MUTED }}>
        {event.time}
      </span>
      <span style={{ ...cellBase, flex: COLS[1].flex, fontWeight: 700 }}>
        {typeMeta.glyph && (
          <span style={{ color: typeMeta.color, marginRight: '0.4em', fontSize: '0.78em' }}>
            {typeMeta.glyph}
          </span>
        )}
        <span style={{ color: TEXT_WHITE }}>{event.type}</span>
      </span>
      <span style={{ ...cellBase, flex: COLS[2].flex, color: TEXT_PRIMARY, textAlign: 'center' }}>
        {event.amount !== '-' ? Number(event.amount).toLocaleString() : '-'}
      </span>
      <span style={{ ...cellBase, flex: COLS[3].flex, color: TEXT_WHITE }}>
        {formatAccount(event.account, panelWidth)}
      </span>
    </div>
  )
}

export function EventStream({ selectedTicker, events, wsConnected, onTickerChange }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker)
  const [containerWidth, setContainerWidth] = useState(0)
  const containerRef = useRef(null)
  const fontSize = usePanelFontSize(containerRef)
  const df = dataFontSize(fontSize)
  const chStyle = colHeaderStyle(fontSize)
  const hdrFontSize = Math.max(8, fontSize * 0.82)
  const colGap = `${fontSize * 0.8}px`

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const stream = hasData ? (events?.length ? events : mockEvents) : []

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    if (parts[0] === 'GO' && parts[1]) {
      setLocalTicker(parts[1])
      onTickerChange?.(parts[1])
      return `VIEWING ${parts[1]}`
    }
    return `UNKNOWN CMD: ${parts[0]}`
  }

  return (
    <div ref={containerRef} style={panelRootStyle()}>
      {/* Header */}
      <div style={panelHeaderStyle()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: `${fontSize * 0.35}px ${fontSize * 0.9}px` }}>
          <h2 style={panelTitleStyle(fontSize)}>
            {localTicker}{' '}
            <span style={panelSubtitleStyle(fontSize)}>STREAM</span>
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: fontSize * 0.5, fontFamily: 'monospace', fontSize: chStyle.fontSize }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: fontSize * 0.35 }}>
              <span style={{
                width: fontSize * 0.55,
                height: fontSize * 0.55,
                borderRadius: '50%',
                backgroundColor: wsConnected ? COLOR_GREEN : '#FF5252',
                flexShrink: 0,
              }} />
              <span style={{ color: wsConnected ? COLOR_GREEN : '#FF5252' }}>
                {wsConnected ? 'LIVE' : 'OFFLINE'}
              </span>
            </span>
          </div>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {/* Column headers */}
      <div
        className="border-b border-[#1E2530] bg-[#0B0F14] shrink-0"
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: `${hdrFontSize * 0.35}px ${fontSize * 0.9}px`,
          gap: colGap,
          fontSize: hdrFontSize,
        }}
      >
        {COLS.map((col) => (
          <span
            key={col.key}
            style={{
              minWidth: 0,
              flex: col.flex,
              color: 'rgba(154,164,178,0.55)',
              textAlign: col.align,
              fontFamily: 'monospace',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
            }}
          >
            {col.label}
          </span>
        ))}
      </div>

      {hasData ? (
        <div className="flex-1 overflow-y-auto overflow-x-hidden scrollbar-hide">
          {stream.map((event, i) => (
            <EventRow key={event.id} event={event} fontSize={fontSize} isOdd={i % 2 !== 0} panelWidth={containerWidth} />
          ))}
        </div>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: fontSize * 0.5, textAlign: 'center', fontFamily: 'monospace' }}>
          <span style={{ color: TEXT_MUTED, fontSize: df, letterSpacing: '0.1em' }}>{localTicker}</span>
          <span style={{ color: '#1E2530', fontSize: df * 2.5, fontWeight: 700, letterSpacing: '0.1em' }}>N/A</span>
          <span style={{ color: 'rgba(154,164,178,0.5)', fontSize: chStyle.fontSize, textTransform: 'uppercase', letterSpacing: '0.08em' }}>NO STREAM DATA AVAILABLE</span>
          <span style={{ color: 'rgba(154,164,178,0.3)', fontSize: chStyle.fontSize * 0.9, marginTop: fontSize * 0.3 }}>
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}

      {/* Footer */}
      <div style={panelFooterStyle(fontSize)}>
        <span>XRPL Testnet · Altnet</span>
        <span>HTTP POLL · 10s</span>
      </div>
    </div>
  )
}
