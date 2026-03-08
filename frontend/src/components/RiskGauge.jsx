import React, { useRef, useCallback, useState, useEffect } from 'react'
import { PanelCommandLine } from './PanelCommandLine.jsx'
import {
  usePanelFontSize,
  panelRootStyle, panelHeaderStyle, panelTitleStyle, panelSubtitleStyle,
  panelFooterStyle, colHeaderStyle,
} from '../lib/panelTheme.js'

const MAX_TICKERS = 3

// Column definitions: flex weight determines proportional width
const COLS = [
  { key: 'fund_id',   label: 'FUND',    flex: 1.6, align: 'left'  },
  { key: 'score',     label: 'SCORE',   flex: 1.0, align: 'right', colored: true },
  { key: '_class',    label: 'CLASS',   flex: 1.0, align: 'right' },
  { key: 'nw_stress', label: 'NW STR',  flex: 1.1, align: 'right', colored: true },
  { key: 'vol_index', label: 'VOL IX',  flex: 1.1, align: 'right', colored: true },
  { key: '_yld_vol',  label: 'YLD VOL', flex: 1.3, align: 'right' },
  { key: '_tvl',      label: 'TVL',     flex: 1.0, align: 'right' },
  { key: '_kyc',      label: 'KYC',     flex: 0.7, align: 'right' },
  { key: '_min_inv',  label: 'MIN INV', flex: 1.1, align: 'right' },
  { key: '_nets',     label: 'NETS',    flex: 0.7, align: 'right' },
]

function scoreColor(score) {
  if (score == null) return '#9AA4B2'
  if (score <= 40) return '#00C853'
  if (score <= 70) return '#FFC107'
  return '#FF5252'
}

function scoreClass(score) {
  if (score == null) return '----'
  if (score <= 40) return 'LOW'
  if (score <= 70) return 'MOD'
  return 'HIGH'
}

