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

const STORAGE_KEY = 'mmf-terminal-slots'

function loadSlots() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved)
  } catch {}
  return DEFAULT_DYNAMIC_SLOTS
}

function SlotContent({ slot, data }) {
  const { escrow, anomalies, events, wsConnected, riskScores } = data
  switch (slot.type) {
    case 'ESCROW':
      return <EscrowPanel selectedTicker={slot.ticker} escrow={escrow} />
    case 'ALERT':
      return <AlertFeed selectedTicker={slot.ticker} anomalies={anomalies} />
    case 'EVENTS':
      return <EventStream selectedTicker={slot.ticker} events={events} wsConnected={wsConnected} />
    case 'RISK':
      return <RiskGauge selectedTicker={slot.ticker} riskScores={riskScores} />
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
        return { msg: 'MAX 4 PANELS — DEL ONE FIRST', ok: false }
      }
      setDynamicSlots(prev => [...prev, { id: makeSlotId(), type, ticker }])
      return { msg: `${label} [${ticker}] ADDED`, ok: true }
    }

    if (action === 'DEL') {
      const idx = dynamicSlots.findIndex(s => s.type === type && s.ticker === ticker)
      if (idx === -1) {
        return { msg: `${label} [${ticker}] NOT FOUND`, ok: false }
      }
      setDynamicSlots(prev => prev.filter((_, i) => i !== idx))
      return { msg: `${label} [${ticker}] REMOVED`, ok: true }
    }

    return { msg: 'UNKNOWN ERROR', ok: false }
  }

  // Layout: top row = [MON, YF, dynamicSlots[0]]
  //         bottom row = [dynamicSlots[1], dynamicSlots[2], dynamicSlots[3]]
  const slot0 = dynamicSlots[0] ?? null
  const bottomSlots = dynamicSlots.slice(1)
  const hasBottom = bottomSlots.length > 0

  const topTypes = ['MONITOR', 'YIELD', ...(slot0 ? [slot0.type] : [])]
  const topSizes = computeRowSizes(topTypes)

  const bottomTypes = bottomSlots.map(s => s.type)
  const bottomSizes = computeRowSizes(bottomTypes)

  // Keys force PanelGroup remount so defaultSizes apply after slot changes
  const topKey = `top-${slot0?.id ?? 'none'}`
  const bottomKey = `bottom-${bottomSlots.map(s => s.id).join('-')}`
  const vertKey = `vert-${hasBottom}`

  const panelData = { escrow, anomalies, events, wsConnected, riskScores }

  return (
    <div className="h-screen bg-[#000000] text-[#E6EDF3] font-sans flex flex-col overflow-hidden" style={{ fontFamily: 'system-ui, Arial, sans-serif' }}>
      <TerminalHeader alertCount={criticalCount} onPanelCommand={handlePanelCommand} />

      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <span className="text-[#9AA4B2] font-mono text-sm animate-pulse">CONNECTING TO XRPL TESTNET...</span>
        </div>
      )}

      {error && !loading && (
        <div className="px-4 py-1 bg-[#FF5252]/10 border-b border-[#FF5252]/30 text-[#FF5252] text-xs font-mono">
          WARN: API unreachable — displaying mock data ({error})
        </div>
      )}

      <main className="flex-1 overflow-hidden p-1 gap-1">
        <PanelGroup key={vertKey} direction="vertical" className="h-full w-full" style={{ gap: '4px' }}>

          {/* Top row — MON + YF always present, plus dynamic slot 0 */}
          <Panel defaultSize={hasBottom ? 55 : 100} minSize={30}>
            <PanelGroup key={topKey} direction="horizontal" className="h-full" style={{ gap: '4px' }}>

              <Panel defaultSize={topSizes[0]} minSize={15}>
                <FundCard funds={funds} selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
              </Panel>

              <ResizeHandle />

              <Panel defaultSize={topSizes[1]} minSize={25}>
                <YieldChart yieldForecast={yieldForecast} />
              </Panel>

              {slot0 && (
                <>
                  <ResizeHandle />
                  <Panel defaultSize={topSizes[2]} minSize={15}>
                    <SlotContent slot={slot0} data={panelData} />
                  </Panel>
                </>
              )}

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
                        <SlotContent slot={slot} data={panelData} />
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
