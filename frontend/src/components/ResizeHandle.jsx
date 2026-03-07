import React from 'react'
import { PanelResizeHandle } from 'react-resizable-panels'

export function ResizeHandle() {
  return (
    <PanelResizeHandle className="w-1 flex items-center justify-center group">
      <div className="w-px h-full bg-[#1E2530] group-hover:bg-[#FFC107]/50 group-data-[resize-handle-active]:bg-[#FFC107] transition-colors" />
    </PanelResizeHandle>
  )
}

export function HorizontalResizeHandle() {
  return (
    <PanelResizeHandle className="h-1 flex items-center justify-center group">
      <div className="h-px w-full bg-[#1E2530] group-hover:bg-[#FFC107]/50 group-data-[resize-handle-active]:bg-[#FFC107] transition-colors" />
    </PanelResizeHandle>
  )
}
