import React, { useState, useEffect } from 'react'
import { mockRiskScores } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const LIVE_TICKER = 'MMFXX'

function SemicircleGauge({ score, label }) {
  const getColor = (s) => {
    if (s <= 40) return '#00C853'
    if (s <= 70) return '#FFC107'
    return '#FF5252'
  }

  const color = getColor(score)
  const radius = 60
  const circumference = Math.PI * radius
  const strokeDashoffset = circumference - (score / 100) * circumference

  return (
    <div className="flex flex-col items-center justify-center py-1">
      <div className="relative w-[120px] h-[66px] flex flex-col items-center overflow-hidden">
        <svg width="120" height="66" viewBox="0 0 134 75" className="absolute top-0 left-0">
          {/* Track */}
          <path
            d={`M 7 65 A ${radius} ${radius} 0 0 1 127 65`}
            fill="none"
            stroke="#1E2530"
            strokeWidth="12"
            strokeLinecap="round"
          />
          {/* Fill */}
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

export function RiskGauge({ selectedTicker, riskScores }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker)

  useEffect(() => {
    setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const scores = riskScores ?? mockRiskScores
  const fundScores = hasData
    ? (scores.find((r) => r.fund_id === localTicker) ?? scores[0])
    : null

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
            {localTicker} RISK
          </h2>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-1 p-2 overflow-y-auto scrollbar-hide">
          <div className="flex items-start justify-center gap-2 w-full">
            <SemicircleGauge score={fundScores?.nw_stress ?? fundScores?.score ?? 32} label="NW Stress" />
            <div className="w-px self-stretch bg-[#1E2530] my-1" />
            <SemicircleGauge score={fundScores?.vol_index ?? 78} label="Vol Index" />
          </div>

          {fundScores?.score !== undefined && (
            <>
              <div className="w-full h-px bg-[#1E2530]" />
              <div className="w-full px-3 space-y-1">
                <div className="flex justify-between text-[10px] font-mono">
                  <span className="text-[#9AA4B2]">Composite Score</span>
                  <span
                    className="font-bold"
                    style={{
                      color: fundScores.score <= 40 ? '#00C853' : fundScores.score <= 70 ? '#FFC107' : '#FF5252',
                    }}
                  >
                    {fundScores.score}
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-3">
          <span className="text-[#9AA4B2] font-mono text-[11px] tracking-widest">{localTicker}</span>

          {/* Null gauge placeholders */}
          <div className="flex items-center gap-3 opacity-20">
            <div className="flex flex-col items-center gap-1">
              <svg width="120" height="66" viewBox="0 0 134 75">
                <path d="M 7 65 A 60 60 0 0 1 127 65" fill="none" stroke="#1E2530" strokeWidth="12" strokeLinecap="round" />
              </svg>
              <span className="text-[#9AA4B2] font-mono text-[24px] font-bold">--</span>
            </div>
            <div className="w-px self-stretch bg-[#1E2530]" />
            <div className="flex flex-col items-center gap-1">
              <svg width="120" height="66" viewBox="0 0 134 75">
                <path d="M 7 65 A 60 60 0 0 1 127 65" fill="none" stroke="#1E2530" strokeWidth="12" strokeLinecap="round" />
              </svg>
              <span className="text-[#9AA4B2] font-mono text-[24px] font-bold">--</span>
            </div>
          </div>

          <span className="text-[#9AA4B2]/50 font-mono text-[10px] uppercase tracking-wider">
            NO RISK DATA AVAILABLE
          </span>
          <span className="text-[#9AA4B2]/30 font-mono text-[9px]">
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}
    </div>
  )
}
