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
  saveApiKey: (payload: { provider: string; api_key?: string; api_secret?: string }) =>
    api.post('/config/api-keys', payload).then(r => r.data),
}

export const tradesApi = {
  getToday: (): Promise<Trade[]> => api.get('/trades/today').then(r => r.data),
  getHistory: (params?: { from_date?: string; to_date?: string; side?: string }) =>
    api.get('/trades/history', { params }).then(r => r.data),
  getTodayPnl: () => api.get('/trades/pnl/today').then(r => r.data),
  getPnlHistory: () => api.get('/trades/pnl/history').then(r => r.data),
}

export const healthApi = {
  check: () => api.get('/health').then(r => r.data),
}