function fmtTvl(v) {
  if (v == null) return '--'
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `${(v / 1e6).toFixed(0)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return String(v)
}

function fmtMinInv(v) {
  if (v == null) return '--'
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return String(v)
}

function FlashCell({ value, fmt, color, flex, align = 'right' }) {
  const prevRef = useRef(value)
  const [flashing, setFlashing] = useState(false)

  useEffect(() => {
    if (prevRef.current !== value && prevRef.current !== undefined) {
      setFlashing(true)
      const t = setTimeout(() => setFlashing(false), 600)
      prevRef.current = value
      return () => clearTimeout(t)
    }
    prevRef.current = value
  }, [value])

  const display = fmt ? fmt(value) : (value ?? '--')

  return (
    <span
      style={{
        flex,
        color: flashing ? '#FFC107' : (color ?? '#E6EDF3'),
        textAlign: align,
        transition: 'color 0.15s',
        overflow: 'hidden',
        whiteSpace: 'nowrap',
      }}
    >
      {display}
    </span>
  )
}

function RiskRow({ ticker, data, fontSize }) {
  const noData = !data

  const cells = {
    fund_id:   ticker,
    score:     data?.score,
    _class:    scoreClass(data?.score),
    nw_stress: data?.nw_stress,
    vol_index: data?.vol_index,
    _yld_vol:  data?.components?.yield_volatility != null
                 ? data.components.yield_volatility.toFixed(2)
                 : null,
    _tvl:      data?.components?.tvl_size,
    _kyc:      data?.components?.kyc_required != null
                 ? (data.components.kyc_required ? 'Y' : 'N')
                 : null,
    _min_inv:  data?.components?.min_investment,
    _nets:     data?.components?.network_count,
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: `${fontSize * 0.4}px ${fontSize}px`,
        fontFamily: 'monospace',
        fontSize,
        lineHeight: 1.4,
        gap: `${fontSize * 0.8}px`,
        minHeight: fontSize * 2.4,
        cursor: 'default',
      }}
      className="hover:bg-[#11161D]/60 transition-colors border-b border-[#1E2530]/40"
    >
      {/* FUND label */}
      <span style={{ flex: COLS[0].flex, color: '#E6EDF3', fontWeight: 700, overflow: 'hidden', whiteSpace: 'nowrap' }}>
        {ticker}
      </span>

      {noData ? (
        <span style={{ color: 'rgba(154,164,178,0.35)', letterSpacing: '0.1em', fontSize: fontSize * 0.9 }}>
          NO DATA
        </span>
      ) : (
        <>
          <FlashCell value={cells.score}     color={scoreColor(cells.score)}     flex={COLS[1].flex} />
          <span style={{ flex: COLS[2].flex, color: scoreColor(cells.score), textAlign: 'right', overflow: 'hidden', whiteSpace: 'nowrap', fontSize: fontSize * 0.88 }}>
            {cells._class}
          </span>
          <FlashCell value={cells.nw_stress} color={scoreColor(cells.nw_stress)} flex={COLS[3].flex} />
          <FlashCell value={cells.vol_index} color={scoreColor(cells.vol_index)} flex={COLS[4].flex} />
          <FlashCell value={cells._yld_vol}  color="#9AA4B2" flex={COLS[5].flex} />
          <FlashCell value={cells._tvl}      color="#9AA4B2" fmt={fmtTvl}    flex={COLS[6].flex} />
          <span style={{
            flex: COLS[7].flex,
            color: cells._kyc === 'Y' ? '#00C853' : '#9AA4B2',
            textAlign: 'right',
            overflow: 'hidden',
            whiteSpace: 'nowrap',
          }}>
            {cells._kyc ?? '--'}
          </span>
          <FlashCell value={cells._min_inv}  color="#9AA4B2" fmt={fmtMinInv} flex={COLS[8].flex} />
          <FlashCell value={cells._nets}     color="#9AA4B2" flex={COLS[9].flex} />
        </>
      )}
    </div>
  )
}

export function RiskGauge({ tickers, riskScores, onTickersChange }) {
  const scores = riskScores ?? []
  const containerRef = useRef(null)
  const fontSize = usePanelFontSize(containerRef)

  const handleCommand = useCallback((cmd) => {
    const parts = cmd.split(/\s+/)
    const op = parts[0]
    const ticker = parts[1]

    if (!ticker) return 'USAGE: ADD <TICKER> or DEL <TICKER>'

    if (op === 'ADD') {
      if (tickers.includes(ticker)) return `${ticker} ALREADY DISPLAYED`
      if (tickers.length >= MAX_TICKERS) return `MAX ${MAX_TICKERS} TICKERS`
      onTickersChange([...tickers, ticker])
      return `ADDED ${ticker}`
    }

    if (op === 'DEL') {
      if (!tickers.includes(ticker)) return `${ticker} NOT FOUND`
      if (tickers.length === 1) return 'CANNOT REMOVE LAST TICKER'
      onTickersChange(tickers.filter((t) => t !== ticker))
      return `REMOVED ${ticker}`
    }

    return `UNKNOWN CMD: ${op}`
  }, [tickers, onTickersChange])

  const titleTickers =
    tickers.length <= 3
      ? tickers.join(' · ')
      : `${tickers.slice(0, 3).join(' · ')} +${tickers.length - 3}`

  const hdrFontSize = Math.max(8, fontSize * 0.82)
  const colGap = `${fontSize * 0.8}px`

  return (
    <div ref={containerRef} style={panelRootStyle()}>

      {/* Header */}
      <div style={panelHeaderStyle()}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: `${fontSize * 0.35}px ${fontSize * 0.9}px` }}>
          <h2 style={panelTitleStyle(fontSize)}>
            {titleTickers}{' '}
            <span style={panelSubtitleStyle(fontSize)}>RISK MATRIX</span>
          </h2>
          <span style={colHeaderStyle(fontSize)}>ADD · DEL</span>
        </div>
        <PanelCommandLine onCommand={handleCommand} placeholder="ADD BUIDL  or  DEL MMFXX" />
      </div>

      {/* Column headers — mirror row layout exactly */}
      <div
        className="border-b border-[#1E2530] bg-[#0B0F14] shrink-0"
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: `${hdrFontSize * 0.35}px ${fontSize}px`,
          gap: colGap,
          fontSize: hdrFontSize,
        }}
      >
        {COLS.map((col) => (
          <span
            key={col.key}
            style={{
              flex: col.flex,
              color: 'rgba(154,164,178,0.55)',
              textAlign: col.align,
              fontFamily: 'monospace',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              overflow: 'hidden',
              whiteSpace: 'nowrap',
            }}
          >
            {col.label}
          </span>
        ))}
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto scrollbar-hide">
        {tickers.length === 0 ? (
          <div
            className="flex items-center justify-center h-full text-[#9AA4B2]/40 tracking-widest uppercase"
            style={{ fontSize: hdrFontSize }}
          >
            NO TICKERS · ADD &lt;TICKER&gt;
          </div>
        ) : (
          tickers.map((ticker) => {
            const data = scores.find((r) => r.fund_id === ticker) ?? null
            return <RiskRow key={ticker} ticker={ticker} data={data} fontSize={fontSize} />
          })
        )}
      </div>

      {/* Footer legend */}
      <div style={{ ...panelFooterStyle(fontSize), gap: colGap }}>
        {[['LOW', '#00C853', '≤40'], ['MOD', '#FFC107', '≤70'], ['HIGH', '#FF5252', '>70']].map(([label, color, range]) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: '0.3em' }}>
            <span style={{ color, fontFamily: 'monospace' }}>{label}</span>
            <span style={{ color: 'rgba(154,164,178,0.4)', fontFamily: 'monospace' }}>{range}</span>
          </span>
        ))}
        <span style={{ marginLeft: 'auto', color: 'rgba(154,164,178,0.4)', fontFamily: 'monospace' }}>ML/RISK</span>
      </div>
    </div>
  )
}
