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
      <div className="bg-navy-950 border border-navy-700 rounded-xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-navy-700 bg-navy-900/50">
          <div className="flex items-center gap-2">
            <span className="text-orange-500 text-lg">📄</span>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">Live Trade & System Logs</h2>
          </div>
          <button 
            onClick={onClose} 
            className="text-navy-300 hover:text-white transition-colors p-1.5 hover:bg-navy-800 rounded-lg text-lg flex items-center justify-center"
          >
            ✕
          </button>
        </div>

        {/* Filters */}
        <div className="p-4 border-b border-navy-700 bg-navy-900/20 flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <label className="text-xs text-navy-300 font-bold">Start Time:</label>
            <input
              type="time"
              className="bg-navy-900 border border-navy-700 focus:border-orange-500 rounded px-2.5 py-1 text-xs text-white"
              value={startTime}
              onChange={e => setStartTime(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <label className="text-xs text-navy-300 font-bold">End Time:</label>
            <input
              type="time"
              className="bg-navy-900 border border-navy-700 focus:border-orange-500 rounded px-2.5 py-1 text-xs text-white"
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
          <div className="text-[10px] text-navy-300">
            * Recommended duration: 09:00 to 12:30
          </div>
        </div>

        {/* Logs content */}
        <div className="flex-1 p-4 overflow-y-auto bg-navy-950 font-mono text-[11px] text-navy-100 space-y-1">
          {error && <div className="text-red-400 text-center py-4">{error}</div>}
          {loading && logs.length === 0 && (
            <div className="text-navy-300 text-center py-8">Fetching logs...</div>
          )}
          {!loading && logs.length === 0 && !error && (
            <div className="text-navy-300 text-center py-8">No logs found for the selected time range.</div>
          )}
          {logs.map((line, index) => {
            let color = 'text-navy-100'
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
        <div className="p-3 border-t border-navy-700 bg-navy-900/50 flex items-center justify-end gap-2 text-xs text-navy-300">
          <button
            onClick={fetchLogs}
            className="px-3 py-1.5 bg-navy-800 hover:bg-navy-700 text-navy-200 rounded border border-navy-700 font-semibold transition"
          >
            🔄 Refresh
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-navy-800 hover:bg-navy-700 text-white rounded font-bold border border-navy-700 transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>

  )
}
