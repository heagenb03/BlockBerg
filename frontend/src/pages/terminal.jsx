import React, { useState, useEffect } from 'react'
import { Panel, PanelGroup } from 'react-resizable-panels'
import { TerminalHeader } from '../components/TerminalHeader.jsx'
import { FundCard } from '../components/FundCard.jsx'
import { YieldChart } from '../components/YieldChart.jsx'
import { EscrowPanel } from '../components/EscrowPanel.jsx'
import { AlertFeed } from '../components/AlertFeed.jsx'
import { EventStream } from '../components/EventStream.jsx'
import { RiskGauge } from '../components/RiskGauge.jsx'
import { ResizeHandle, HorizontalResizeHandle } from '../components/ResizeHandle.jsx'
import { useTerminalData } from '../hooks/useTerminalData.js'
import {
  DEFAULT_DYNAMIC_SLOTS,
  HELP_TEXT,
  MAX_DYNAMIC_SLOTS,
  PANEL_LABELS,
  computeRowSizes,
  makeSlotId,
  parseCommand,
} from '../lib/panelSlots.js'

const STORAGE_KEY = 'mmf-terminal-slots-v2'

function loadSlots() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) {
      const slots = JSON.parse(saved)
      // Migrate RISK slots that predate multi-ticker support
      return slots.map((s) =>
        s.type === 'RISK' && !s.tickers ? { ...s, tickers: [s.ticker] } : s
      )
    }
  } catch {}
  return DEFAULT_DYNAMIC_SLOTS
}

function SlotContent({ slot, data, onTickerChange, onTickersChange }) {
  const { escrow, anomalies, events, wsConnected, riskScores } = data
  switch (slot.type) {
    case 'ESCROW':
      return <EscrowPanel selectedTicker={slot.ticker} escrow={escrow} onTickerChange={onTickerChange} />
    case 'ALERT':
      return <AlertFeed selectedTicker={slot.ticker} anomalies={anomalies} onTickerChange={onTickerChange} />
    case 'EVENTS':
      return <EventStream selectedTicker={slot.ticker} events={events} wsConnected={wsConnected} onTickerChange={onTickerChange} />
    case 'RISK':
      return (
        <RiskGauge
          tickers={slot.tickers ?? [slot.ticker]}
          riskScores={riskScores}
          onTickersChange={onTickersChange}
        />
      )
    default:
      return null
  }
}

