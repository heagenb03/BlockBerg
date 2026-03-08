import React, { useState, useEffect, useRef } from 'react'
import { mockEvents } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'
import {
  usePanelFontSize,
  panelRootStyle, panelHeaderStyle, panelTitleStyle, panelSubtitleStyle,
  panelFooterStyle, colHeaderStyle, dataFontSize,
  TEXT_WHITE, TEXT_MUTED, TEXT_PRIMARY, COLOR_GREEN, COLOR_AMBER,
} from '../lib/panelTheme.js'

const LIVE_TICKER = 'MMFXX'

function getTypeColor(type) {
  switch (type) {
    case 'ESCROW_FINISH': return COLOR_GREEN
    case 'ESCROW_CREATE': return COLOR_AMBER
    case 'TRUST_SET':     return TEXT_MUTED
    default:              return TEXT_WHITE
  }
}

export function EventStream({ selectedTicker, events, wsConnected, onTickerChange }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker)
  const containerRef = useRef(null)
  const fontSize = usePanelFontSize(containerRef)
  const df = dataFontSize(fontSize)
  const chStyle = colHeaderStyle(fontSize)

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
    <div ref={containerRef} style={{ ...panelRootStyle(), overflow: 'hidden' }}>
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

      {hasData ? (
        <div style={{ flex: 1, overflowX: 'auto', overflowY: 'auto' }} className="scrollbar-hide">
          <table style={{ width: '100%', borderCollapse: 'collapse', whiteSpace: 'nowrap', fontFamily: 'monospace', fontSize: df }}>
            <thead style={{ position: 'sticky', top: 0, backgroundColor: '#0B0F14', borderBottom: `1px solid #1E2530`, zIndex: 10 }}>
              <tr>
                {['Time', 'Type', 'Amount', 'Account'].map((label, i) => (
                  <th key={label} style={{ ...chStyle, padding: `${fontSize * 0.35}px ${fontSize * 0.9}px`, textAlign: i === 2 ? 'right' : 'left', fontWeight: 400 }}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stream.map((event, i) => (
                <tr
                  key={event.id}
                  style={{
                    backgroundColor: i % 2 === 0 ? 'transparent' : 'rgba(17,22,29,0.3)',
                    cursor: 'pointer',
                    transition: 'background-color 0.15s',
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#1E2530'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = i % 2 === 0 ? 'transparent' : 'rgba(17,22,29,0.3)'}
                >
                  <td style={{ padding: `${fontSize * 0.3}px ${fontSize * 0.9}px`, color: TEXT_MUTED }}>{event.time}</td>
                  <td style={{ padding: `${fontSize * 0.3}px ${fontSize * 0.9}px`, color: getTypeColor(event.type), fontWeight: 700 }}>{event.type}</td>
                  <td style={{ padding: `${fontSize * 0.3}px ${fontSize * 0.9}px`, color: TEXT_PRIMARY, textAlign: 'right' }}>
                    {event.amount !== '-' ? `${event.amount} ${localTicker}` : '-'}
                  </td>
                  <td
                    style={{ padding: `${fontSize * 0.3}px ${fontSize * 0.9}px`, paddingLeft: fontSize * 1.8, color: TEXT_WHITE }}
                    onMouseEnter={(e) => { e.currentTarget.style.color = COLOR_AMBER; e.currentTarget.style.textDecoration = 'underline' }}
                    onMouseLeave={(e) => { e.currentTarget.style.color = TEXT_WHITE; e.currentTarget.style.textDecoration = 'none' }}
                  >
                    {event.account}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
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
