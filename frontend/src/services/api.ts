import axios from 'axios'
import type { StrategyConfig, Trade } from '../types'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
})

export const strategyApi = {
  getStatus: () => api.get('/strategy/status').then(r => r.data),
  start: () => api.post('/strategy/start').then(r => r.data),
  stop: () => api.post('/strategy/stop').then(r => r.data),
  reset: () => api.post('/strategy/reset-daily').then(r => r.data),
  simulateTick: (price: number) =>
    api.post(`/strategy/simulate-tick?nifty_price=${price}`).then(r => r.data),
}

export const configApi = {
  getStrategy: (): Promise<StrategyConfig> => api.get('/config/strategy').then(r => r.data),
  saveStrategy: (cfg: Omit<StrategyConfig, 'id' | 'is_active'>) =>
    api.post('/config/strategy', cfg).then(r => r.data),
  getApiKeys: () => api.get('/config/api-keys').then(r => r.data),
  saveApiKey: (payload: {
    provider: string
    api_key?: string
    api_secret?: string
    extra_config?: Record<string, unknown>
  }) =>
    api.post('/config/api-keys', payload).then(r => r.data),
}

export const tradesApi = {
  getToday: (): Promise<Trade[]> => api.get('/trades/today').then(r => r.data),
  getHistory: (params?: { from_date?: string; to_date?: string; side?: string; limit?: number }): Promise<Trade[]> =>
    api.get('/trades/history', { params }).then(r => r.data),
  getTodayPnl: () => api.get('/trades/pnl/today').then(r => r.data),
  getPnlHistory: () => api.get('/trades/pnl/history').then(r => r.data),
  exportTrades: (): Promise<Blob> => api.get('/trades/export', { responseType: 'blob' }).then(r => r.data),
  exportLogs: (): Promise<Blob> => api.get('/trades/logs/export', { responseType: 'blob' }).then(r => r.data),
  getLogs: (start_time?: string, end_time?: string): Promise<{ logs: string[] }> =>
    api.get('/trades/logs', { params: { start_time, end_time } }).then(r => r.data),
  getReports: (): Promise<{ reports: any[] }> => api.get('/trades/reports').then(r => r.data),
  downloadReport: (filename: string): Promise<Blob> =>
    api.get(`/trades/reports/download`, { params: { filename }, responseType: 'blob' }).then(r => r.data),
  triggerReport: (reportDate?: string) =>
    api.post('/trades/reports/trigger-daily', null, { params: { report_date: reportDate } }).then(r => r.data),
}

export const healthApi = {
  check: () => api.get('/health').then(r => r.data),
}

export const kiteApi = {
  getLoginUrl: () => api.get('/auth/kite/login').then(r => r.data),
  getStatus: () => api.get('/auth/kite/status').then(r => r.data),
  startFeed: () => api.post('/auth/kite/start-feed').then(r => r.data),
  stopFeed: () => api.post('/auth/kite/stop-feed').then(r => r.data),
  validateToken: () => api.post('/auth/kite/validate').then(r => r.data),
  loadInstruments: () => api.post('/auth/kite/load-instruments').then(r => r.data),
  logout: () => api.post('/auth/kite/logout').then(r => r.data),
}

export const aiApi = {
  getSuggestions: (limit = 20) =>
    api.get(`/ai/suggestions?limit=${limit}`).then(r => r.data),
  getHistory: (days = 7) =>
    api.get(`/ai/suggestions/history?days=${days}`).then(r => r.data),
  testConnection: () => api.post('/ai/test').then(r => r.data),
  reload: () => api.post('/ai/reload').then(r => r.data),
  getStatus: () => api.get('/ai/status').then(r => r.data),
  getPreMarketBrief: () => api.get('/ai/brief/pre-market').then(r => r.data),
  getPostSessionReview: () => api.get('/ai/brief/post-session').then(r => r.data),
}

export const backtestApi = {
  run: (payload: {
    start_date: string
    end_date: string
    config: {
      r1: number
      r2: number
      r3: number
      s1: number
      s2: number
      s3: number
      lot_size: number
      target_points: number
      sl_points: number
      name?: string
    }
    compare_configs?: Array<{
      r1: number
      r2: number
      r3: number
      s1: number
      s2: number
      s3: number
      lot_size: number
      target_points: number
      sl_points: number
      name?: string
    }>
  }) => api.post('/backtest', payload).then(r => r.data),
}

export const sessionApi = {
  register: (username: string, password: string) =>
    api.post('/session/register', { username, password }).then(r => r.data),
  login: (username: string, password: string) =>
    api.post('/session/login', { username, password }).then(r => r.data),
  logout: () => api.post('/session/logout').then(r => r.data),
  me: () => api.get('/session/me').then(r => r.data),
  check: () => api.get('/session/check').then(r => r.data),
  setToken: (token: string) => {
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    localStorage.setItem('pyramid_token', token)
  },
  clearToken: () => {
    delete api.defaults.headers.common['Authorization']
    localStorage.removeItem('pyramid_token')
  },
  restoreToken: () => {
    const t = localStorage.getItem('pyramid_token')
    if (t) api.defaults.headers.common['Authorization'] = `Bearer ${t}`
    return t
  },
}

export const notificationApi = {
  test: () => api.post('/notifications/test').then(r => r.data),
  testWhatsapp: () => api.post('/notifications/whatsapp/test').then(r => r.data),
  getStatus: () => api.get('/notifications/status').then(r => r.data),
  reload: () => api.post('/notifications/reload').then(r => r.data),
}

// Restore token on module load
sessionApi.restoreToken()
