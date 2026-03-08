import { useState, useEffect } from 'react'

// ── Color tokens ─────────────────────────────────────────────────────────────
export const PANEL_BG   = '#0B0F14'
export const YIELD_BG   = '#000000'
export const HEADER_BG  = '#11161D'
export const BORDER     = '#1E2530'
export const TEXT_WHITE = '#FFFFFF'
export const TEXT_PRIMARY = '#E6EDF3'
export const TEXT_MUTED   = '#9AA4B2'
export const TEXT_MUTED_DIM = 'rgba(154,164,178,0.55)'
export const COLOR_GREEN = '#00C853'
export const COLOR_AMBER = '#FFC107'
export const COLOR_RED   = '#FF5252'
export const COLOR_BLUE  = '#42A5F5'

// ── Font size hook ────────────────────────────────────────────────────────────
// Maps container width [200, 700] → font size [9, 14]
export function usePanelFontSize(containerRef) {
  const [fontSize, setFontSize] = useState(11)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width
      const clamped = Math.max(200, Math.min(700, w))
      const scaled = 9 + ((clamped - 200) / 500) * 5
      setFontSize(Math.round(scaled * 10) / 10)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  return fontSize
}

// ── Style helpers ─────────────────────────────────────────────────────────────

/** Root panel container style */
export function panelRootStyle(bg = PANEL_BG) {
  return {
    background: bg,
    fontFamily: 'monospace',
    border: `1px solid ${BORDER}`,
    height: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  }
}

/** Header wrapper (title row above PanelCommandLine) */
export function panelHeaderStyle() {
  return {
    background: HEADER_BG,
    borderBottom: `1px solid ${BORDER}`,
    display: 'flex',
    flexDirection: 'column',
    flexShrink: 0,
  }
}

/** Panel title text */
export function panelTitleStyle(fontSize) {
  return {
    color: TEXT_WHITE,
    fontFamily: 'monospace',
    fontWeight: 700,
    fontSize: Math.max(9, fontSize * 0.9),
    letterSpacing: '0.1em',
    textTransform: 'uppercase',
  }
}

/** Muted subtitle / accent text in the title row */
export function panelSubtitleStyle(fontSize) {
  return {
    color: TEXT_MUTED,
    fontWeight: 400,
    fontFamily: 'monospace',
    fontSize: Math.max(9, fontSize * 0.9),
    letterSpacing: '0.1em',
  }
}

/** Column-header row text */
export function colHeaderStyle(fontSize) {
  return {
    color: TEXT_MUTED_DIM,
    fontFamily: 'monospace',
    fontSize: Math.max(8, fontSize * 0.82),
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    fontWeight: 400,
  }
}

/** Footer bar style */
export function panelFooterStyle(fontSize) {
  return {
    background: 'rgba(17,22,29,0.6)',
    borderTop: `1px solid ${BORDER}`,
    fontFamily: 'monospace',
    fontSize: Math.max(8, fontSize * 0.82),
    color: TEXT_MUTED,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: `${Math.max(3, fontSize * 0.35)}px ${Math.max(6, fontSize * 0.9)}px`,
    flexShrink: 0,
  }
}

/** Data row font size */
export function dataFontSize(fontSize) {
  return Math.max(9, fontSize * 0.95)
}
