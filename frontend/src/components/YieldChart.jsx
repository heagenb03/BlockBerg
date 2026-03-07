import React, { useState, useEffect } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceDot,
} from 'recharts'
import { mockYieldForecast } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const LIVE_TICKER = 'MMFXX'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-[#11161D] border border-[#1E2530] p-3 shadow-lg font-sans text-xs">
      <p className="text-[#9AA4B2] mb-2 font-mono">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex justify-between items-center gap-4">
          <span style={{ color: entry.color }}>{entry.name}:</span>
          <span className="text-[#E6EDF3] font-mono font-medium">{entry.value.toFixed(2)}%</span>
        </div>
      ))}
    </div>
  )
}

export function YieldChart({ selectedTicker, yieldForecast }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker)

  useEffect(() => {
    setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const chartData = hasData ? (yieldForecast?.data ?? mockYieldForecast.data) : []

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
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase">
            {localTicker} YIELD FRCST
          </h2>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <>
          <div className="flex-1 p-2 pb-0 min-h-[150px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2530" vertical={false} />
                <XAxis
                  dataKey="time"
                  stroke="#9AA4B2"
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontFamily: 'monospace', fill: '#9AA4B2' }}
                  dy={8}
                />
                <YAxis
                  stroke="#9AA4B2"
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                  domain={['auto', 'auto']}
                  tick={{ fontFamily: 'monospace', fill: '#9AA4B2' }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Line
                  type="monotone"
                  dataKey="actual"
                  name="Actual Yield"
                  stroke="#FFFFFF"
                  strokeWidth={2}
                  dot={{ fill: '#11161D', stroke: '#FFFFFF', strokeWidth: 2, r: 3 }}
                  activeDot={{ r: 5, fill: '#FFFFFF' }}
                />
                <Line
                  type="monotone"
                  dataKey="predicted"
                  name="ML Forecast"
                  stroke="#FFC107"
                  strokeWidth={2}
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={{ r: 4, fill: '#FFC107' }}
                />
                {chartData.map((entry, i) =>
                  entry.anomaly ? (
                    <ReferenceDot key={`a-${i}`} x={entry.time} y={entry.actual} r={8} fill="#FF5252" stroke="none" fillOpacity={0.35} />
                  ) : null
                )}
                {chartData.map((entry, i) =>
                  entry.anomaly ? (
                    <ReferenceDot key={`ac-${i}`} x={entry.time} y={entry.actual} r={3} fill="#FF5252" stroke="#11161D" strokeWidth={2} />
                  ) : null
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="flex items-center gap-4 px-2 py-1.5 bg-[#11161D] border-t border-[#1E2530]">
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase">
              <div className="w-3 h-px bg-[#FFFFFF]" />
              <span className="text-[#9AA4B2]">Act ({localTicker})</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase">
              <div className="w-3 h-px bg-[#FFC107] border-dashed" style={{ borderTop: '1px dashed #FFC107' }} />
              <span className="text-[#9AA4B2]">ML Pred</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase">
              <div className="w-2 h-2 rounded-full bg-[#FF5252]" />
              <span className="text-[#9AA4B2]">Anomaly</span>
            </div>
          </div>
        </>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
          <span className="text-[#9AA4B2] font-mono text-[11px] tracking-widest">{localTicker}</span>
          <span className="text-[#1E2530] font-mono text-[28px] font-bold tracking-wider">N/A</span>
          <span className="text-[#9AA4B2]/50 font-mono text-[10px] uppercase tracking-wider">
            NO YIELD DATA AVAILABLE
          </span>
          <span className="text-[#9AA4B2]/30 font-mono text-[9px] mt-1">
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}
    </div>
  )
}