export default function Terminal() {
  const [selectedTicker, setSelectedTicker] = useState('MMFXX')
  const [dynamicSlots, setDynamicSlots] = useState(loadSlots)

  const { funds, yieldForecast, anomalies, riskScores, escrow, events, wsConnected, loading, error } = useTerminalData()

  const criticalCount = anomalies.filter((a) => a.severity === 'Critical').length

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(dynamicSlots))
  }, [dynamicSlots])

  const handlePanelCommand = (cmd) => {
    const parsed = parseCommand(cmd)

    if (parsed.action === 'HELP') {
      return { msg: HELP_TEXT, ok: true }
    }

    if (parsed.error) {
      return { msg: parsed.error, ok: false }
    }

    const { action, type, ticker } = parsed
    const label = PANEL_LABELS[type]

    if (action === 'ADD') {
      if (dynamicSlots.length >= MAX_DYNAMIC_SLOTS) {
        return { msg: 'MAX 6 PANELS — DEL ONE FIRST', ok: false }
      }
      const newSlot =
        type === 'RISK'
          ? { id: makeSlotId(), type, ticker, tickers: [ticker] }
          : { id: makeSlotId(), type, ticker }
      setDynamicSlots(prev => [...prev, newSlot])
      return { msg: `${label} [${ticker}] ADDED`, ok: true }
    }

    if (action === 'DEL') {
      if (type === 'RISK') {
        const idx = dynamicSlots.findIndex(
          (s) => s.type === 'RISK' && (s.tickers ?? [s.ticker]).includes(ticker)
        )
        if (idx === -1) return { msg: `${label} [${ticker}] NOT FOUND`, ok: false }
        const slotTickers = dynamicSlots[idx].tickers ?? [dynamicSlots[idx].ticker]
        if (slotTickers.length > 1) {
          const newTickers = slotTickers.filter((t) => t !== ticker)
          setDynamicSlots(prev =>
            prev.map((s, i) =>
              i === idx ? { ...s, tickers: newTickers, ticker: newTickers[0] } : s
            )
          )
          return { msg: `${label} [${ticker}] REMOVED FROM PANEL`, ok: true }
        }
        setDynamicSlots(prev => prev.filter((_, i) => i !== idx))
        return { msg: `${label} [${ticker}] REMOVED`, ok: true }
      }

      const idx = dynamicSlots.findIndex(s => s.type === type && s.ticker === ticker)
      if (idx === -1) {
        return { msg: `${label} [${ticker}] NOT FOUND`, ok: false }
      }
      setDynamicSlots(prev => prev.filter((_, i) => i !== idx))
      return { msg: `${label} [${ticker}] REMOVED`, ok: true }
    }

    return { msg: 'UNKNOWN ERROR', ok: false }
  }

  // Layout: top row    = [MON, YF, dynamicSlots[0], dynamicSlots[1]]
  //         bottom row = [dynamicSlots[2], dynamicSlots[3], dynamicSlots[4], dynamicSlots[5]]
  const topDynamic = dynamicSlots.slice(0, 2)
  const bottomSlots = dynamicSlots.slice(2)
  const hasBottom = bottomSlots.length > 0

  const TOP_FIXED_COUNT = 2 // MON + YF
  const topTypes = ['MONITOR', 'YIELD', ...topDynamic.map(s => s.type)]
  const topSizes = computeRowSizes(topTypes)

  const bottomTypes = bottomSlots.map(s => s.type)
  const bottomSizes = computeRowSizes(bottomTypes)

  // Keys force PanelGroup remount so defaultSizes apply after slot changes
  const topKey = `top-${topDynamic.map(s => s.id).join('-')}`
  const bottomKey = `bottom-${bottomSlots.map(s => s.id).join('-')}`
  const vertKey = `vert-${hasBottom}`

  const handleSlotTickerChange = (slotId, newTicker) => {
    setDynamicSlots(prev => prev.map(s => s.id === slotId ? { ...s, ticker: newTicker } : s))
  }

  const handleSlotTickersChange = (slotId, newTickers) => {
    setDynamicSlots(prev =>
      prev.map(s =>
        s.id === slotId ? { ...s, tickers: newTickers, ticker: newTickers[0] } : s
      )
    )
  }

  const panelData = { escrow, anomalies, events, wsConnected, riskScores }

  return (
    <div className="h-screen bg-[#000000] text-[#E6EDF3] font-sans flex flex-col overflow-hidden" style={{ fontFamily: 'system-ui, Arial, sans-serif' }}>
      <TerminalHeader alertCount={criticalCount} onPanelCommand={handlePanelCommand} />

      {error && !loading && (
        <div className="px-4 py-1 bg-[#FF5252]/10 border-b border-[#FF5252]/30 text-[#FF5252] text-xs font-mono">
          WARN: API unreachable — displaying mock data ({error})
        </div>
      )}

      {loading ? (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-[#9AA4B2] font-mono text-sm animate-pulse">CONNECTING TO XRPL TESTNET...</span>
        </div>
      ) : null}

      <main className={`flex-1 overflow-hidden p-1 gap-1${loading ? ' hidden' : ''}`}>
        <PanelGroup key={vertKey} direction="vertical" className="h-full w-full" style={{ gap: '4px' }}>

          {/* Top row — MON + YF always present, plus dynamic slots 0–1 */}
          <Panel defaultSize={hasBottom ? 55 : 100} minSize={30}>
            <PanelGroup key={topKey} direction="horizontal" className="h-full" style={{ gap: '4px' }}>

              <Panel defaultSize={topSizes[0]} minSize={15}>
                <FundCard funds={funds} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
              </Panel>

              <ResizeHandle />

              <Panel defaultSize={topSizes[1]} minSize={25}>
                <YieldChart yieldForecast={yieldForecast} />
              </Panel>

              {topDynamic.map((slot, idx) => (
                <React.Fragment key={slot.id}>
                  <ResizeHandle />
                  <Panel defaultSize={topSizes[TOP_FIXED_COUNT + idx]} minSize={15}>
                    <SlotContent
                      slot={slot}
                      data={panelData}
                      onTickerChange={(t) => handleSlotTickerChange(slot.id, t)}
                      onTickersChange={(ts) => handleSlotTickersChange(slot.id, ts)}
                    />
                  </Panel>
                </React.Fragment>
              ))}

            </PanelGroup>
          </Panel>

          {/* Bottom row — 0–3 dynamic slots; hidden when empty */}
          {hasBottom && (
            <>
              <HorizontalResizeHandle />
              <Panel defaultSize={45} minSize={20}>
                <PanelGroup key={bottomKey} direction="horizontal" className="h-full" style={{ gap: '4px' }}>
                  {bottomSlots.map((slot, idx) => (
                    <React.Fragment key={slot.id}>
                      {idx > 0 && <ResizeHandle />}
                      <Panel defaultSize={bottomSizes[idx]} minSize={15}>
                        <SlotContent
                          slot={slot}
                          data={panelData}
                          onTickerChange={(t) => handleSlotTickerChange(slot.id, t)}
                          onTickersChange={(ts) => handleSlotTickersChange(slot.id, ts)}
                        />
                      </Panel>
                    </React.Fragment>
                  ))}
                </PanelGroup>
              </Panel>
            </>
          )}

        </PanelGroup>
      </main>
    </div>
  )
}
