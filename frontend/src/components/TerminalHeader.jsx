import React, { useEffect, useState } from 'react'
import { Activity, Clock } from 'lucide-react'

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
          <h1 className="text-sm font-bold tracking-widest text-[#FFFFFF] uppercase">MMFBlerg</h1>
        </div>

      </div>

      {/* Right */}
      <div className="flex items-center space-x-4 text-xs font-mono">
        <div className="w-px h-3 bg-[#1E2530]" />
        <div className="flex items-center space-x-1.5 text-[#FFFFFF]">
          <Clock className="w-3.5 h-3.5" />
          <span>{time.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>
      </div>
    </div>
  )
}
