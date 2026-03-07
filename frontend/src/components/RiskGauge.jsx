import React from 'react'
import { mockRiskScores } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const MAX_TICKERS = 3

function getColor(score) {
  if (score <= 40) return '#00C853'
  if (score <= 70) return '#FFC107'
  return '#FF5252'
}

function SemicircleGauge({ score, label }) {
  const color = getColor(score)
  const radius = 60
  const circumference = Math.PI * radius
  const strokeDashoffset = circumference - (score / 100) * circumference

  return (
    <div className="flex flex-col items-center justify-center py-1">
      <div className="relative w-[120px] h-[66px] flex flex-col items-center overflow-hidden">
        <svg width="120" height="66" viewBox="0 0 134 75" className="absolute top-0 left-0">
          <path
            d={`M 7 65 A ${radius} ${radius} 0 0 1 127 65`}
            fill="none"
            stroke="#1E2530"
            strokeWidth="12"
            strokeLinecap="round"
          />
          <path
            d={`M 7 65 A ${radius} ${radius} 0 0 1 127 65`}
            fill="none"
            stroke={color}
            strokeWidth="12"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            style={{ transition: 'stroke-dashoffset 1s ease-out, stroke 0.5s ease' }}
          />
        </svg>
        <div className="absolute bottom-0 w-full flex items-end justify-center mb-1">
          <span className="text-[28px] font-mono font-bold tracking-tighter" style={{ color }}>
            {score}
          </span>
        </div>
      </div>
      <span className="text-[#E6EDF3] text-[11px] font-semibold tracking-wide mt-1 uppercase">
        {label}
      </span>
    </div>
  )
}

const LIVE_TICKER = 'MMFXX'

function TickerRiskRow({ ticker, scores }) {
  const hasData = ticker === LIVE_TICKER
  const fundScores = hasData
    ? (scores.find((r) => r.fund_id === ticker) ?? scores[0])
    : null

  return (
    <div className="w-full py-1">
      <div className="flex items-center justify-between px-3 pb-1">
        <span className="text-[#9AA4B2] font-mono text-[10px] uppercase tracking-widest">
          {ticker}
        </span>
        {hasData && fundScores?.score !== undefined && (
          <span
            className="font-mono text-[10px] font-bold"
            style={{ color: getColor(fundScores.score) }}
          >
            {fundScores.score}
          </span>
        )}
      </div>

      {hasData ? (
        <div className="flex items-start justify-center gap-2 w-full px-2">
          <SemicircleGauge score={fundScores?.nw_stress ?? fundScores?.score ?? 32} label="NW Stress" />
          <div className="w-px self-stretch bg-[#1E2530] my-1" />
          <SemicircleGauge score={fundScores?.vol_index ?? 78} label="Vol Index" />
        </div>
      ) : (
        <div className="flex flex-col items-center gap-1 py-2">
          <div className="flex items-center gap-3 opacity-20">
            {[0, 1].map((i) => (
              <div key={i} className="flex flex-col items-center gap-1">
                <svg width="120" height="66" viewBox="0 0 134 75">
                  <path d="M 7 65 A 60 60 0 0 1 127 65" fill="none" stroke="#1E2530" strokeWidth="12" strokeLinecap="round" />
                </svg>
                <span className="text-[#9AA4B2] font-mono text-[24px] font-bold">--</span>
              </div>
            ))}
          </div>
          <span className="text-[#9AA4B2]/50 font-mono text-[9px] uppercase tracking-wider">
            NO RISK DATA · TYPE GO {LIVE_TICKER}
          </span>
        </div>
      )}
    </div>
  )
}

export function RiskGauge({ tickers, riskScores, onTickersChange }) {
  const scores = riskScores ?? mockRiskScores

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    const op = parts[0]
    const ticker = parts[1]

    if (!ticker) return 'USAGE: ADD <TICKER> or DEL <TICKER>'

    if (op === 'ADD') {
      if (tickers.includes(ticker)) return `${ticker} ALREADY DISPLAYED`
      if (tickers.length >= MAX_TICKERS) return `MAX ${MAX_TICKERS} TICKERS`
      onTickersChange([...tickers, ticker])
      return `ADDED ${ticker}`
    }

    if (op === 'DEL') {
      if (!tickers.includes(ticker)) return `${ticker} NOT FOUND`
      if (tickers.length === 1) return 'CANNOT REMOVE LAST TICKER'
      onTickersChange(tickers.filter((t) => t !== ticker))
      return `REMOVED ${ticker}`
    }

    return `UNKNOWN CMD: ${op}`
  }

  const titleTickers =
    tickers.length <= 3
      ? tickers.join(' · ')
      : `${tickers.slice(0, 3).join(' · ')} +${tickers.length - 3}`

  return (
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="border-b border-[#1E2530] bg-[#11161D] flex flex-col">
        <div className="flex items-center justify-between p-1.5">
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase">
            {titleTickers} RISK
          </h2>
          <span className="text-[9px] font-mono text-[#9AA4B2]">ADD · DEL</span>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="ADD BUIDL  or  DEL MMFXX" />
      </div>

      <div className="flex-1 overflow-auto scrollbar-hide divide-y divide-[#1E2530]">
        {tickers.map((ticker) => (
          <TickerRiskRow key={ticker} ticker={ticker} scores={scores} />
        ))}
      </div>
    </div>
  )
}
