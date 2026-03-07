import React, { useState } from 'react'
import { mockFunds } from '../lib/mockData.js'

export function FundCard({ funds, selectedTicker, onSelectTicker }) {
  const [sortCol, setSortCol] = useState('tvl')
  const [sortDir, setSortDir] = useState('desc')

  const fundList = funds && funds.length > 0 ? funds : mockFunds

  const sorted = [...fundList].sort((a, b) => {
    const av = a[sortCol], bv = b[sortCol]
    if (av < bv) return sortDir === 'asc' ? -1 : 1
    if (av > bv) return sortDir === 'asc' ? 1 : -1
    return 0
  })

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir('desc')
    }
  }

  const SortIndicator = ({ col }) =>
    sortCol === col ? (
      <span className="text-[#FFC107]">{sortDir === 'asc' ? ' ▲' : ' ▼'}</span>
    ) : null

  return (
    <div className="bg-[#0B0F14] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="flex items-center justify-between p-1.5 border-b border-[#1E2530] bg-[#11161D]">
        <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase flex items-center gap-2">
          MONITOR <span className="text-[#9AA4B2] font-mono">&lt;GO&gt;</span>
        </h2>
      </div>

      <div className="flex-1 overflow-auto scrollbar-hide">
        <table className="w-full text-left border-collapse whitespace-nowrap">
          <thead className="sticky top-0 bg-[#11161D] z-10 border-b border-[#1E2530]">
            <tr>
              <th
                className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase cursor-pointer hover:text-[#E6EDF3] select-none"
                onClick={() => handleSort('ticker')}
              >
                Ticker<SortIndicator col="ticker" />
              </th>
              <th
                className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase cursor-pointer hover:text-[#E6EDF3] text-right select-none"
                onClick={() => handleSort('yld')}
              >
                Yld%<SortIndicator col="yld" />
              </th>
              <th
                className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase cursor-pointer hover:text-[#E6EDF3] text-right select-none"
                onClick={() => handleSort('chg')}
              >
                Chg<SortIndicator col="chg" />
              </th>
              <th
                className="py-1 px-2 text-[#9AA4B2] text-[10px] uppercase cursor-pointer hover:text-[#E6EDF3] text-right select-none"
                onClick={() => handleSort('tvl')}
              >
                TVL(M)<SortIndicator col="tvl" />
              </th>
            </tr>
          </thead>
          <tbody className="font-mono text-[11px]">
            {sorted.map((fund) => {
              const isSelected = selectedTicker === fund.ticker
              const isPos = fund.chg >= 0
              return (
                <tr
                  key={fund.ticker}
                  className={`cursor-pointer border-b border-[#1E2530]/30 hover:bg-[#1E2530] transition-colors ${isSelected ? 'bg-[#FFFFFF]/10' : ''}`}
                  onClick={() => onSelectTicker(fund.ticker)}
                >
                  <td className={`py-1.5 px-2 font-bold ${isSelected ? 'text-[#FFFFFF]' : 'text-[#E6EDF3]'}`}>
                    {fund.ticker}
                    {isSelected && <span className="ml-1 text-[#FFC107]">◀</span>}
                  </td>
                  <td className="py-1.5 px-2 text-right text-[#E6EDF3]">
                    {fund.yld.toFixed(2)}
                  </td>
                  <td className={`py-1.5 px-2 text-right ${isPos ? 'text-[#00C853]' : 'text-[#FF5252]'}`}>
                    {isPos ? '+' : ''}{fund.chg.toFixed(2)}
                  </td>
                  <td className="py-1.5 px-2 text-right text-[#E6EDF3]">
                    {fund.tvl.toFixed(1)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
