import React, { useState, useEffect } from 'react'
import { mockAnomalies } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const LIVE_TICKER = 'MMFXX'

function getSeverityStyle(severity) {
  switch (severity) {
    case 'Critical': return { border: 'border-[#FF5252]', text: 'text-[#FF5252]', bg: 'bg-[#FF5252]/5' }
    case 'Warning':  return { border: 'border-[#FFC107]', text: 'text-[#FFC107]', bg: 'bg-[#FFC107]/5' }
    default:         return { border: 'border-[#9AA4B2]', text: 'text-[#9AA4B2]', bg: 'bg-[#FFFFFF]/5' }
  }
}

function formatTime(ts) {
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ts
  }
}

export function AlertFeed({ anomalies, selectedTicker }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker ?? LIVE_TICKER)

  useEffect(() => {
    if (selectedTicker) setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const alerts = hasData ? (anomalies?.length ? anomalies : mockAnomalies) : []
  const criticalCount = alerts.filter((a) => a.severity === 'Critical').length

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    if (parts[0] === 'GO' && parts[1]) {
      setLocalTicker(parts[1])
      return `VIEWING ${parts[1]}`
    }
    return `UNKNOWN CMD: ${parts[0]}`
  }

  return (
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="border-b border-[#1E2530] bg-[#11161D] flex flex-col">
        <div className="flex justify-between items-center p-1.5">
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase flex items-center gap-2">
            {localTicker} ALERTS
          </h2>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <div className="flex-1 overflow-y-auto p-1.5 space-y-1 scrollbar-hide">
          {alerts.map((alert, i) => {
            const style = getSeverityStyle(alert.severity)
            return (
              <div
                key={i}
                className={`flex flex-col gap-0.5 p-1.5 border-l-2 ${style.border} ${style.bg} hover:bg-[#1E2530] transition-colors cursor-pointer`}
              >
                <div className="flex justify-between items-center">
                  <span className={`text-[10px] font-bold uppercase tracking-wider ${style.text}`}>
                    {alert.severity}
                  </span>
                  <span className="text-[#9AA4B2] text-[10px] font-mono">
                    {formatTime(alert.timestamp)}
                  </span>
                </div>
                <p className="text-[#E6EDF3] text-[11px] leading-tight">{alert.description}</p>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
          <span className="text-[#9AA4B2] font-mono text-[11px] tracking-widest">{localTicker}</span>
          <span className="text-[#1E2530] font-mono text-[28px] font-bold tracking-wider">N/A</span>
          <span className="text-[#9AA4B2]/50 font-mono text-[10px] uppercase tracking-wider">
            NO ALERT DATA AVAILABLE
          </span>
          <span className="text-[#9AA4B2]/30 font-mono text-[9px] mt-1">
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}
    </div>
  )
}
