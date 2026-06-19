import { useQuery } from '@tanstack/react-query'
import { useStrategyStore } from '../../store/strategyStore'
import { aiApi } from '../../services/api'
import { format } from 'date-fns'

interface ApiSuggestion {
  id: number
  trade_date: string
  event: string
  side: string | null
  level: string | null
  nifty_ltp: number | null
  provider: string
  suggestion: string
  created_at: string
}

export function AIObserver() {
  const wsSuggestions = useStrategyStore((s) => s.aiSuggestions)

  // Also poll DB for persisted suggestions (catches startup + missed WS events)
  const { data: apiSuggestions } = useQuery<ApiSuggestion[]>({
    queryKey: ['ai-suggestions'],
    queryFn: () => aiApi.getSuggestions(20),
    refetchInterval: 15_000,  // refresh every 15s
    retry: false,
  })

  // Merge: WS suggestions are live (shown first), API suggestions fill history
  const hasWs = wsSuggestions.length > 0
  const hasApi = apiSuggestions && apiSuggestions.length > 0

  if (!hasWs && !hasApi) {
    return (
      <div className="text-navy-300 text-sm text-center py-6">
        🤖 AI Observer watching...
        <br />
        <span className="text-xs text-navy-400">Suggestions appear after trade events</span>
      </div>
    )
  }

  return (
    <div className="space-y-2 max-h-56 overflow-auto">
      {/* Live WS suggestions (newest real-time) */}
      {wsSuggestions.map((s, i) => (
        <div key={`ws-${i}`} className="bg-navy-800 border border-blue-800/60 rounded p-2">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-blue-400 font-bold">🤖 AI</span>
            {s.side && (
              <span className={`text-xs font-bold ${s.side === 'CE' ? 'text-green-400' : 'text-red-400'}`}>
                {s.side}
              </span>
            )}
            <span className="text-xs text-navy-300">{s.event}</span>
            <span className="text-xs text-navy-400 ml-auto">
              {format(s.ts, 'HH:mm:ss')}
            </span>
          </div>
          <p className="text-xs text-navy-100 leading-relaxed">{s.text}</p>
        </div>
      ))}

      {/* DB suggestions (persisted, shown when no WS data or as history) */}
      {!hasWs && apiSuggestions?.map((s) => (
        <div key={`api-${s.id}`} className="bg-navy-800 border border-navy-700/60 rounded p-2">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-blue-400 font-bold">🤖 {s.provider?.toUpperCase() ?? 'AI'}</span>
            {s.side && (
              <span className={`text-xs font-bold ${s.side === 'CE' ? 'text-green-400' : 'text-red-400'}`}>
                {s.side}
              </span>
            )}
            <span className="text-xs text-navy-300">{s.event}</span>
            {s.nifty_ltp && (
              <span className="text-xs text-navy-400">NIFTY: {s.nifty_ltp}</span>
            )}
            <span className="text-xs text-navy-400 ml-auto">
              {s.created_at ? format(new Date(s.created_at), 'HH:mm') : ''}
            </span>
          </div>
          <p className="text-xs text-navy-100 leading-relaxed">{s.suggestion}</p>
        </div>
      ))}
    </div>
  )
}
