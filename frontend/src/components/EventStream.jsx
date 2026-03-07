import React from 'react'
import { RefreshCw } from 'lucide-react'
import { mockEvents } from '../lib/mockData.js'

function getTypeColor(type) {
  switch (type) {
    case 'ESCROW_FINISH': return 'text-[#00C853]'
    case 'ESCROW_CREATE': return 'text-[#FFC107]'
    case 'TRUST_SET':     return 'text-[#9AA4B2]'
    default:              return 'text-[#FFFFFF]'
  }
}

export function EventStream({ selectedTicker, events }) {
  const stream = events?.length ? events : mockEvents

  return (
    <div className="bg-[#000000] border border-[#1E2530] h-full flex flex-col font-sans overflow-hidden">
      <div className="flex justify-between items-center p-1.5 border-b border-[#1E2530] bg-[#11161D]">
        <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase flex items-center gap-2">
          XRPL STREAM <span className="text-[#9AA4B2] font-mono">&lt;GO&gt;</span>
        </h2>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[#9AA4B2] uppercase font-mono border border-[#1E2530] px-1 bg-[#000000]">
            FILTER: {selectedTicker}
          </span>
          <button className="text-[#9AA4B2] hover:text-[#E6EDF3] transition-colors p-0.5">
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>
      </div>

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
                  {event.amount !== '-' ? `${event.amount} ${selectedTicker}` : '-'}
                </td>
                <td className="py-1 px-2 pl-4 text-[#FFFFFF] hover:text-[#FFC107] hover:underline">
                  {event.account}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
