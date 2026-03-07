import React, { useState, useEffect } from 'react'
import { mockAnomalies } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const LIVE_TICKER = 'MMFXX'

function getSeverityStyle(severity) {
  switch (severity) {
    case 'Critical': return { msgColor: 'text-[#FF5252]' }
    case 'Warning':  return { msgColor: 'text-[#FFC107]' }
    default:         return { msgColor: 'text-[#9AA4B2]' }
  }
}

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ts
  }
}

export function AlertFeed({ anomalies, selectedTicker, onTickerChange }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker ?? LIVE_TICKER)
  const [selectedAlert, setSelectedAlert] = useState(null)

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
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-mono">
      <div className="border-b border-[#1E2530] bg-[#11161D] flex flex-col">
        <div className="flex justify-between items-center p-1.5">
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase">
            {localTicker} ALERTS
          </h2>
          {selectedAlert && (
            <button
              onClick={() => setSelectedAlert(null)}
              className="text-[#9AA4B2]/50 text-[10px] hover:text-[#9AA4B2] tracking-wider uppercase transition-colors"
            >
              CLR
            </button>
          )}
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <>
          <div className="flex-1 overflow-y-auto scrollbar-hide">
            {alerts.map((alert, i) => {
              const style = getSeverityStyle(alert.severity)
              const isSelected = selectedAlert?._idx === i
              return (
                <div
                  key={i}
                  onClick={() => handleRowClick(alert, i)}
                  className={`flex items-baseline justify-between gap-2 px-1.5 py-[3px] cursor-pointer transition-colors ${
                    isSelected ? 'bg-[#1E2530]' : 'hover:bg-[#1E2530]/60'
                  }`}
                >
                  <p className={`text-[11px] leading-tight flex-1 min-w-0 truncate ${style.msgColor}`}>
                    <span className="text-[#FFFFFF] font-bold">{alert.severity.toUpperCase()}:</span>
                    {' '}{alert.description}
                  </p>
                  <span className="text-[#9AA4B2]/70 text-[10px] shrink-0">
                    {formatTime(alert.timestamp)}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Detail tray */}
          <div className="border-t border-[#1E2530] bg-[#0B0F14] h-[72px] shrink-0 flex flex-col justify-center px-2 py-1.5">
            {selectedAlert ? (() => {
              const style = getSeverityStyle(selectedAlert.severity)
              return (
                <>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`text-[10px] font-bold tracking-widest uppercase ${style.msgColor}`}>
                      {selectedAlert.severity}
                    </span>
                    <span className="text-[#9AA4B2]/60 text-[10px]">
                      {formatTime(selectedAlert.timestamp)}
                    </span>
                  </div>
                  <p className="text-[#E6EDF3] text-[11px] leading-snug break-words line-clamp-3">
                    {selectedAlert.description}
                  </p>
                </>
              )
            })() : (
              <span className="text-[#1E2530] text-[10px] tracking-widest uppercase self-center">
                SELECT ALERT TO EXPAND
              </span>
            )}
          </div>
        </>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
          <span className="text-[#9AA4B2] text-[11px] tracking-widest">{localTicker}</span>
          <span className="text-[#1E2530] text-[28px] font-bold tracking-wider">N/A</span>
          <span className="text-[#9AA4B2]/50 text-[10px] uppercase tracking-wider">
            NO ALERT DATA AVAILABLE
          </span>
          <span className="text-[#9AA4B2]/30 text-[9px] mt-1">
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}
    </div>
  )
}
