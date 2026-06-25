import { useState, useEffect, useMemo } from 'react'
import { tradesApi, configApi } from '../../services/api'

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
    const loadConfigAndFetch = async () => {
      setLoading(true)
      try {
        const cfg = await configApi.getStrategy()
        let initialEndTime = '12:30'
        if (cfg && cfg.squareoff_time) {
          const [hStr, mStr] = cfg.squareoff_time.split(':')
          const h = parseInt(hStr, 10)
          const m = parseInt(mStr, 10)
          const dateObj = new Date()
          dateObj.setHours(h, m, 0, 0)
          dateObj.setHours(dateObj.getHours() + 1)
          const eh = String(dateObj.getHours()).padStart(2, '0')
          const em = String(dateObj.getMinutes()).padStart(2, '0')
          initialEndTime = `${eh}:${em}`
        }
        setEndTime(initialEndTime)
        const data = await tradesApi.getLogs(startTime, initialEndTime)
        setLogs(data.logs)
      } catch (err) {
        console.error(err)
        fetchLogs()
      } finally {
        setLoading(false)
      }
    }
    loadConfigAndFetch()
  }, [])

  const parsedLogs = useMemo(() => {
    return logs.map((line, index) => {
      const parts = line.split('|');
      if (parts.length >= 3) {
        const timestampPart = parts[0].trim();
        const levelPart = parts[1].trim();
        const remaining = parts.slice(2).join('|').trim();
        
        const dashIdx = remaining.indexOf(' - ');
        if (dashIdx !== -1) {
          const modulePart = remaining.substring(0, dashIdx).trim();
          const messagePart = remaining.substring(dashIdx + 3).trim();
          
          let moduleClean = modulePart.split(':')[0].replace('app.core.', '').replace('app.services.', '');
          
          if (moduleClean === 'order_manager') moduleClean = '🛒 Orders';
          else if (moduleClean === 'state_machine') moduleClean = '⚙️ Logic';
          else if (moduleClean === 'strategy_engine') moduleClean = '🧠 Engine';
          else if (moduleClean === 'safety_checks') moduleClean = '🛡️ Safety';
          else if (moduleClean === 'option_selector') moduleClean = '🎯 Selector';
          
          const timePart = timestampPart.includes(' ') ? timestampPart.split(' ')[1] : timestampPart;
          
          return {
            id: index,
            time: timePart,
            level: levelPart,
            module: moduleClean,
            message: messagePart,
            isParsed: true,
            raw: line
          };
        }
      }
      return {
        id: index,
        time: '—',
        level: line.includes('| ERROR |') ? 'ERROR' : line.includes('| WARNING |') ? 'WARNING' : 'INFO',
        module: '💻 System',
        message: line,
        isParsed: false,
        raw: line
      };
    });
  }, [logs]);

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-navy-950 border border-navy-700 rounded-xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-navy-700 bg-navy-900/50">
          <div className="flex items-center gap-2">
            <span className="text-orange-500 text-lg">📄</span>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">Live Trade Log</h2>
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
            * Recommended duration: 09:00 to {endTime}
          </div>
        </div>

        {/* Logs content (Table format) */}
        <div className="flex-1 p-4 overflow-y-auto bg-navy-950 scrollbar-thin">
          {error && <div className="text-red-400 text-center py-4">{error}</div>}
          {loading && parsedLogs.length === 0 && (
            <div className="text-navy-300 text-center py-8">Fetching logs...</div>
          )}
          {!loading && parsedLogs.length === 0 && !error && (
            <div className="text-navy-300 text-center py-8">No logs found for the selected time range.</div>
          )}
          {parsedLogs.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 bg-navy-900 border-b border-navy-700 z-10 text-[10px] uppercase tracking-wider text-navy-300">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold w-24">Time</th>
                    <th className="py-2.5 px-2 font-semibold w-20">Level</th>
                    <th className="py-2.5 px-2 font-semibold w-28">Component</th>
                    <th className="py-2.5 px-3 font-semibold">Activity Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-navy-850/60 font-mono text-[11px]">
                  {parsedLogs.map((log) => {
                    let levelClass = '';
                    if (log.level === 'ERROR') levelClass = 'bg-red-950/40 text-red-400 border border-red-500/20';
                    else if (log.level === 'WARNING') levelClass = 'bg-yellow-950/40 text-yellow-400 border border-yellow-500/20';
                    else levelClass = 'bg-green-950/40 text-green-400 border border-green-500/20';

                    return (
                      <tr key={log.id} className="hover:bg-navy-900/40 transition-colors">
                        <td className="py-2 px-3 text-navy-300 whitespace-nowrap align-top">{log.time}</td>
                        <td className="py-2 px-2 align-top">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-extrabold uppercase leading-none ${levelClass}`}>
                            {log.level}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-navy-200 font-semibold whitespace-nowrap align-top">{log.module}</td>
                        <td className="py-2 px-3 text-navy-100 whitespace-pre-wrap break-all align-top">{log.message}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
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
