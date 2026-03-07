export const mockFunds = [
  { ticker: 'MMFXX', tvl: 42.5, yld: 4.95, chg: 0.12, vol: 1.2, name: 'Main Money Market Fund' },
  { ticker: 'XMTD',  tvl: 18.2, yld: 4.10, chg: -0.05, vol: 0.45, name: 'Treasury Note Token' },
  { ticker: 'USTY',  tvl: 105.8, yld: 5.05, chg: 0.22, vol: 8.5, name: 'US Gov Yield TKN' },
  { ticker: 'CORP',  tvl: 8.4,  yld: 5.80, chg: 0.45, vol: 0.12, name: 'Corporate Grade A' },
  { ticker: 'RPLZ',  tvl: 2.1,  yld: 3.50, chg: -0.15, vol: 0.8, name: 'Ripple Repo Reserve' },
  { ticker: 'GOVX',  tvl: 54.3, yld: 4.65, chg: 0.08, vol: 3.2, name: 'Govx Multi-Strategy' },
  { ticker: 'FEDF',  tvl: 32.1, yld: 5.25, chg: 0.31, vol: 2.1, name: 'Federal Fund Proxy' },
  { ticker: 'MUNY',  tvl: 9.8,  yld: 3.80, chg: 0.02, vol: 0.05, name: 'Muni Equivalent' },
]

export const mockFund = {
  mpt_issuance_id: 'MOCK001',
  supply: 1_000_000,
  nav: 1.0002,
  yield_7d: 4.95,
  tvl_usd: 42_500_000,
  recent_txns: [
    { hash: 'abc123', type: 'MPTokenIssuanceCreate', amount: 100000, timestamp: '2026-03-06T10:00:00Z' },
    { hash: 'def456', type: 'Payment', amount: 5000, timestamp: '2026-03-06T10:05:00Z' },
  ],
}

export const mockYieldForecast = {
  data: [
    { time: '08:00', actual: 4.82, predicted: 4.80, anomaly: false },
    { time: '08:30', actual: 4.83, predicted: 4.82, anomaly: false },
    { time: '09:00', actual: 4.85, predicted: 4.84, anomaly: false },
    { time: '09:30', actual: 4.86, predicted: 4.86, anomaly: false },
    { time: '10:00', actual: 5.10, predicted: 4.88, anomaly: true },
    { time: '10:30', actual: 4.90, predicted: 4.90, anomaly: false },
    { time: '11:00', actual: 4.91, predicted: 4.92, anomaly: false },
    { time: '11:30', actual: 4.93, predicted: 4.94, anomaly: false },
    { time: '12:00', actual: 4.95, predicted: 4.95, anomaly: false },
    { time: '12:30', actual: 4.94, predicted: 4.96, anomaly: false },
    { time: '13:00', actual: 4.95, predicted: 4.97, anomaly: false },
  ],
}

export const mockAnomalies = [
  { timestamp: '2026-03-06T10:45:02Z', type: 'volume_spike',    severity: 'Critical', description: 'Unexpected large withdrawal from MMFXX escrow' },
  { timestamp: '2026-03-06T10:41:15Z', type: 'forecast_var',    severity: 'Warning',  description: 'High prediction variance detected in yield forecast' },
  { timestamp: '2026-03-06T10:22:04Z', type: 'oracle_update',   severity: 'Info',     description: 'Scheduled XRPL oracle update successful' },
  { timestamp: '2026-03-06T10:05:33Z', type: 'volume_high',     severity: 'Warning',  description: 'Transfer volume exceeds 30-day moving average' },
  { timestamp: '2026-03-06T09:50:11Z', type: 'escrow_create',   severity: 'Info',     description: 'New escrow lock created for 500,000 MMFXX' },
  { timestamp: '2026-03-06T09:12:45Z', type: 'latency',         severity: 'Info',     description: 'Minor latency observed in validator nodes' },
  { timestamp: '2026-03-06T08:30:00Z', type: 'yield_drop',      severity: 'Warning',  description: 'Yield drop predicted within next 4 hours' },
]

export const mockRiskScores = [
  {
    fund_id: 'MMFXX',
    score: 32,
    components: { yield_volatility: 0.02, tvl_size: 42_500_000, kyc_required: true,  min_investment: 1000,  network_count: 3 },
  },
  {
    fund_id: 'MMFXX',
    nw_stress: 32,
    vol_index: 78,
  },
]

export const mockEscrow = [
  { escrow_id: 'ESC-001', subscriber: 'rPjU...9Kx', amount: 1_200_000, finish_after: '2026-03-07T10:00:00Z', status: 'pending' },
  { escrow_id: 'ESC-002', subscriber: 'rQZc...5Wt', amount:   500_000, finish_after: '2026-03-07T14:00:00Z', status: 'pending' },
  { escrow_id: 'ESC-003', subscriber: 'rUa2...bNq', amount:   100_000, finish_after: '2026-03-07T10:00:00Z', status: 'pending' },
  { escrow_id: 'ESC-004', subscriber: 'rLb9...3Po', amount:    50_000, finish_after: '2026-03-06T22:00:00Z', status: 'maturing' },
  { escrow_id: 'ESC-005', subscriber: 'rHx8...2Xl', amount:   250_000, finish_after: '2026-03-08T10:00:00Z', status: 'pending' },
]

export const mockEvents = [
  { id: '1', time: '10:46:12', type: 'TRANSFER',      amount: '500,000',   account: 'rPjU...9Kx' },
  { id: '2', time: '10:45:02', type: 'ESCROW_FINISH',  amount: '1,200,000', account: 'rQZc...5Wt' },
  { id: '3', time: '10:44:18', type: 'PAYMENT',        amount: '10,000',    account: 'rLb9...3Po' },
  { id: '4', time: '10:41:05', type: 'TRANSFER',       amount: '25,000',    account: 'rPjU...9Kx' },
  { id: '5', time: '10:39:55', type: 'ESCROW_CREATE',  amount: '100,000',   account: 'rUa2...bNq' },
  { id: '6', time: '10:35:10', type: 'TRUST_SET',      amount: '-',         account: 'rHx8...2Xl' },
  { id: '7', time: '10:30:22', type: 'PAYMENT',        amount: '5,500',     account: 'rTq9...1Cz' },
  { id: '8', time: '10:28:44', type: 'TRANSFER',       amount: '80,000',    account: 'rMv7...4Hj' },
]
