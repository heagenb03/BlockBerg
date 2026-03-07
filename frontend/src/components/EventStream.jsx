import React, { useState, useEffect } from 'react'
import { mockEvents } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

const LIVE_TICKER = 'MMFXX'

function getTypeColor(type) {
  switch (type) {
    case 'ESCROW_FINISH': return 'text-[#00C853]'
    case 'ESCROW_CREATE': return 'text-[#FFC107]'
    case 'TRUST_SET':     return 'text-[#9AA4B2]'
    default:              return 'text-[#FFFFFF]'
  }
}

export function EventStream({ selectedTicker, events, wsConnected }) {
  const [localTicker, setLocalTicker] = useState(selectedTicker)

  useEffect(() => {
    setLocalTicker(selectedTicker)
  }, [selectedTicker])

  const hasData = localTicker === LIVE_TICKER
  const stream = hasData ? (events?.length ? events : mockEvents) : []

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    if (parts[0] === 'GO' && parts[1]) {
      setLocalTicker(parts[1])
      return `VIEWING ${parts[1]}`
    }
    return `UNKNOWN CMD: ${parts[0]}`
  }

  return (
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-sans overflow-hidden">
      <div className="border-b border-[#1E2530] bg-[#11161D] flex flex-col">
        <div className="flex justify-between items-center p-1.5">
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase flex items-center gap-2">
            {localTicker} STREAM
          </h2>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-1 text-[10px] font-mono">
              <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-[#00C853] animate-pulse' : 'bg-[#FF5252]'}`} />
              <span className={wsConnected ? 'text-[#00C853]' : 'text-[#FF5252]'}>
                {wsConnected ? 'LIVE' : 'OFFLINE'}
              </span>
            </span>
          </div>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="GO MMFXX" />
      </div>

      {hasData ? (
        <div className="flex-1 overflow-x-auto overflow-y-auto scrollbar-hide">
          <table className="w-full text-left border-collapse whitespace-nowrap">
            <thead className="sticky top-0 bg-[#11161D] border-b border-[#1E2530] z-10">
              <tr>
                <th className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase font-bold">Time</th>
                <th className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase font-bold">Type</th>
                <th className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase font-bold text-right">Amount</th>
                <th className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase font-bold pl-4">Account</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E2530]/30 font-mono text-[11px]">
              {stream.map((event, i) => (
                <tr
                  key={event.id}
                  className={`hover:bg-[#1E2530] cursor-pointer transition-colors ${i % 2 === 0 ? 'bg-[#000000]' : 'bg-[#11161D]/30'}`}
                >
                  <td className="py-1 px-2 text-[#9AA4B2]">{event.time}</td>
                  <td className={`py-1 px-2 font-bold ${getTypeColor(event.type)}`}>{event.type}</td>
                  <td className="py-1 px-2 text-[#E6EDF3] text-right">
                    {event.amount !== '-' ? `${event.amount} ${localTicker}` : '-'}
                  </td>
                  <td className="py-1 px-2 pl-4 text-[#FFFFFF] hover:text-[#FFC107] hover:underline">
                    {event.account}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
          <span className="text-[#9AA4B2] font-mono text-[11px] tracking-widest">{localTicker}</span>
          <span className="text-[#1E2530] font-mono text-[28px] font-bold tracking-wider">N/A</span>
          <span className="text-[#9AA4B2]/50 font-mono text-[10px] uppercase tracking-wider">
            NO STREAM DATA AVAILABLE
          </span>
          <span className="text-[#9AA4B2]/30 font-mono text-[9px] mt-1">
            TYPE  GO {LIVE_TICKER}  TO RESTORE
          </span>
        </div>
      )}
    </div>
  )
}
