import React, { useEffect, useState } from 'react'
import { Activity, Clock, Globe } from 'lucide-react'

export function TerminalHeader({ alertCount = 0 }) {
  const [time, setTime] = useState(new Date())

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="h-10 bg-[#000000] border-b border-[#1E2530] flex items-center justify-between px-4 text-[#E6EDF3] shrink-0 select-none">
      {/* Left */}
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-[#FFFFFF]" />
          <h1 className="text-sm font-bold tracking-widest text-[#FFFFFF] uppercase">MMF Terminal</h1>
          <span className="text-[#00C853] text-[10px] font-bold px-1.5 py-0.5 border border-[#00C853]/50 rounded-sm bg-[#00C853]/10">
            TESTNET
          </span>
        </div>

        <div className="flex items-center bg-[#11161D] border border-[#1E2530] rounded-sm px-2 py-0.5 ml-4">
          <span className="text-[#FFFFFF] font-mono text-xs">&gt;</span>
          <input
            type="text"
            placeholder="Enter command e.g. MMFXX YLD <GO>"
            className="bg-transparent border-none outline-none text-[#FFFFFF] font-mono text-xs w-[240px] ml-2 placeholder:text-[#9AA4B2]/50 focus:ring-0"
            spellCheck="false"
          />
          <div className="w-1.5 h-3.5 bg-[#FFFFFF] animate-pulse ml-1" />
        </div>
      </div>

      {/* Right */}
      <div className="flex items-center space-x-4 text-xs font-mono">
        {alertCount > 0 && (
          <>
            <div className="flex items-center space-x-1.5 text-[#FF5252]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#FF5252] animate-pulse" />
              <span>ALERTS ({alertCount})</span>
            </div>
            <div className="w-px h-3 bg-[#1E2530]" />
          </>
        )}
        <div className="flex items-center space-x-1.5 text-[#9AA4B2]">
          <Globe className="w-3.5 h-3.5" />
          <span>XRPL-TEST</span>
        </div>
        <div className="w-px h-3 bg-[#1E2530]" />
        <div className="flex items-center space-x-1.5 text-[#FFFFFF]">
          <Clock className="w-3.5 h-3.5" />
          <span>{time.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>
      </div>
    </div>
  )
}
