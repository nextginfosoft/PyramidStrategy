import { create } from 'zustand'
import type { StrategyStatus, Trade, WSMessage } from '../types'

interface StrategyStore {
  status: StrategyStatus | null
  trades: Trade[]
  aiSuggestions: Array<{ text: string; side: string; event: string; ts: Date }>
  wsConnected: boolean
  setStatus: (s: StrategyStatus) => void
  addTrade: (t: Trade) => void
  setTrades: (trades: Trade[]) => void
  addAISuggestion: (s: string, side: string, event: string) => void
  setWsConnected: (v: boolean) => void
  handleWSMessage: (msg: WSMessage) => void
  clearAISuggestions: () => void
}

export const useStrategyStore = create<StrategyStore>((set, get) => ({
  status: null,
  trades: [],
  aiSuggestions: [],
  wsConnected: false,

  setStatus: (s) => set({ status: s }),
  addTrade: (t) => set((st) => ({ trades: [t, ...st.trades].slice(0, 100) })),
  setTrades: (trades) => set({ trades }),
  setWsConnected: (v) => set({ wsConnected: v }),
  clearAISuggestions: () => set({ aiSuggestions: [], trades: [] }),

  addAISuggestion: (text, side, event) =>
    set((st) => ({
      aiSuggestions: [
        { text, side, event, ts: new Date() },
        ...st.aiSuggestions,
      ].slice(0, 10),
    })),

  handleWSMessage: (msg) => {
    const store = get()
    if (msg.type === 'strategy_status') {
      store.setStatus(msg.data)
    } else if (msg.type === 'trade_event') {
      // Refresh trades list via react-query instead
    } else if (msg.type === 'ai_suggestion') {
      store.addAISuggestion(msg.data.suggestion, msg.data.side, msg.data.event)
    }
  },
}))
