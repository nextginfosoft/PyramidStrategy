import { create } from 'zustand'
import type { StrategyStatus, Trade, WSMessage } from '../types'
import { useGamificationStore } from './gamificationStore'

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
    } else if (msg.type === 'gamification_event') {
      const d = msg.data
      useGamificationStore.getState().showQuote({
        eventType: d.event_type,
        quote: d.quote,
        author: d.author,
        emoji: d.emoji,
        label: d.label,
        side: d.side,
        level: d.level,
        duration: d.duration,
        extra: d.extra,
      })
    }
  },
}))
