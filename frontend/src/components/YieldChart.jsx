import React, { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceDot,
} from 'recharts'
import { mockYieldForecast } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const LIVE_TICKER = 'MMFXX'
const TICKER_COLORS = ['#FFFFFF', '#4FC3F7', '#00C853', '#CE93D8', '#FFB74D', '#F48FB1']

function getColor(index) {
  return TICKER_COLORS[index % TICKER_COLORS.length]
}

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

export function YieldChart({ yieldForecast }) {
  const [activeTickers, setActiveTickers] = useState([LIVE_TICKER])

  const getTickerData = (ticker) => {
    if (ticker === LIVE_TICKER) return yieldForecast?.data ?? mockYieldForecast.data
    return []
  }

  // Build merged chart data using MMFXX time axis as base
  const baseData = activeTickers.reduce((best, t) => {
    const d = getTickerData(t)
    return d.length > best.length ? d : best
  }, [])

  const chartData = baseData.map((point) => {
    const row = { time: point.time }
    activeTickers.forEach((ticker) => {
      const match = getTickerData(ticker).find((d) => d.time === point.time)
      if (match) {
        if (match.actual !== undefined) row[`actual_${ticker}`] = match.actual
        if (match.predicted !== undefined) row[`predicted_${ticker}`] = match.predicted
        if (match.anomaly) row[`anomaly_${ticker}`] = true
      }
    })
    return row
  })

  const tickersWithData = activeTickers.filter((t) => getTickerData(t).length > 0)
  const hasAnyData = tickersWithData.length > 0

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    const op = parts[0]
    const ticker = parts[1]

    if (!ticker) return 'USAGE: ADD <TICKER> or DEL <TICKER>'

    if (op === 'ADD') {
      if (activeTickers.includes(ticker)) return `${ticker} ALREADY DISPLAYED`
      if (activeTickers.length >= 6) return 'MAX 6 TICKERS'
      setActiveTickers((prev) => [...prev, ticker])
      return `ADDED ${ticker}`
    }

    if (op === 'DEL') {
      if (!activeTickers.includes(ticker)) return `${ticker} NOT FOUND`
      if (activeTickers.length === 1) return 'CANNOT REMOVE LAST TICKER'
      setActiveTickers((prev) => prev.filter((t) => t !== ticker))
      return `REMOVED ${ticker}`
    }

    return `UNKNOWN CMD: ${op}`
  }

  const titleTickers =
    activeTickers.length <= 3
      ? activeTickers.join(' · ')
      : `${activeTickers.slice(0, 3).join(' · ')} +${activeTickers.length - 3}`

  return (
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="border-b border-[#1E2530] bg-[#11161D] flex flex-col">
        <div className="flex justify-between items-center p-1.5">
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase">
            {titleTickers} YIELD FRCST
          </h2>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="ADD BUIDL  or  DEL MMFXX" />
      </div>

      {hasAnyData ? (
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
                {tickersWithData.map((ticker, i) => (
                  <React.Fragment key={ticker}>
                    <Line
                      type="monotone"
                      dataKey={`actual_${ticker}`}
                      name={`${ticker} Actual`}
                      stroke={getColor(i)}
                      strokeWidth={2}
                      dot={{ fill: '#11161D', stroke: getColor(i), strokeWidth: 2, r: 3 }}
                      activeDot={{ r: 5, fill: getColor(i) }}
                      connectNulls={false}
                    />
                    <Line
                      type="monotone"
                      dataKey={`predicted_${ticker}`}
                      name={`${ticker} ML Pred`}
                      stroke={getColor(i)}
                      strokeWidth={1.5}
                      strokeDasharray="5 5"
                      dot={false}
                      activeDot={{ r: 4, fill: getColor(i) }}
                      connectNulls={false}
                      opacity={0.6}
                    />
                  </React.Fragment>
                ))}
                {tickersWithData.flatMap((ticker, i) =>
                  chartData.flatMap((entry, j) =>
                    entry[`anomaly_${ticker}`] && entry[`actual_${ticker}`] !== undefined
                      ? [
                          <ReferenceDot key={`ao-${ticker}-${j}`} x={entry.time} y={entry[`actual_${ticker}`]} r={8} fill="#FF5252" stroke="none" fillOpacity={0.35} />,
                          <ReferenceDot key={`ac-${ticker}-${j}`} x={entry.time} y={entry[`actual_${ticker}`]} r={3} fill="#FF5252" stroke="#11161D" strokeWidth={2} />,
                        ]
                      : []
                  )
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-2 py-1.5 bg-[#11161D] border-t border-[#1E2530]">
            {activeTickers.map((ticker, i) => {
              const hasData = tickersWithData.includes(ticker)
              const color = getColor(tickersWithData.indexOf(ticker))
              return (
                <div key={ticker} className="flex items-center gap-1.5 text-[10px] font-mono uppercase">
                  <div className="w-3 h-px" style={{ backgroundColor: hasData ? color : '#9AA4B2' }} />
                  <span className={hasData ? 'text-[#9AA4B2]' : 'text-[#9AA4B2]/30'}>
                    {ticker}{!hasData && ' N/A'}
                  </span>
                </div>
              )
            })}
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase">
              <div className="w-3 h-px" style={{ borderTop: '1px dashed #9AA4B2', opacity: 0.4 }} />
              <span className="text-[#9AA4B2]/50">ML Pred</span>
            </div>
            <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase">
              <div className="w-2 h-2 rounded-full bg-[#FF5252]" />
              <span className="text-[#9AA4B2]">Anomaly</span>
            </div>
          </div>
        </>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
          <span className="text-[#9AA4B2] font-mono text-[11px] tracking-widest">
            {activeTickers.join(' · ')}
          </span>
          <span className="text-[#1E2530] font-mono text-[28px] font-bold tracking-wider">N/A</span>
          <span className="text-[#9AA4B2]/50 font-mono text-[10px] uppercase tracking-wider">
            NO YIELD DATA AVAILABLE
          </span>
          <span className="text-[#9AA4B2]/30 font-mono text-[9px] mt-1">
            TYPE  ADD {LIVE_TICKER}  TO SEE DATA
          </span>
        </div>
      )}
    </div>
  )
}
