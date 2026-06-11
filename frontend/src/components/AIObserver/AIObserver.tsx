import { useStrategyStore } from '../../store/strategyStore'
import { format } from 'date-fns'

export function AIObserver() {
  const suggestions = useStrategyStore((s) => s.aiSuggestions)

  if (!suggestions.length) {
    return (
      <div className="text-gray-500 text-sm text-center py-6">
        🤖 AI Observer watching...
        <br />
        <span className="text-xs text-gray-600">Suggestions appear after trade events</span>
      </div>
    )
  }

  return (
    <div className="space-y-2 max-h-48 overflow-auto">
      {suggestions.map((s, i) => (
        <div key={i} className="bg-gray-900 border border-gray-700 rounded p-2">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-blue-400 font-bold">🤖 AI</span>
            <span className={`text-xs font-bold ${s.side === 'CE' ? 'text-green-400' : 'text-red-400'}`}>
              {s.side}
            </span>
            <span className="text-xs text-gray-500">{s.event}</span>
            <span className="text-xs text-gray-600 ml-auto">
              {format(s.ts, 'HH:mm:ss')}
            </span>
          </div>
          <p className="text-xs text-gray-300 leading-relaxed">{s.text}</p>
        </div>
      ))}
    </div>
  )
}
