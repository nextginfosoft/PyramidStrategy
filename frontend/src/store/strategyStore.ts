import { create } from 'zustand'
import type { StrategyStatus, Trade, WSMessage } from '../types'
import { useGamificationStore } from './gamificationStore'
import {
  DEFAULT_UNDERLYING,
  isUnderlying,
  loadStoredUnderlying,
  storeUnderlying,
  type Underlying,
} from '../utils/instruments'

interface StrategyStore {
  /** Instrument the whole UI is currently showing */
  underlying: Underlying
  /** Latest live status per instrument (filled by WS + REST) */
  statuses: Partial<Record<Underlying, StrategyStatus>>
  /** Status of the selected instrument (kept in sync with `statuses`) */
  status: StrategyStatus | null
  trades: Trade[]
  aiSuggestions: Array<{ text: string; side: string; event: string; ts: Date }>
  wsConnected: boolean
  selectUnderlying: (u: Underlying) => void
  setStatus: (s: StrategyStatus, underlying?: Underlying) => void
  addTrade: (t: Trade) => void
  setTrades: (trades: Trade[]) => void
  addAISuggestion: (s: string, side: string, event: string) => void
  setWsConnected: (v: boolean) => void
  handleWSMessage: (msg: WSMessage) => void
  clearAISuggestions: () => void
}

/** Messages/statuses without a tag come from the NIFTY engine (backward compatible). */
const tagOf = (raw: unknown): Underlying => (isUnderlying(raw) ? raw : DEFAULT_UNDERLYING)

const initialUnderlying = loadStoredUnderlying()

export const useStrategyStore = create<StrategyStore>((set, get) => ({
  underlying: initialUnderlying,
  statuses: {},
  status: null,
  trades: [],
  aiSuggestions: [],
  wsConnected: false,

  selectUnderlying: (u) => {
    storeUnderlying(u)
    set((st) => ({ underlying: u, status: st.statuses[u] ?? null, trades: [] }))
  },

  setStatus: (s, underlying) => {
    const u = tagOf(underlying ?? s.underlying)
    set((st) => ({
      statuses: { ...st.statuses, [u]: s },
      // only the selected instrument drives the visible status
      status: u === st.underlying ? s : st.status,
    }))
  },
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
      store.setStatus(msg.data, tagOf(msg.underlying ?? msg.data?.underlying))
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
