import React, { useState, useRef } from 'react'
import { mockFunds } from '../lib/mockData.js'
import { PanelCommandLine } from './PanelCommandLine.jsx'
import {
  usePanelFontSize,
  panelRootStyle, panelHeaderStyle, panelTitleStyle, panelSubtitleStyle,
  panelFooterStyle, colHeaderStyle, dataFontSize,
  COLOR_GREEN, COLOR_AMBER, COLOR_RED, TEXT_WHITE, TEXT_MUTED, TEXT_PRIMARY,
} from '../lib/panelTheme.js'

export function FundCard({ funds, selectedTicker, onSelectTicker }) {
  const [sortCol, setSortCol] = useState('tvl')
  const [sortDir, setSortDir] = useState('desc')

  const allFunds = funds && funds.length > 0 ? funds : mockFunds
  const [watchlist, setWatchlist] = useState(allFunds)

  const containerRef = useRef(null)
  const fontSize = usePanelFontSize(containerRef)
  const df = dataFontSize(fontSize)

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
      <span style={{ color: COLOR_AMBER }}>{sortDir === 'asc' ? ' ▲' : ' ▼'}</span>
    ) : null

  const chStyle = colHeaderStyle(fontSize)

  return (
    <div ref={containerRef} style={panelRootStyle()}>
      {/* Header */}
      <div style={panelHeaderStyle()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: `${fontSize * 0.35}px ${fontSize * 0.9}px` }}>
          <h2 style={panelTitleStyle(fontSize)}>
            MONITOR{' '}
            <span style={panelSubtitleStyle(fontSize)}>WATCHLIST</span>
          </h2>
          <span style={{ ...chStyle, color: TEXT_MUTED }}>ADD · DEL</span>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="ADD WTGXX  or  DEL BUIDL" />
      </div>

      {/* Table */}
      <div style={{ flex: 1, overflowY: 'auto' }} className="scrollbar-hide">
        <table style={{ width: '100%', borderCollapse: 'collapse', whiteSpace: 'nowrap' }}>
          <thead style={{ position: 'sticky', top: 0, backgroundColor: '#0B0F14', zIndex: 10, borderBottom: '1px solid #1E2530' }}>
            <tr>
              {[
                { col: 'ticker', label: 'Ticker', align: 'left' },
                { col: 'yld',    label: 'Yld%',   align: 'right' },
                { col: 'chg',    label: 'Chg',    align: 'right' },
                { col: 'tvl',    label: 'TVL(M)', align: 'right' },
              ].map(({ col, label, align }) => (
                <th
                  key={col}
                  onClick={() => handleSort(col)}
                  style={{ ...chStyle, padding: `${fontSize * 0.4}px ${fontSize * 0.9}px`, textAlign: align, cursor: 'pointer', userSelect: 'none' }}
                  onMouseEnter={(e) => e.currentTarget.style.color = TEXT_PRIMARY}
                  onMouseLeave={(e) => e.currentTarget.style.color = chStyle.color}
                >
                  {label}<SortIndicator col={col} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((fund) => {
              const isNull = fund.yld === 0 && fund.tvl === 0
              const isPos = fund.chg >= 0
              return (
                <tr
                  key={fund.ticker}
                  onClick={() => onSelectTicker(fund.ticker)}
                  style={{ cursor: 'pointer', borderBottom: '1px solid rgba(30,37,48,0.3)', fontSize: df }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#1E2530'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  <td style={{ padding: `${fontSize * 0.5}px ${fontSize * 0.9}px`, color: isNull ? TEXT_MUTED : TEXT_PRIMARY, fontWeight: 700 }}>
                    {fund.ticker}
                  </td>
                  <td style={{ padding: `${fontSize * 0.5}px ${fontSize * 0.9}px`, color: TEXT_PRIMARY, textAlign: 'right' }}>
                    {isNull ? '--' : fund.yld.toFixed(2)}
                  </td>
                  <td style={{ padding: `${fontSize * 0.5}px ${fontSize * 0.9}px`, color: isNull ? TEXT_MUTED : isPos ? COLOR_GREEN : COLOR_RED, textAlign: 'right' }}>
                    {isNull ? '--' : `${isPos ? '+' : ''}${fund.chg.toFixed(2)}`}
                  </td>
                  <td style={{ padding: `${fontSize * 0.5}px ${fontSize * 0.9}px`, color: TEXT_PRIMARY, textAlign: 'right' }}>
                    {isNull ? '--' : fund.tvl.toFixed(1)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div style={panelFooterStyle(fontSize)}>
        <span>RWAPIPE · RWA.XYZ</span>
        <span>MON WATCHLIST</span>
      </div>
    </div>
  )
}
