import { useState, useEffect } from 'react'
import { tradesApi } from '../../services/api'

export function LiveLogModal({ onClose }: { onClose: () => void }) {
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('12:30')
  const [logs, setLogs] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchLogs = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await tradesApi.getLogs(startTime, endTime)
      setLogs(data.logs)
    } catch (err: any) {
      console.error(err)
      setError('Failed to fetch live logs.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLogs()
  }, [])

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-gray-950 border border-gray-800 rounded-xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800 bg-gray-900/50">
          <div className="flex items-center gap-2">
            <span className="text-orange-500 text-lg">📄</span>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">Live Trade & System Logs</h2>
          </div>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-white transition-colors p-1.5 hover:bg-gray-800 rounded-lg text-lg flex items-center justify-center"
          >
            ✕
          </button>
        </div>

        {/* Filters */}
        <div className="p-4 border-b border-gray-800 bg-gray-900/20 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400 font-bold">Start Time:</label>
            <input
              type="time"
              className="bg-gray-900 border border-gray-800 focus:border-orange-500 rounded px-2.5 py-1 text-xs text-white"
              value={startTime}
              onChange={e => setStartTime(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-400 font-bold">End Time:</label>
            <input
              type="time"
              className="bg-gray-900 border border-gray-800 focus:border-orange-500 rounded px-2.5 py-1 text-xs text-white"
              value={endTime}
              onChange={e => setEndTime(e.target.value)}
            />
          </div>
          <button
            onClick={fetchLogs}
            disabled={loading}
            className="px-4 py-1.5 bg-orange-700 hover:bg-orange-600 disabled:opacity-40 rounded text-xs font-bold text-white transition-all shadow-md"
          >
            {loading ? 'Filtering...' : 'Apply Filter'}
          </button>
          <div className="text-[10px] text-gray-500">
            * Recommended duration: 09:00 to 12:30
          </div>
        </div>

        {/* Logs content */}
        <div className="flex-1 p-4 overflow-y-auto bg-gray-950 font-mono text-[11px] text-gray-300 space-y-1">
          {error && <div className="text-red-400 text-center py-4">{error}</div>}
          {loading && logs.length === 0 && (
            <div className="text-gray-500 text-center py-8">Fetching logs...</div>
          )}
          {!loading && logs.length === 0 && !error && (
            <div className="text-gray-500 text-center py-8">No logs found for the selected time range.</div>
          )}
          {logs.map((line, index) => {
            let color = 'text-gray-300'
            if (line.includes('| ERROR |')) color = 'text-red-400 font-semibold'
            else if (line.includes('| WARNING |')) color = 'text-yellow-400'
            else if (line.includes('| INFO |')) color = 'text-green-400'
            return (
              <div key={index} className={`whitespace-pre-wrap break-all py-0.5 ${color}`}>
                {line}
              </div>
            )
          })}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-gray-800 bg-gray-900/50 flex items-center justify-end gap-2 text-xs text-gray-500">
          <button
            onClick={fetchLogs}
            className="px-3 py-1.5 bg-gray-850 hover:bg-gray-800 text-gray-300 rounded border border-gray-700 font-semibold"
          >
            🔄 Refresh
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded font-bold"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
