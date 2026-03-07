import { useState, useEffect } from 'react'
import axios from 'axios'
import { mockFunds, mockFund, mockYieldForecast, mockAnomalies, mockRiskScores, mockEscrow, mockEvents } from '../lib/mockData.js'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const POLL_INTERVAL = 5000

export function useTerminalData() {
  const [funds, setFunds] = useState(USE_MOCK ? mockFunds : [])
  const [fund, setFund] = useState(USE_MOCK ? mockFund : null)
  const [yieldForecast, setYieldForecast] = useState(USE_MOCK ? mockYieldForecast : null)
  const [anomalies, setAnomalies] = useState(USE_MOCK ? mockAnomalies : [])
  const [riskScores, setRiskScores] = useState(USE_MOCK ? mockRiskScores : [])
  const [escrow, setEscrow] = useState(USE_MOCK ? mockEscrow : [])
  const [events, setEvents] = useState(USE_MOCK ? mockEvents : [])
  const [loading, setLoading] = useState(!USE_MOCK)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (USE_MOCK) return

    const fetchAll = async () => {
      try {
        const [fundsRes, fundRes, forecastRes, scoresRes, escrowRes, eventsRes] = await Promise.all([
          axios.get('/api/funds'),
          axios.get('/api/xrpl/fund'),
          axios.get('/api/ml/yield-forecast'),
          axios.get('/api/ml/risk-scores'),
          axios.get('/api/xrpl/escrow'),
          axios.get('/api/xrpl/events'),
        ])
        setFunds(fundsRes.data)
        setFund(fundRes.data)
        setYieldForecast(forecastRes.data)
        setRiskScores(scoresRes.data)
        setEscrow(escrowRes.data)
        setEvents(eventsRes.data)
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

    return () => clearInterval(anomalyInterval)
  }, [])

  return { funds, fund, yieldForecast, anomalies, riskScores, escrow, events, loading, error }
}
