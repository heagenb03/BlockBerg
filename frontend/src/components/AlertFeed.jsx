import React, { useState, useEffect, useRef } from 'react'
import { mockAnomalies } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'
import {
  usePanelFontSize,
  panelRootStyle, panelHeaderStyle, panelTitleStyle, panelSubtitleStyle,
  colHeaderStyle, dataFontSize, formatTime,
  BORDER, TEXT_WHITE, TEXT_MUTED, TEXT_PRIMARY, COLOR_RED, COLOR_AMBER,
} from '../lib/panelTheme.js'

const LIVE_TICKER = 'MMFXX'

function getSeverityColor(severity) {
  switch (severity) {
    case 'Critical': return COLOR_RED
    case 'Warning':  return COLOR_AMBER
    default:         return TEXT_MUTED
  }
}


export function AlertFeed({ anomalies, selectedTicker, onTickerChange }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker ?? LIVE_TICKER)
  const [selectedAlert, setSelectedAlert] = useState(null)
  const containerRef = useRef(null)
  const fontSize = usePanelFontSize(containerRef)
  const df = dataFontSize(fontSize)
  const chStyle = colHeaderStyle(fontSize)

  useEffect(() => {
    if (selectedTicker) setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const alerts = hasData ? (anomalies?.length ? anomalies : mockAnomalies) : []

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    if (parts[0] === 'GO' && parts[1]) {
      setLocalTicker(parts[1])
      setSelectedAlert(null)
      onTickerChange?.(parts[1])
      return `VIEWING ${parts[1]}`
    }
    return `UNKNOWN CMD: ${parts[0]}`
  }

  const handleRowClick = (alert, i) => {
    setSelectedAlert(prev => prev?._idx === i ? null : { ...alert, _idx: i })
  }

  return (
    <div ref={containerRef} style={{ ...panelRootStyle(), fontFamily: 'monospace' }}>
      {/* Header */}
      <div style={panelHeaderStyle()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: `${fontSize * 0.35}px ${fontSize * 0.9}px` }}>
          <h2 style={panelTitleStyle(fontSize)}>
            {localTicker}{' '}
            <span style={panelSubtitleStyle(fontSize)}>ALERTS</span>
          </h2>
          {selectedAlert && (
            <button
              onClick={() => setSelectedAlert(null)}
              style={{ color: 'rgba(154,164,178,0.5)', fontSize: chStyle.fontSize, fontFamily: 'monospace', letterSpacing: '0.1em', textTransform: 'uppercase', background: 'none', border: 'none', cursor: 'pointer' }}
              onMouseEnter={(e) => e.currentTarget.style.color = TEXT_MUTED}
              onMouseLeave={(e) => e.currentTarget.style.color = 'rgba(154,164,178,0.5)'}
            >
              CLR
            </button>
          )}
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <>
          {/* Alert list */}
          <div style={{ flex: 1, overflowY: 'auto' }} className="scrollbar-hide">
            {alerts.map((alert, i) => {
              const color = getSeverityColor(alert.severity)
              const isSelected = selectedAlert?._idx === i
              return (
                <div
                  key={i}
                  onClick={() => handleRowClick(alert, i)}
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: fontSize * 0.5,
                    padding: `${fontSize * 0.22}px ${fontSize * 0.9}px`,
                    cursor: 'pointer',
                    backgroundColor: isSelected ? '#1E2530' : 'transparent',
                    transition: 'background-color 0.15s',
                    fontSize: df,
                  }}
                  onMouseEnter={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = 'rgba(30,37,48,0.6)' }}
                  onMouseLeave={(e) => { if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent' }}
                >
                  <p style={{ color, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', lineHeight: 1.4 }}>
                    <span style={{ color: TEXT_WHITE, fontWeight: 700 }}>{alert.severity.toUpperCase()}:</span>
                    {' '}{alert.description}
                  </p>
                  <span style={{ color: 'rgba(154,164,178,0.7)', fontSize: chStyle.fontSize, flexShrink: 0 }}>
                    {formatTime(alert.timestamp)}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Detail tray */}
          <div style={{ borderTop: `1px solid ${BORDER}`, background: '#0B0F14', minHeight: fontSize * 6, flexShrink: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: `${fontSize * 0.5}px ${fontSize * 0.9}px` }}>
            {selectedAlert ? (() => {
              const color = getSeverityColor(selectedAlert.severity)
              return (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: fontSize * 0.35 }}>
                    <span style={{ color, fontSize: chStyle.fontSize, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase' }}>
                      {selectedAlert.severity}
                    </span>
                    <span style={{ color: 'rgba(154,164,178,0.6)', fontSize: chStyle.fontSize }}>
                      {formatTime(selectedAlert.timestamp)}
                    </span>
                  </div>
                  <p style={{ color: TEXT_PRIMARY, fontSize: df, lineHeight: 1.45, display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                    {selectedAlert.description}
                  </p>
                </>
              )
            })() : (
              <span style={{ color: '#1E2530', fontSize: chStyle.fontSize, letterSpacing: '0.1em', textTransform: 'uppercase', textAlign: 'center' }}>
                SELECT ALERT TO EXPAND
              </span>
            )}
          </div>
        </>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: fontSize * 0.5, textAlign: 'center' }}>
          <span style={{ color: TEXT_MUTED, fontSize: df, letterSpacing: '0.1em' }}>{localTicker}</span>
          <span style={{ color: '#1E2530', fontSize: df * 2.5, fontWeight: 700, letterSpacing: '0.1em' }}>N/A</span>
          <span style={{ color: 'rgba(154,164,178,0.5)', fontSize: chStyle.fontSize, textTransform: 'uppercase', letterSpacing: '0.08em' }}>NO ALERT DATA AVAILABLE</span>
          <span style={{ color: 'rgba(154,164,178,0.3)', fontSize: chStyle.fontSize * 0.9, marginTop: fontSize * 0.3 }}>
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}
    </div>
  )
}
