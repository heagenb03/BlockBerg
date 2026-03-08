import React, { useState, useRef } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceDot,
} from 'recharts'
import { mockYieldForecast } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'
import {
  usePanelFontSize,
  panelRootStyle, panelHeaderStyle, panelTitleStyle, panelSubtitleStyle,
  colHeaderStyle, dataFontSize,
  YIELD_BG, BORDER, TEXT_MUTED, TEXT_PRIMARY, COLOR_RED,
} from '../lib/panelTheme.js'

const LIVE_TICKER = 'MMFXX'
const TICKER_COLORS = ['#FFFFFF', '#4FC3F7', '#00C853', '#CE93D8', '#FFB74D', '#F48FB1']

function getColor(index) {
  return TICKER_COLORS[index % TICKER_COLORS.length]
}

function CustomTooltip({ active, payload, label, fontSize }) {
  if (!active || !payload?.length) return null
  const fs = fontSize ?? 11
  return (
    <div style={{ background: '#11161D', border: `1px solid ${BORDER}`, padding: `${fs * 0.7}px ${fs}px`, fontFamily: 'monospace', fontSize: fs }}>
      <p style={{ color: TEXT_MUTED, marginBottom: fs * 0.4 }}>{label}</p>
      {payload.map((entry, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: fs * 2 }}>
          <span style={{ color: entry.color }}>{entry.name}:</span>
          <span style={{ color: TEXT_PRIMARY, fontWeight: 500 }}>{entry.value.toFixed(2)}%</span>
        </div>
      ))}
    </div>
  )
}

export function YieldChart({ yieldForecast }) {
  const [activeTickers, setActiveTickers] = useState([LIVE_TICKER])
  const containerRef = useRef(null)
  const fontSize = usePanelFontSize(containerRef)
  const df = dataFontSize(fontSize)

  const getTickerData = (ticker) => {
    if (ticker === LIVE_TICKER) return yieldForecast?.data ?? mockYieldForecast.data
    return []
  }

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

  const chStyle = colHeaderStyle(fontSize)

  return (
    <div ref={containerRef} style={{ ...panelRootStyle(YIELD_BG) }}>
      {/* Header */}
      <div style={panelHeaderStyle()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: `${fontSize * 0.35}px ${fontSize * 0.9}px` }}>
          <h2 style={panelTitleStyle(fontSize)}>
            {titleTickers}{' '}
            <span style={panelSubtitleStyle(fontSize)}>YIELD FORECAST</span>
          </h2>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="ADD BUIDL  or  DEL MMFXX" />
      </div>

      {hasAnyData ? (
        <>
          <div style={{ flex: 1, padding: `${fontSize * 0.5}px ${fontSize * 0.5}px 0`, minHeight: 150 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E2530" vertical={false} />
                <XAxis
                  dataKey="time"
                  stroke={TEXT_MUTED}
                  fontSize={df * 0.9}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontFamily: 'monospace', fill: TEXT_MUTED }}
                  dy={8}
                />
                <YAxis
                  stroke={TEXT_MUTED}
                  fontSize={df * 0.9}
                  tickLine={false}
                  axisLine={false}
                  domain={['auto', 'auto']}
                  tick={{ fontFamily: 'monospace', fill: TEXT_MUTED }}
                  tickFormatter={(v) => `${v}%`}
                />
                <Tooltip content={<CustomTooltip fontSize={df} />} />
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
                          <ReferenceDot key={`ao-${ticker}-${j}`} x={entry.time} y={entry[`actual_${ticker}`]} r={8} fill={COLOR_RED} stroke="none" fillOpacity={0.35} />,
                          <ReferenceDot key={`ac-${ticker}-${j}`} x={entry.time} y={entry[`actual_${ticker}`]} r={3} fill={COLOR_RED} stroke="#11161D" strokeWidth={2} />,
                        ]
                      : []
                  )
                )}
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Legend footer */}
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: `${fontSize * 0.5}px ${fontSize}px`, padding: `${fontSize * 0.45}px ${fontSize * 0.9}px`, background: '#11161D', borderTop: `1px solid ${BORDER}`, flexShrink: 0 }}>
            {activeTickers.map((ticker, i) => {
              const hasData = tickersWithData.includes(ticker)
              const color = getColor(tickersWithData.indexOf(ticker))
              return (
                <div key={ticker} style={{ display: 'flex', alignItems: 'center', gap: fontSize * 0.4, fontFamily: 'monospace', fontSize: chStyle.fontSize, textTransform: 'uppercase' }}>
                  <div style={{ width: fontSize, height: 1, backgroundColor: hasData ? color : TEXT_MUTED, flexShrink: 0 }} />
                  <span style={{ color: hasData ? TEXT_MUTED : 'rgba(154,164,178,0.3)' }}>
                    {ticker}{!hasData && ' N/A'}
                  </span>
                </div>
              )
            })}
            <div style={{ display: 'flex', alignItems: 'center', gap: fontSize * 0.4, fontFamily: 'monospace', fontSize: chStyle.fontSize, textTransform: 'uppercase' }}>
              <div style={{ width: fontSize, height: 0, borderTop: '1px dashed rgba(154,164,178,0.4)' }} />
              <span style={{ color: 'rgba(154,164,178,0.5)' }}>ML Pred</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: fontSize * 0.4, fontFamily: 'monospace', fontSize: chStyle.fontSize, textTransform: 'uppercase' }}>
              <div style={{ width: fontSize * 0.7, height: fontSize * 0.7, borderRadius: '50%', backgroundColor: COLOR_RED, flexShrink: 0 }} />
              <span style={{ color: TEXT_MUTED }}>Anomaly</span>
            </div>
          </div>
        </>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: fontSize * 0.5, textAlign: 'center', fontFamily: 'monospace' }}>
          <span style={{ color: TEXT_MUTED, fontSize: df, letterSpacing: '0.1em' }}>{activeTickers.join(' · ')}</span>
          <span style={{ color: '#1E2530', fontSize: df * 2.5, fontWeight: 700, letterSpacing: '0.1em' }}>N/A</span>
          <span style={{ color: 'rgba(154,164,178,0.5)', fontSize: chStyle.fontSize, textTransform: 'uppercase', letterSpacing: '0.08em' }}>NO YIELD DATA AVAILABLE</span>
          <span style={{ color: 'rgba(154,164,178,0.3)', fontSize: chStyle.fontSize * 0.9, marginTop: fontSize * 0.3 }}>TYPE  ADD {LIVE_TICKER}  TO SEE DATA</span>
        </div>
      )}
    </div>
  )
}
