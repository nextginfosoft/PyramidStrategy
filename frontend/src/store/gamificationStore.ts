import { create } from 'zustand'

export interface MotivationalQuote {
  id: string
  eventType: string
  quote: string
  author: string
  emoji: string
  label: string
  side: string
  level: string
  duration: number
  extra: Record<string, unknown>
  createdAt: number
}

interface GamificationStore {
  currentQuote: MotivationalQuote | null
  quoteHistory: MotivationalQuote[]
  showQuote: (data: {
    eventType: string
    quote: string
    author: string
    emoji: string
    label: string
    side: string
    level: string
    duration: number
    extra: Record<string, unknown>
  }) => void
  dismissQuote: () => void
}

export const useGamificationStore = create<GamificationStore>((set) => ({
  currentQuote: null,
  quoteHistory: [],

  showQuote: (data) => {
    const id = Math.random().toString(36).substring(2, 9)
    const quote: MotivationalQuote = {
      id,
      ...data,
      createdAt: Date.now(),
    }

    set((state) => ({
      currentQuote: quote,
      quoteHistory: [quote, ...state.quoteHistory].slice(0, 50),
    }))

    // Auto-dismiss after duration
    if (data.duration > 0) {
      setTimeout(() => {
        set((state) => {
          // Only dismiss if it's still the same quote
          if (state.currentQuote?.id === id) {
            return { currentQuote: null }
          }
          return state
        })
      }, data.duration)
    }
  },

  dismissQuote: () => set({ currentQuote: null }),
}))
