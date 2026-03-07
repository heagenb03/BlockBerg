import React, { useState } from 'react'
import { mockFunds } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'

export function FundCard({ funds, selectedTicker, onSelectTicker }) {
  const [sortCol, setSortCol] = useState('tvl')
  const [sortDir, setSortDir] = useState('desc')

  const allFunds = funds && funds.length > 0 ? funds : mockFunds
  const [watchlist, setWatchlist] = useState(allFunds)

  const sorted = [...watchlist].sort((a, b) => {
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

  const handleCommand = (cmd) => {
    const parts = cmd.split(/\s+/)
    const op = parts[0]
    const ticker = parts[1]

    if (!ticker) return 'USAGE: ADD <TICKER> or DEL <TICKER>'

    if (op === 'ADD') {
      if (watchlist.some((f) => f.ticker === ticker)) return `${ticker} ALREADY IN MONITOR`
      const known = allFunds.find((f) => f.ticker === ticker)
      const entry = known ?? { ticker, name: 'UNKNOWN FUND', tvl: 0, yld: 0, chg: 0, vol: 0 }
      setWatchlist((prev) => [...prev, entry])
      return `ADDED ${ticker}`
    }

    if (op === 'DEL') {
      if (!watchlist.some((f) => f.ticker === ticker)) return `${ticker} NOT FOUND`
      setWatchlist((prev) => prev.filter((f) => f.ticker !== ticker))
      return `REMOVED ${ticker}`
    }

    return `UNKNOWN CMD: ${op}`
  }

  const SortIndicator = ({ col }) =>
    sortCol === col ? (
      <span className="text-[#FFC107]">{sortDir === 'asc' ? ' ▲' : ' ▼'}</span>
    ) : null

  return (
    <div className="bg-[#0B0F14] border border-[#1E2530] h-full flex flex-col font-sans">
      <div className="border-b border-[#1E2530] bg-[#11161D] flex flex-col">
        <div className="flex items-center justify-between p-1.5">
          <h2 className="text-[#FFFFFF] font-semibold text-[11px] tracking-wider uppercase">
            MONITOR
          </h2>
          <span className="text-[9px] font-mono text-[#9AA4B2]">ADD · DEL</span>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="ADD WTGXX  or  DEL BUIDL" />
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
              const isNull = fund.yld === 0 && fund.tvl === 0
              const isPos = fund.chg >= 0
              return (
                <tr
                  key={fund.ticker}
                  className="cursor-pointer border-b border-[#1E2530]/30 hover:bg-[#1E2530] transition-colors"
                  onClick={() => onSelectTicker(fund.ticker)}
                >
                  <td className={`py-1.5 px-2 font-bold ${isNull ? 'text-[#9AA4B2]' : 'text-[#E6EDF3]'}`}>
                    {fund.ticker}
                  </td>
                  <td className="py-1.5 px-2 text-right text-[#E6EDF3]">
                    {isNull ? '--' : fund.yld.toFixed(2)}
                  </td>
                  <td className={`py-1.5 px-2 text-right ${isNull ? 'text-[#9AA4B2]' : isPos ? 'text-[#00C853]' : 'text-[#FF5252]'}`}>
                    {isNull ? '--' : `${isPos ? '+' : ''}${fund.chg.toFixed(2)}`}
                  </td>
                  <td className="py-1.5 px-2 text-right text-[#E6EDF3]">
                    {isNull ? '--' : fund.tvl.toFixed(1)}
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
