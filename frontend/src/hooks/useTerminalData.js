import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { mockFunds, mockFund, mockYieldForecast, mockAnomalies, mockRiskScores, mockEscrow, mockEvents } from '../lib/mockData.js'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const POLL_INTERVAL = 5000
const WS_RECONNECT_DELAY = 3000
const MAX_EVENTS = 50

export function useTerminalData() {
  const [funds, setFunds] = useState(USE_MOCK ? mockFunds : [])
  const [fund, setFund] = useState(USE_MOCK ? mockFund : null)
  const [yieldForecast, setYieldForecast] = useState(USE_MOCK ? mockYieldForecast : null)
  const [anomalies, setAnomalies] = useState(USE_MOCK ? mockAnomalies : [])
  const [riskScores, setRiskScores] = useState(USE_MOCK ? mockRiskScores : [])
  const [escrow, setEscrow] = useState(USE_MOCK ? mockEscrow : [])
  const [events, setEvents] = useState(USE_MOCK ? mockEvents : [])
  const [wsConnected, setWsConnected] = useState(false)
  const [loading, setLoading] = useState(!USE_MOCK)
  const [error, setError] = useState(null)

  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)
  const mountedRef = useRef(true)

  useEffect(() => {
    if (USE_MOCK) return
    mountedRef.current = true

    // HTTP fetch for everything except events (events come via WebSocket)
    const fetchAll = async () => {
      try {
        const [fundsRes, fundRes, forecastRes, scoresRes, escrowRes] = await Promise.all([
          axios.get('/api/funds'),
          axios.get('/api/xrpl/fund'),
          axios.get('/api/ml/yield-forecast'),
          axios.get('/api/ml/risk-scores'),
          axios.get('/api/xrpl/escrow'),
        ])
        setFunds(fundsRes.data)
        setFund(fundRes.data)
        setYieldForecast(forecastRes.data)
        setRiskScores(scoresRes.data)
        setEscrow(escrowRes.data)
        setLoading(false)
      } catch (e) {
        setError(e.message)
        setFunds(mockFunds)
        setLoading(false)
      }
    }

    fetchAll()

    const anomalyInterval = setInterval(async () => {
      try {
        const res = await axios.get('/api/ml/anomalies')
        setAnomalies(res.data)
      } catch {}
    }, POLL_INTERVAL)

    const escrowInterval = setInterval(async () => {
      try {
        const res = await axios.get('/api/xrpl/escrow')
        setEscrow(res.data)
      } catch {}
    }, 15000)

    // WebSocket for live XRPL events
    const connectWs = () => {
      if (!mountedRef.current) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/xrpl/events`)
      wsRef.current = ws

      ws.onopen = () => {
        if (mountedRef.current) setWsConnected(true)
      }

      ws.onmessage = (e) => {
        if (!mountedRef.current) return
        try {
          const event = JSON.parse(e.data)
          setEvents(prev => [event, ...prev].slice(0, MAX_EVENTS))
        } catch {}
      }

      ws.onclose = () => {
        if (!mountedRef.current) return
        setWsConnected(false)
        reconnectTimer.current = setTimeout(connectWs, WS_RECONNECT_DELAY)
      }

      ws.onerror = () => {
        // browser closes the socket automatically after error, onclose handles reconnect
      }
    }

    connectWs()

    return () => {
      mountedRef.current = false
      clearInterval(anomalyInterval)
      clearInterval(escrowInterval)
      clearTimeout(reconnectTimer.current)
      const ws = wsRef.current
      wsRef.current = null
      if (ws) {
        ws.onopen = null
        ws.onclose = null
        ws.onerror = null
        ws.onmessage = null
        if (ws.readyState === WebSocket.OPEN) ws.close()
      }
    }
  }, [])

  return { funds, fund, yieldForecast, anomalies, riskScores, escrow, events, wsConnected, loading, error }
}
