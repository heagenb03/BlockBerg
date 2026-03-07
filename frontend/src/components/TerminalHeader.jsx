import React, { useEffect, useRef, useState } from 'react'
import { Activity, Clock } from 'lucide-react'

export function TerminalHeader({ alertCount = 0, onPanelCommand }) {
  const [time, setTime] = useState(new Date())
  const [inputValue, setInputValue] = useState('')
  const [feedback, setFeedback] = useState(null) // { msg, ok }
  const inputRef = useRef(null)

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      const cmd = inputValue.trim().toUpperCase()
      if (!cmd || !onPanelCommand) return
      const result = onPanelCommand(cmd)
      setInputValue('')
      if (result) {
        setFeedback(result)
        setTimeout(() => setFeedback(null), 3000)
      }
    } else if (e.key === 'Escape') {
      setInputValue('')
      setFeedback(null)
      inputRef.current?.blur()
    }
  }

  return (
    <div className="h-10 bg-[#000000] border-b border-[#1E2530] flex items-center justify-between px-4 text-[#E6EDF3] shrink-0 select-none">

      {/* Left — brand */}
      <div className="flex items-center space-x-2 shrink-0">
        <Activity className="w-4 h-4 text-[#FFFFFF]" />
        <h1 className="text-sm font-bold tracking-widest text-[#FFFFFF] uppercase">MMFBlerg</h1>
      </div>

      {/* Center — panel command input */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="flex items-center gap-1.5 border border-[#1E2530] bg-[#0B0F14] px-3 py-1 rounded w-full max-w-lg">
          <span className="text-[#FFC107] font-mono text-xs select-none shrink-0">{'>'}</span>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="ADD ES MMFXX  ·  DEL RG BUIDL  ·  HELP"
            className="flex-1 bg-transparent border-none outline-none text-[#E6EDF3] font-mono text-xs placeholder:text-[#9AA4B2]/35 focus:ring-0 min-w-0"
            spellCheck="false"
            autoComplete="off"
          />
          {feedback && (
            <span
              className={`text-[11px] font-mono shrink-0 whitespace-nowrap tracking-wide ${
                feedback.ok ? 'text-[#00C853]' : 'text-[#FF5252]'
              }`}
            >
              {feedback.msg}
            </span>
          )}
        </div>
      </div>

      {/* Right — clock */}
      <div className="flex items-center space-x-4 text-xs font-mono shrink-0">
        <div className="w-px h-3 bg-[#1E2530]" />
        <div className="flex items-center space-x-1.5 text-[#FFFFFF]">
          <Clock className="w-3.5 h-3.5" />
          <span>{time.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
        </div>
      </div>

    </div>
  )
}
