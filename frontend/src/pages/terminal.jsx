import React, { useState } from 'react'
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

export default function Terminal() {
  const [selectedTicker, setSelectedTicker] = useState('MMFXX')
  const { yieldForecast, anomalies, riskScores, escrow, events, loading, error } = useTerminalData()

  const criticalCount = anomalies.filter((a) => a.severity === 'Critical').length

  return (
    <div className="h-screen bg-[#000000] text-[#E6EDF3] font-sans flex flex-col overflow-hidden" style={{ fontFamily: 'system-ui, Arial, sans-serif' }}>
      <TerminalHeader alertCount={criticalCount} />

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
        <PanelGroup direction="vertical" className="h-full w-full" style={{ gap: '4px' }}>

          {/* Top row */}
          <Panel defaultSize={55} minSize={30}>
            <PanelGroup direction="horizontal" className="h-full" style={{ gap: '4px' }}>

              <Panel defaultSize={25} minSize={15}>
                <FundCard selectedTicker={selectedTicker} onSelectTicker={setSelectedTicker} />
              </Panel>

              <ResizeHandle />

              <Panel defaultSize={50} minSize={30}>
                <YieldChart selectedTicker={selectedTicker} yieldForecast={yieldForecast} />
              </Panel>

              <ResizeHandle />

              <Panel defaultSize={25} minSize={15}>
                <EscrowPanel selectedTicker={selectedTicker} escrow={escrow} />
              </Panel>

            </PanelGroup>
          </Panel>

          <HorizontalResizeHandle />

          {/* Bottom row */}
          <Panel defaultSize={45} minSize={20}>
            <PanelGroup direction="horizontal" className="h-full" style={{ gap: '4px' }}>

              <Panel defaultSize={25} minSize={15}>
                <AlertFeed anomalies={anomalies} />
              </Panel>

              <ResizeHandle />

              <Panel defaultSize={50} minSize={30}>
                <EventStream selectedTicker={selectedTicker} events={events} />
              </Panel>

              <ResizeHandle />

              <Panel defaultSize={25} minSize={15}>
                <RiskGauge selectedTicker={selectedTicker} riskScores={riskScores} />
              </Panel>

            </PanelGroup>
          </Panel>

        </PanelGroup>
      </main>
    </div>
  )
}
