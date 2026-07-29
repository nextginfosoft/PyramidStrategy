import { useState, useEffect } from 'react'
import { configApi } from '../../services/api'
import type { StrategyConfig } from '../../types'

interface LevelHistoryModalProps {
  isOpen: boolean
  onClose: () => void
  onSelectConfig?: (config: StrategyConfig) => void
}

export function LevelHistoryModal({ isOpen, onClose, onSelectConfig }: LevelHistoryModalProps) {
  const [history, setHistory] = useState<StrategyConfig[]>([])
  const [loading, setLoading] = useState(false)
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [expandedId, setExpandedId] = useState<number | null>(null)

  const fetchHistory = async () => {
    setLoading(true)
    try {
      const data = await configApi.getStrategyHistory({
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
        limit: 100,
      })
      setHistory(data)
    } catch (err) {
      console.error('Failed to fetch level history:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleExportCSV = () => {
    if (history.length === 0) return
    const headers = [
      'Config ID',
      'Created At',
      'R3',
      'R2',
      'R1',
      'S1',
      'S2',
      'S3',
      'Lot Size',
      'Target Pts',
      'SL Pts',
      'Paper Trade',
      'Squareoff Time',
    ]

    const rows = history.map((cfg) => [
      cfg.id,
      cfg.created_at ? new Date(cfg.created_at).toLocaleString('en-IN') : '',
      cfg.r3,
      cfg.r2,
      cfg.r1,
      cfg.s1,
      cfg.s2,
      cfg.s3,
      cfg.lot_size,
      cfg.target_points,
      cfg.sl_points,
      cfg.paper_trade ? 'Yes' : 'No',
      cfg.squareoff_time || '',
    ])

    const csvContent = [
      headers.join(','),
      ...rows.map((r) => r.map((val) => `"${val}"`).join(',')),
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `strategy_level_history_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  useEffect(() => {
    if (isOpen) {
      fetchHistory()
    }
  }, [isOpen])

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-4xl bg-navy-900 border border-navy-700 rounded-xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-navy-800 bg-navy-950/60">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Strategy Level History</h2>
              <p className="text-xs text-navy-300">Track, filter, and export historical level configurations</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-navy-400 hover:text-white hover:bg-navy-800 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Filters and Actions Bar */}
        <div className="px-6 py-3 border-b border-navy-800 bg-navy-900/50 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-navy-950 border border-navy-800 rounded-lg px-3 py-1.5 text-xs">
              <span className="text-navy-400">From:</span>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => setFromDate(e.target.value)}
                className="bg-transparent text-white focus:outline-none text-xs"
              />
            </div>
            <div className="flex items-center gap-2 bg-navy-950 border border-navy-800 rounded-lg px-3 py-1.5 text-xs">
              <span className="text-navy-400">To:</span>
              <input
                type="date"
                value={toDate}
                onChange={(e) => setToDate(e.target.value)}
                className="bg-transparent text-white focus:outline-none text-xs"
              />
            </div>
            <button
              onClick={fetchHistory}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors disabled:opacity-50"
            >
              <svg className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Filter
            </button>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleExportCSV}
              disabled={history.length === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Export CSV
            </button>
            <div className="text-xs text-navy-400 font-mono">
              Total: <span className="text-white font-bold">{history.length}</span>
            </div>
          </div>
        </div>

        {/* Content Table */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {loading && history.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-navy-400 gap-2">
              <svg className="w-6 h-6 animate-spin text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span className="text-sm">Loading level history...</span>
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-12 text-navy-400 text-sm">
              No historical level configurations found for the selected range.
            </div>
          ) : (
            <div className="space-y-2">
              {history.map((cfg, idx) => {
                const isExpanded = expandedId === cfg.id
                const isLatest = idx === 0

                return (
                  <div
                    key={cfg.id}
                    className={`border rounded-lg transition-all ${
                      isLatest
                        ? 'border-blue-500/40 bg-blue-950/20'
                        : 'border-navy-800 bg-navy-950/40 hover:border-navy-700'
                    }`}
                  >
                    {/* Header Row */}
                    <div
                      onClick={() => setExpandedId(isExpanded ? null : cfg.id)}
                      className="flex items-center justify-between px-4 py-3 cursor-pointer select-none"
                    >
                      <div className="flex items-center gap-3">
                        {isLatest ? (
                          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                            ✓ Active
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[11px] font-mono text-navy-400 bg-navy-800">
                            #{cfg.id}
                          </span>
                        )}
                        <span className="text-xs text-navy-300 font-mono">
                          {cfg.created_at
                            ? new Date(cfg.created_at).toLocaleString('en-IN', {
                                dateStyle: 'medium',
                                timeStyle: 'short',
                              })
                            : 'N/A'}
                        </span>
                      </div>

                      {/* Level Badges */}
                      <div className="flex items-center gap-2 text-xs font-mono">
                        <span className="text-red-400 bg-red-950/40 border border-red-900/40 px-2 py-0.5 rounded">
                          R3: {cfg.r3}
                        </span>
                        <span className="text-red-300 bg-red-950/20 border border-red-950 px-2 py-0.5 rounded">
                          R1: {cfg.r1}
                        </span>
                        <span className="text-emerald-300 bg-emerald-950/20 border border-emerald-950 px-2 py-0.5 rounded">
                          S1: {cfg.s1}
                        </span>
                        <span className="text-emerald-400 bg-emerald-950/40 border border-emerald-900/40 px-2 py-0.5 rounded">
                          S3: {cfg.s3}
                        </span>
                        <svg
                          className={`w-4 h-4 text-navy-400 transition-transform ${
                            isExpanded ? 'rotate-180' : ''
                          }`}
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </div>
                    </div>

                    {/* Detailed Expanded Section */}
                    {isExpanded && (
                      <div className="px-4 pb-4 pt-2 border-t border-navy-800/60 bg-navy-900/40 text-xs">
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                          <div className="p-2.5 rounded bg-navy-950 border border-navy-850">
                            <div className="text-navy-400 mb-1">Resistance Levels</div>
                            <div className="font-mono text-red-400 space-y-0.5">
                              <div>R3: {cfg.r3}</div>
                              <div>R2: {cfg.r2}</div>
                              <div>R1: {cfg.r1}</div>
                            </div>
                          </div>
                          <div className="p-2.5 rounded bg-navy-950 border border-navy-850">
                            <div className="text-navy-400 mb-1">Support Levels</div>
                            <div className="font-mono text-emerald-400 space-y-0.5">
                              <div>S1: {cfg.s1}</div>
                              <div>S2: {cfg.s2}</div>
                              <div>S3: {cfg.s3}</div>
                            </div>
                          </div>
                          <div className="p-2.5 rounded bg-navy-950 border border-navy-850">
                            <div className="text-navy-400 mb-1">Trade Parameters</div>
                            <div className="space-y-0.5 font-mono text-navy-200">
                              <div>Lot Size: {cfg.lot_size}</div>
                              <div>Target: {cfg.target_points} pts</div>
                              <div>Stop Loss: {cfg.sl_points} pts</div>
                            </div>
                          </div>
                          <div className="p-2.5 rounded bg-navy-950 border border-navy-850">
                            <div className="text-navy-400 mb-1">Execution Mode</div>
                            <div className="space-y-0.5 font-mono text-navy-200">
                              <div>
                                Mode:{' '}
                                <span className={cfg.paper_trade ? 'text-amber-400' : 'text-emerald-400'}>
                                  {cfg.paper_trade ? 'Paper Trade' : 'Live Trading'}
                                </span>
                              </div>
                              <div>Squareoff: {cfg.squareoff_time}</div>
                            </div>
                          </div>
                        </div>

                        {onSelectConfig && (
                          <div className="flex justify-end pt-1">
                            <button
                              onClick={() => {
                                onSelectConfig(cfg)
                                onClose()
                              }}
                              className="px-3 py-1.5 rounded bg-blue-600/80 hover:bg-blue-600 text-white font-medium transition-colors"
                            >
                              Load as Active Config
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
