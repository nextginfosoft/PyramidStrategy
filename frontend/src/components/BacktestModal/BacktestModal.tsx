import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { StrategyConfig } from '../../types'
import { configApi, backtestApi } from '../../services/api'
import clsx from 'clsx'
import { useToastStore } from '../../store/toastStore'

interface Props {
  onClose: () => void
}

type BacktestConfig = {
  name: string
  r1: number; r2: number; r3: number
  s1: number; s2: number; s3: number
  lot_size: number
  target_points: number
  sl_points: number
  squareoff_time?: string
}

type BacktestSummary = {
  total_pnl: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  win_rate: number
  average_profit: number
  average_loss: number
  max_drawdown: number
}

type BacktestTrade = {
  date: string
  side: 'CE' | 'PE'
  level: string
  lots: number
  qty: number
  entry_time: string
  entry_price: number
  exit_time: string
  exit_price: number
  exit_reason: string
  pnl: number
}

type BacktestResult = {
  primary: {
    summary: BacktestSummary
    trades: BacktestTrade[]
  }
  comparisons: Array<{
    name: string
    config: BacktestConfig
    summary: BacktestSummary
  }>
}

export function BacktestModal({ onClose }: Props) {
  const addToast = useToastStore(state => state.addToast)
  const { data: cfg } = useQuery<StrategyConfig>({
    queryKey: ['strategy-config'],
    queryFn: () => configApi.getStrategy(),
  })

  // Date range (defaults to last 7 days)
  const [startDate, setStartDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 7)
    return d.toISOString().split('T')[0]
  })
  const [endDate, setEndDate] = useState(() => new Date().toISOString().split('T')[0])

  // Primary Config
  const [primaryConfig, setPrimaryConfig] = useState<BacktestConfig>({
    name: 'Primary Config',
    r1: 24100, r2: 24200, r3: 24300,
    s1: 23900, s2: 23800, s3: 23700,
    lot_size: 75,
    target_points: 20,
    sl_points: 10,
    squareoff_time: '11:30',
  })

  // Comparison Configs
  const [comparisons, setComparisons] = useState<BacktestConfig[]>([])

  // Running states
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Populate config fields when API loads config
  useEffect(() => {
    if (cfg) {
      setPrimaryConfig({
        name: 'Primary Config',
        r1: cfg.r1, r2: cfg.r2, r3: cfg.r3,
        s1: cfg.s1, s2: cfg.s2, s3: cfg.s3,
        lot_size: cfg.lot_size,
        target_points: cfg.target_points,
        sl_points: cfg.sl_points,
        squareoff_time: cfg.squareoff_time ?? '11:30',
      })
    }
  }, [cfg])

  const handleRunBacktest = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await backtestApi.run({
        start_date: startDate,
        end_date: endDate,
        config: primaryConfig,
        compare_configs: comparisons.length > 0 ? comparisons : undefined,
      })
      setResult(data)
    } catch (err: any) {
      console.error(err)
      setError(err.response?.data?.detail || 'Failed to run historical backtest.')
    } finally {
      setLoading(false)
    }
  }

  const handleAddComparison = () => {
    if (comparisons.length >= 2) {
      addToast('You can compare a maximum of 2 alternative configurations.', 'warning')
      return
    }
    setComparisons([
      ...comparisons,
      {
        name: `Config Option ${comparisons.length + 1}`,
        r1: primaryConfig.r1, r2: primaryConfig.r2, r3: primaryConfig.r3,
        s1: primaryConfig.s1, s2: primaryConfig.s2, s3: primaryConfig.s3,
        lot_size: primaryConfig.lot_size,
        target_points: primaryConfig.target_points,
        sl_points: primaryConfig.sl_points,
        squareoff_time: primaryConfig.squareoff_time,
      },
    ])
  }

  const handleRemoveComparison = (idx: number) => {
    setComparisons(comparisons.filter((_, i) => i !== idx))
  }

  const handleUpdateComparison = (idx: number, key: keyof BacktestConfig, val: any) => {
    const updated = [...comparisons]
    updated[idx] = { ...updated[idx], [key]: val }
    setComparisons(updated)
  }

  return (
    <div className="fixed inset-0 bg-black/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-navy-950 border border-navy-700 rounded-xl w-full max-w-5xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-navy-700 bg-navy-900/50">
          <div className="flex items-center gap-2">
            <span className="text-orange-400 text-lg">📊</span>
            <h2 className="text-base font-bold text-white tracking-wide uppercase">Historical Backtesting Module</h2>
          </div>
          <button 
            onClick={onClose} 
            className="text-navy-300 hover:text-white transition-colors p-1.5 hover:bg-navy-800 rounded-lg text-lg flex items-center justify-center"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Controls Panel */}
          <div className="grid grid-cols-12 gap-4 bg-navy-900/40 p-4 border border-navy-800 rounded-xl">
            {/* Left: Date Range + Stats parameters */}
            <div className="col-span-12 md:col-span-4 space-y-3">
              <h3 className="text-xs font-bold text-orange-400 uppercase tracking-wider">Backtest Scope</h3>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <label className="text-[10px] text-navy-300 font-bold uppercase">Start Date</label>
                  <input
                    type="date"
                    className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded px-2.5 py-1.5 text-xs text-white"
                    value={startDate}
                    onChange={e => setStartDate(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-navy-300 font-bold uppercase">End Date</label>
                  <input
                    type="date"
                    className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded px-2.5 py-1.5 text-xs text-white"
                    value={endDate}
                    onChange={e => setEndDate(e.target.value)}
                  />
                </div>
              </div>

              {/* Strategy Parameters (Lot size, target, sl) */}
              <div className="grid grid-cols-3 gap-2 pt-2">
                <div className="space-y-1">
                  <label className="text-[10px] text-navy-300 font-bold uppercase">Lot Size</label>
                  <input
                    type="number"
                    className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded px-2 py-1 text-xs text-white"
                    value={primaryConfig.lot_size}
                    onChange={e => setPrimaryConfig({ ...primaryConfig, lot_size: +e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-navy-300 font-bold uppercase">Target Pts</label>
                  <input
                    type="number"
                    className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded px-2 py-1 text-xs text-white"
                    value={primaryConfig.target_points}
                    onChange={e => setPrimaryConfig({ ...primaryConfig, target_points: +e.target.value })}
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-[10px] text-navy-300 font-bold uppercase">SL Pts</label>
                  <input
                    type="number"
                    className="w-full bg-navy-900 border border-navy-700 focus:border-orange-500 rounded px-2 py-1 text-xs text-white"
                    value={primaryConfig.sl_points}
                    onChange={e => setPrimaryConfig({ ...primaryConfig, sl_points: +e.target.value })}
                  />
                </div>
              </div>
              
              <div className="pt-2">
                <button
                  onClick={handleRunBacktest}
                  disabled={loading}
                  className="w-full py-2 bg-orange-700 hover:bg-orange-600 disabled:opacity-40 text-white rounded font-bold text-xs shadow-md shadow-orange-950/20 transition-all flex items-center justify-center gap-2"
                >
                  {loading ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Replaying Price Feed...
                    </>
                  ) : (
                    '🚀 Run Historical Backtest'
                  )}
                </button>
              </div>
            </div>

            {/* Right: Resistance & Support Levels setup */}
            <div className="col-span-12 md:col-span-8 flex flex-col justify-between">
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <h3 className="text-xs font-bold text-orange-400 uppercase tracking-wider">Primary Configuration Levels</h3>
                </div>
                
                <div className="grid grid-cols-6 gap-2">
                  <div className="space-y-1">
                    <label className="text-[10px] text-navy-300 font-bold uppercase">R3 (PE)</label>
                    <input
                      type="number"
                      className="w-full bg-navy-900 border border-navy-700 rounded px-2 py-1 text-xs text-white"
                      value={primaryConfig.r3}
                      onChange={e => setPrimaryConfig({ ...primaryConfig, r3: +e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-navy-300 font-bold uppercase">R2 (PE)</label>
                    <input
                      type="number"
                      className="w-full bg-navy-900 border border-navy-700 rounded px-2 py-1 text-xs text-white"
                      value={primaryConfig.r2}
                      onChange={e => setPrimaryConfig({ ...primaryConfig, r2: +e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-navy-300 font-bold uppercase">R1 (PE)</label>
                    <input
                      type="number"
                      className="w-full bg-navy-900 border border-navy-700 rounded px-2 py-1 text-xs text-white"
                      value={primaryConfig.r1}
                      onChange={e => setPrimaryConfig({ ...primaryConfig, r1: +e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-navy-300 font-bold uppercase">S1 (CE)</label>
                    <input
                      type="number"
                      className="w-full bg-navy-900 border border-navy-700 rounded px-2 py-1 text-xs text-white"
                      value={primaryConfig.s1}
                      onChange={e => setPrimaryConfig({ ...primaryConfig, s1: +e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-navy-300 font-bold uppercase">S2 (CE)</label>
                    <input
                      type="number"
                      className="w-full bg-navy-900 border border-navy-700 rounded px-2 py-1 text-xs text-white"
                      value={primaryConfig.s2}
                      onChange={e => setPrimaryConfig({ ...primaryConfig, s2: +e.target.value })}
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] text-navy-300 font-bold uppercase">S3 (CE)</label>
                    <input
                      type="number"
                      className="w-full bg-navy-900 border border-navy-700 rounded px-2 py-1 text-xs text-white"
                      value={primaryConfig.s3}
                      onChange={e => setPrimaryConfig({ ...primaryConfig, s3: +e.target.value })}
                    />
                  </div>
                </div>
              </div>

              {/* Add Comparison Config action */}
              <div className="pt-4 border-t border-navy-800/60 mt-3 flex justify-between items-center">
                <span className="text-[11px] text-navy-300">Compare with alternate setups to analyze optimal configuration:</span>
                <button
                  onClick={handleAddComparison}
                  className="px-3 py-1 bg-navy-800 hover:bg-navy-700 text-orange-400 border border-navy-700 rounded text-xs font-bold transition flex items-center gap-1"
                >
                  ➕ Add Comparison Config ({comparisons.length}/2)
                </button>
              </div>
            </div>
          </div>

          {/* Alternative Config Inputs */}
          {comparisons.length > 0 && (
            <div className="space-y-3 bg-navy-900/20 p-4 border border-navy-800/80 rounded-xl">
              <h4 className="text-xs font-bold text-orange-400 uppercase tracking-wider">Comparison Configurations</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {comparisons.map((c, idx) => (
                  <div key={idx} className="bg-navy-950 border border-navy-800 p-3 rounded-lg relative space-y-2">
                    <button
                      onClick={() => handleRemoveComparison(idx)}
                      className="absolute top-2 right-2 text-[10px] bg-red-950/40 text-red-400 px-1.5 py-0.5 rounded border border-red-900 hover:bg-red-900 hover:text-white"
                    >
                      Remove
                    </button>
                    
                    <div className="flex gap-2 items-center mb-1">
                      <input
                        type="text"
                        className="bg-transparent text-xs font-bold text-white border-b border-navy-700 focus:border-orange-500 focus:outline-none py-0.5"
                        value={c.name}
                        onChange={e => handleUpdateComparison(idx, 'name', e.target.value)}
                      />
                    </div>

                    <div className="grid grid-cols-3 gap-1">
                      <div className="space-y-0.5">
                        <label className="text-[9px] text-navy-300">R3</label>
                        <input
                          type="number"
                          className="w-full bg-navy-900 border border-navy-800 rounded px-1.5 py-0.5 text-xs text-white"
                          value={c.r3}
                          onChange={e => handleUpdateComparison(idx, 'r3', +e.target.value)}
                        />
                      </div>
                      <div className="space-y-0.5">
                        <label className="text-[9px] text-navy-300">R2</label>
                        <input
                          type="number"
                          className="w-full bg-navy-900 border border-navy-800 rounded px-1.5 py-0.5 text-xs text-white"
                          value={c.r2}
                          onChange={e => handleUpdateComparison(idx, 'r2', +e.target.value)}
                        />
                      </div>
                      <div className="space-y-0.5">
                        <label className="text-[9px] text-navy-300">R1</label>
                        <input
                          type="number"
                          className="w-full bg-navy-900 border border-navy-800 rounded px-1.5 py-0.5 text-xs text-white"
                          value={c.r1}
                          onChange={e => handleUpdateComparison(idx, 'r1', +e.target.value)}
                        />
                      </div>
                    </div>
                    
                    <div className="grid grid-cols-3 gap-1">
                      <div className="space-y-0.5">
                        <label className="text-[9px] text-navy-300">S1</label>
                        <input
                          type="number"
                          className="w-full bg-navy-900 border border-navy-800 rounded px-1.5 py-0.5 text-xs text-white"
                          value={c.s1}
                          onChange={e => handleUpdateComparison(idx, 's1', +e.target.value)}
                        />
                      </div>
                      <div className="space-y-0.5">
                        <label className="text-[9px] text-navy-300">S2</label>
                        <input
                          type="number"
                          className="w-full bg-navy-900 border border-navy-800 rounded px-1.5 py-0.5 text-xs text-white"
                          value={c.s2}
                          onChange={e => handleUpdateComparison(idx, 's2', +e.target.value)}
                        />
                      </div>
                      <div className="space-y-0.5">
                        <label className="text-[9px] text-navy-300">S3</label>
                        <input
                          type="number"
                          className="w-full bg-navy-900 border border-navy-800 rounded px-1.5 py-0.5 text-xs text-white"
                          value={c.s3}
                          onChange={e => handleUpdateComparison(idx, 's3', +e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-950/40 border border-red-800 text-red-300 rounded-lg text-xs font-semibold text-center">
              ⚠️ Backtesting Error: {error}
            </div>
          )}

          {/* Results Display */}
          {result && (
            <div className="space-y-4 pt-2 border-t border-navy-800">
              {/* Stats Cards */}
              <div className="grid grid-cols-4 gap-3">
                <div className="bg-navy-900 border border-navy-800 p-3 rounded-lg">
                  <div className="text-[10px] text-navy-300 font-bold uppercase">Total Net Profit</div>
                  <div className={clsx("text-lg font-bold font-mono mt-1", 
                    result.primary.summary.total_pnl > 0 ? "text-green-400" : result.primary.summary.total_pnl < 0 ? "text-red-400" : "text-white"
                  )}>
                    {result.primary.summary.total_pnl >= 0 ? '+' : ''}₹{result.primary.summary.total_pnl.toLocaleString('en-IN')}
                  </div>
                </div>

                <div className="bg-navy-900 border border-navy-800 p-3 rounded-lg">
                  <div className="text-[10px] text-navy-300 font-bold uppercase">Win Rate</div>
                  <div className="text-lg font-bold text-white font-mono mt-1">
                    {(result.primary.summary.win_rate * 100).toFixed(1)}%
                    <span className="text-[11px] text-navy-300 ml-1.5 font-normal">
                      ({result.primary.summary.winning_trades} / {result.primary.summary.total_trades})
                    </span>
                  </div>
                </div>

                <div className="bg-navy-900 border border-navy-800 p-3 rounded-lg">
                  <div className="text-[10px] text-navy-300 font-bold uppercase">Max Drawdown</div>
                  <div className="text-lg font-bold text-red-400 font-mono mt-1">
                    ₹{result.primary.summary.max_drawdown.toLocaleString('en-IN')}
                  </div>
                </div>

                <div className="bg-navy-900 border border-navy-800 p-3 rounded-lg">
                  <div className="text-[10px] text-navy-300 font-bold uppercase">Avg Win / Loss</div>
                  <div className="text-xs font-semibold font-mono mt-2 space-y-0.5">
                    <div className="text-green-400">Win: +₹{result.primary.summary.average_profit.toFixed(0)}</div>
                    <div className="text-red-400">Loss: ₹{result.primary.summary.average_loss.toFixed(0)}</div>
                  </div>
                </div>
              </div>

              {/* Side-by-Side Comparison Table (if exists) */}
              {result.comparisons.length > 0 && (
                <div className="bg-navy-900 border border-navy-800 p-3 rounded-lg">
                  <h4 className="text-xs font-bold text-orange-400 uppercase tracking-wider mb-2">Side-by-Side Configuration Comparison</h4>
                  <table className="w-full text-xs text-left">
                    <thead>
                      <tr className="text-navy-300 border-b border-navy-850">
                        <th className="py-1">Configuration Name</th>
                        <th>Levels (R3 ➜ R1 | S1 ➜ S3)</th>
                        <th className="text-right">Trades</th>
                        <th className="text-right">Win Rate</th>
                        <th className="text-right">Max Drawdown</th>
                        <th className="text-right font-bold">Total P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Primary */}
                      <tr className="border-b border-navy-850 hover:bg-navy-900/40 text-navy-200">
                        <td className="py-1.5 font-bold text-white">Primary Config (Tested)</td>
                        <td className="font-mono text-[10px] text-navy-300">
                          {primaryConfig.r3}/{primaryConfig.r2}/{primaryConfig.r1} | {primaryConfig.s1}/{primaryConfig.s2}/{primaryConfig.s3}
                        </td>
                        <td className="text-right">{result.primary.summary.total_trades}</td>
                        <td className="text-right">{(result.primary.summary.win_rate * 100).toFixed(1)}%</td>
                        <td className="text-right text-red-400">₹{result.primary.summary.max_drawdown}</td>
                        <td className={clsx("text-right font-bold font-mono", result.primary.summary.total_pnl >= 0 ? "text-green-400" : "text-red-400")}>
                          {result.primary.summary.total_pnl >= 0 ? '+' : ''}₹{result.primary.summary.total_pnl.toFixed(0)}
                        </td>
                      </tr>
                      {/* Alts */}
                      {result.comparisons.map((c, i) => (
                        <tr key={i} className="border-b border-navy-850 hover:bg-navy-900/40 text-navy-200">
                          <td className="py-1.5 font-semibold text-white">{c.name}</td>
                          <td className="font-mono text-[10px] text-navy-300">
                            {c.config.r3}/{c.config.r2}/{c.config.r1} | {c.config.s1}/{c.config.s2}/{c.config.s3}
                          </td>
                          <td className="text-right">{c.summary.total_trades}</td>
                          <td className="text-right">{(c.summary.win_rate * 100).toFixed(1)}%</td>
                          <td className="text-right text-red-400">₹{c.summary.max_drawdown}</td>
                          <td className={clsx("text-right font-bold font-mono", c.summary.total_pnl >= 0 ? "text-green-400" : "text-red-400")}>
                            {c.summary.total_pnl >= 0 ? '+' : ''}₹{c.summary.total_pnl.toFixed(0)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Primary Trades List Table */}
              <div className="bg-navy-900 border border-navy-800 p-3 rounded-lg">
                <h4 className="text-xs font-bold text-orange-400 uppercase tracking-wider mb-2">Primary Configuration Trades Log</h4>
                <div className="overflow-auto max-h-48">
                  <table className="w-full text-[11px] text-left">
                    <thead>
                      <tr className="text-navy-300 border-b border-navy-850">
                        <th className="py-1">Date</th>
                        <th>Side</th>
                        <th>Lvl</th>
                        <th>Lots</th>
                        <th>Entry Time/Price</th>
                        <th>Exit Time/Price</th>
                        <th>Reason</th>
                        <th className="text-right font-bold">PnL</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.primary.trades.map((t, idx) => (
                        <tr key={idx} className="border-b border-navy-850/60 hover:bg-navy-900/30 text-navy-200">
                          <td className="py-1 font-semibold">{t.date}</td>
                          <td className={clsx("font-bold", t.side === 'CE' ? "text-green-400" : "text-red-400")}>{t.side}</td>
                          <td className="text-navy-300 font-mono">{t.level}</td>
                          <td>{t.lots}</td>
                          <td>{t.entry_time} @ ₹{t.entry_price.toFixed(1)}</td>
                          <td>{t.exit_time} @ ₹{t.exit_price.toFixed(1)}</td>
                          <td className="text-[10px] text-navy-300">{t.exit_reason}</td>
                          <td className={clsx("text-right font-bold font-mono", t.pnl >= 0 ? "text-green-400" : "text-red-400")}>
                            {t.pnl >= 0 ? '+' : ''}₹{t.pnl.toFixed(0)}
                          </td>
                        </tr>
                      ))}
                      {result.primary.trades.length === 0 && (
                        <tr>
                          <td colSpan={8} className="text-center py-4 text-navy-300">No trades executed in the selected date range.</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
