import React, { useState, useRef } from 'react'

export function PanelCommandLine({ onCommand, placeholder = 'e.g. GO MMFXX' }) {
  const [value, setValue] = useState('')
  const [feedback, setFeedback] = useState(null)
  const inputRef = useRef(null)

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      const cmd = value.trim().toUpperCase()
      if (cmd) {
        const result = onCommand(cmd)
        setValue('')
        if (result) {
          setFeedback(result)
          setTimeout(() => setFeedback(null), 2500)
        }
      }
    } else if (e.key === 'Escape') {
      setValue('')
      inputRef.current?.blur()
    }
  }

  return (
    <div className="flex items-center gap-1.5 px-2 py-0.5 border-t border-[#1E2530]/60 bg-[#000000]">
      <span className="text-[#FFC107] font-mono text-[10px] select-none">{'>'}</span>
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="flex-1 bg-transparent border-none outline-none text-[#E6EDF3] font-mono text-[10px] placeholder:text-[#9AA4B2]/35 focus:ring-0 min-w-0"
        spellCheck="false"
        autoComplete="off"
      />
      {feedback && (
        <span className="text-[10px] font-mono text-[#00C853] shrink-0 tracking-wide">{feedback}</span>
      )}
    </div>
  )
}
