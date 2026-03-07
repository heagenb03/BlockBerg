import React from 'react'
import { RefreshCw } from 'lucide-react'
import { mockAnomalies } from '../lib/mockData.js'

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

export function AlertFeed({ anomalies }) {
  const alerts = anomalies?.length ? anomalies : mockAnomalies
  const criticalCount = alerts.filter((a) => a.severity === 'Critical').length

  return (
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="flex justify-between items-center p-1.5 border-b border-[#1E2530] bg-[#11161D]">
        <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase flex items-center gap-2">
          ALERTS
          {criticalCount > 0 && (
            <span className="text-[#FF5252] font-mono text-[10px] border border-[#FF5252]/40 px-1 bg-[#FF5252]/10">
              {criticalCount} CRIT
            </span>
          )}
          <span className="text-[#9AA4B2] font-mono">&lt;GO&gt;</span>
        </h2>
        <button className="text-[#9AA4B2] hover:text-[#E6EDF3] transition-colors p-0.5">
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>

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
    </div>
  )
}
