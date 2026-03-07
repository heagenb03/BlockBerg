import React from 'react'
import { RefreshCw } from 'lucide-react'
import { mockRiskScores } from '../lib/mockData.js'

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
    <div className="flex flex-col items-center justify-center py-2">
      <div className="relative w-[134px] h-[75px] flex flex-col items-center overflow-hidden">
        <svg width="134" height="75" viewBox="0 0 134 75" className="absolute top-0 left-0">
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
          <span className="text-[32px] font-mono font-bold tracking-tighter" style={{ color }}>
            {score}
          </span>
        </div>
      </div>
      <span className="text-[#E6EDF3] text-[11px] font-semibold tracking-wide mt-3 uppercase">
        {label}
      </span>
      <div className="flex justify-between w-[134px] mt-1 text-[9px] text-[#9AA4B2] font-mono px-1">
        <span>0</span>
        <span>40</span>
        <span>70</span>
        <span>100</span>
      </div>
      <div className="w-[134px] h-[3px] flex rounded-full mt-1 overflow-hidden opacity-70">
        <div className="bg-[#00C853] w-[40%] h-full" />
        <div className="bg-[#FFC107] w-[30%] h-full" />
        <div className="bg-[#FF5252] w-[30%] h-full" />
      </div>
    </div>
  )
}

export function RiskGauge({ selectedTicker, riskScores }) {
  const scores = riskScores ?? mockRiskScores
  const fundScores = scores.find((r) => r.fund_id === selectedTicker) ?? scores[0]

  return (
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="flex justify-between items-center p-1.5 border-b border-[#1E2530] bg-[#11161D]">
        <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase flex items-center gap-2">
          {selectedTicker} RISK <span className="text-[#9AA4B2] font-mono">&lt;GO&gt;</span>
        </h2>
        <button className="text-[#9AA4B2] hover:text-[#E6EDF3] transition-colors p-0.5">
          <RefreshCw className="w-3 h-3" />
        </button>
      </div>

      <div className="flex-1 flex flex-col items-center justify-around p-2 overflow-y-auto scrollbar-hide">
        <SemicircleGauge score={fundScores?.nw_stress ?? fundScores?.score ?? 32} label="NW Stress" />
        <div className="w-4/5 h-px bg-[#1E2530]" />
        <SemicircleGauge score={fundScores?.vol_index ?? 78} label="Vol Index" />

        {fundScores?.score !== undefined && (
          <>
            <div className="w-4/5 h-px bg-[#1E2530]" />
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
    </div>
  )
}
