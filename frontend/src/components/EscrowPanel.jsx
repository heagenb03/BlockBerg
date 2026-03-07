import React, { useState, useEffect } from 'react'
import { Lock } from 'lucide-react'
import { mockEscrow } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const LIVE_TICKER = 'MMFXX'

function formatAmount(n) {
  return n.toLocaleString()
}

function formatFinishAfter(ts) {
  try {
    const d = new Date(ts)
    const now = new Date()
    const diffMs = d - now
    const diffH = Math.floor(diffMs / 3_600_000)
    const diffM = Math.floor((diffMs % 3_600_000) / 60_000)
    if (diffMs < 0) return 'MATURED'
    return `T+${diffH}h${diffM}m`
  } catch {
    return ts
  }
}

function getStatusStyle(status) {
  switch (status) {
    case 'maturing': return 'text-[#FFC107]'
    case 'finished': return 'text-[#00C853]'
    default:         return 'text-[#9AA4B2]'
  }
}

export function EscrowPanel({ selectedTicker, escrow }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker)

  useEffect(() => {
    setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const positions = hasData ? (escrow?.length ? escrow : mockEscrow) : []
  const totalLocked = positions.reduce((s, e) => s + e.amount, 0)

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    if (parts[0] === 'GO' && parts[1]) {
      setLocalTicker(parts[1])
      return `VIEWING ${parts[1]}`
    }
    return `UNKNOWN CMD: ${parts[0]}`
  }

  return (
    <div className="bg-[#0B0F14] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="border-b border-[#1E2530] bg-[#11161D] flex flex-col">
        <div className="flex items-center justify-between p-1.5">
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase">
            {localTicker} ESCROW
          </h2>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <>
          <div className="flex items-center justify-between px-2 py-1 bg-[#11161D]/60 border-b border-[#1E2530]/50 text-[10px] font-mono">
            <div className="flex items-center gap-1 text-[#9AA4B2]">
              <Lock className="w-2.5 h-2.5" />
              <span>LOCKED</span>
            </div>
            <span className="text-[#FFC107] font-bold">{formatAmount(totalLocked)} {localTicker}</span>
            <span className="text-[#9AA4B2]">T+1 SETTLE</span>
          </div>

          <div className="flex text-[10px] font-mono text-[#9AA4B2] uppercase px-2 py-1 bg-[#11161D] border-b border-[#1E2530]">
            <div className="w-[28%]">ID</div>
            <div className="w-[28%] text-right">Amount</div>
            <div className="w-[26%] text-right">Settle</div>
            <div className="w-[18%] text-right">Status</div>
          </div>

          <div className="flex-1 overflow-y-auto scrollbar-hide divide-y divide-[#1E2530]/30 font-mono text-[11px]">
            {positions.map((pos, i) => (
              <div
                key={pos.escrow_id}
                className={`flex items-center px-2 py-1.5 hover:bg-[#1E2530] transition-colors cursor-pointer ${i % 2 === 0 ? '' : 'bg-[#11161D]/20'}`}
              >
                <div className="w-[28%] text-[#E6EDF3]">{pos.escrow_id}</div>
                <div className="w-[28%] text-right text-[#FFFFFF]">{formatAmount(pos.amount)}</div>
                <div className="w-[26%] text-right text-[#9AA4B2]">{formatFinishAfter(pos.finish_after)}</div>
                <div className={`w-[18%] text-right font-bold uppercase text-[9px] ${getStatusStyle(pos.status)}`}>
                  {pos.status}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
          <span className="text-[#9AA4B2] font-mono text-[11px] tracking-widest">{localTicker}</span>
          <span className="text-[#1E2530] font-mono text-[28px] font-bold tracking-wider">N/A</span>
          <span className="text-[#9AA4B2]/50 font-mono text-[10px] uppercase tracking-wider">
            NO ESCROW DATA AVAILABLE
          </span>
          <span className="text-[#9AA4B2]/30 font-mono text-[9px] mt-1">
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}

      <div className="px-2 py-1 border-t border-[#1E2530] bg-[#11161D]/60 text-[9px] font-mono text-[#9AA4B2] flex justify-between">
        <span>XLS-85 MPT Escrow</span>
        <span>Mainnet: 2026-02-12</span>
      </div>
    </div>
  )
}
