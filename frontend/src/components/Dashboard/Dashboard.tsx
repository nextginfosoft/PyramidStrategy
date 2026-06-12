import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useStrategyStore } from '../../store/strategyStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import { strategyApi, configApi, tradesApi, sessionApi } from '../../services/api'
import { LevelPanel } from '../LevelPanel/LevelPanel'
import { TradeLog } from '../TradeLog/TradeLog'
import { PnLChart } from '../PnLChart/PnLChart'
import { AIObserver } from '../AIObserver/AIObserver'
import { Settings } from '../Settings/Settings'
import KiteStatus from '../KiteStatus/KiteStatus'

export function Dashboard({ onLogout }: { onLogout?: () => void }) {
  useWebSocket()
  const qc = useQueryClient()
  const { status, wsConnected } = useStrategyStore()
  const [showSettings, setShowSettings] = useState(false)
  const [simPrice, setSimPrice] = useState('')

  const handleLogout = () => {
    sessionApi.logout()
    onLogout?.()
  }

  const { data: config } = useQuery({
    queryKey: ['strategy-config'],
    queryFn: configApi.getStrategy,
    retry: false,
  })

  const { data: trades = [] } = useQuery({
    queryKey: ['trades-today'],
    queryFn: tradesApi.getToday,
    refetchInterval: 3000,
  })

  const { data: pnl } = useQuery({
    queryKey: ['pnl-today'],
    queryFn: tradesApi.getTodayPnl,
    refetchInterval: 3000,
  })

  const startMut = useMutation({
    mutationFn: strategyApi.start,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategy-status'] }),
  })
  const stopMut = useMutation({
    mutationFn: strategyApi.stop,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategy-status'] }),
  })
  const simMut = useMutation({
    mutationFn: (p: number) => strategyApi.simulateTick(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trades-today'] })
      qc.invalidateQueries({ queryKey: ['pnl-today'] })
    },
  })

  const pnlChartData = useMemo(() => {
    return trades
      .filter(t => t.action === 'EXIT' && t.pnl != null)
      .map(t => ({
        time: new Date(t.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }),
        pnl: t.pnl!,
      }))
  }, [trades])

  const isRunning = status?.is_running ?? false
  const paperTrade = status?.paper_trade ?? true
  const niftyLtp = status?.nifty_ltp
  const todayPnl = pnl?.gross_pnl ?? 0

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-orange-400 font-bold text-lg">🔺 PyramidStrategy</span>
          {paperTrade && (
            <span className="text-xs bg-yellow-900/50 border border-yellow-700 text-yellow-400 px-2 py-0.5 rounded font-bold">
              PAPER TRADE
            </span>
          )}
          <span className={clsx('text-xs flex items-center gap-1',
            wsConnected ? 'text-green-400' : 'text-red-400')}>
            <span className={clsx('w-1.5 h-1.5 rounded-full', wsConnected ? 'bg-green-400 animate-pulse' : 'bg-red-400')} />
            {wsConnected ? 'LIVE' : 'DISCONNECTED'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isRunning ? (
            <button onClick={() => stopMut.mutate()}
              className="px-3 py-1 bg-red-800 hover:bg-red-700 rounded text-xs font-bold">
              ⏸ PAUSE
            </button>
          ) : (
            <button onClick={() => startMut.mutate()}
              disabled={!config}
              className="px-3 py-1 bg-green-700 hover:bg-green-600 disabled:opacity-40 rounded text-xs font-bold">
              ▶ START
            </button>
          )}
          <button onClick={() => setShowSettings(true)}
            className="px-3 py-1 bg-gray-700 hover:bg-gray-600 rounded text-xs">
            ⚙ Settings
          </button>
          <button onClick={handleLogout}
            className="px-3 py-1 bg-gray-800 hover:bg-gray-700 rounded text-xs text-gray-400">
            ⇥ Logout
          </button>
        </div>
      </header>

      {/* Time warnings */}
      {status && !status.entries_allowed && (
        <div className="bg-yellow-900/30 border-b border-yellow-800 px-4 py-1 text-xs text-yellow-400 text-center">
          ⚠ 11:15 AM passed — No new entries allowed
        </div>
      )}
      {status?.squareoff_triggered && (
        <div className="bg-red-900/40 border-b border-red-800 px-4 py-1 text-xs text-red-400 text-center font-bold animate-pulse">
          🔔 11:30 AM — SQUAREOFF TRIGGERED
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-12 gap-3 p-3">
        {/* Left: NIFTY + Levels */}
        <div className="col-span-3 space-y-3">
          {/* NIFTY price */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1">NIFTY 50</div>
            <div className="text-2xl font-bold text-white font-mono">
              {niftyLtp ? niftyLtp.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
            </div>
          </div>

          {/* Level panel */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-2">LEVELS</div>
            <LevelPanel status={status} config={config ?? null} />
          </div>

          {/* Paper trade simulator */}
          {paperTrade && (
            <div className="bg-gray-900 border border-gray-700 rounded-lg p-3">
              <div className="text-xs text-yellow-600 mb-2 font-bold">🎮 SIMULATE TICK</div>
              <div className="flex gap-1">
                <input
                  type="number"
                  className="flex-1 bg-gray-800 border border-gray-600 rounded px-2 py-1 text-xs text-white"
                  placeholder="NIFTY price"
                  value={simPrice}
                  onChange={e => setSimPrice(e.target.value)}
                />
                <button
                  onClick={() => { simMut.mutate(+simPrice); setSimPrice('') }}
                  disabled={!simPrice}
                  className="px-2 py-1 bg-orange-700 hover:bg-orange-600 rounded text-xs disabled:opacity-40">
                  →
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Center: P&L + Trade Log */}
        <div className="col-span-5 space-y-3">
          {/* P&L Summary */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-gray-500">TODAY'S P&L</span>
              <span className="text-xs text-gray-600">{pnl?.total_exits ?? 0} exits | {pnl?.winning_trades ?? 0} wins</span>
            </div>
            <div className={clsx('text-2xl font-bold font-mono',
              todayPnl > 0 ? 'text-green-400' : todayPnl < 0 ? 'text-red-400' : 'text-gray-400')}>
              {todayPnl >= 0 ? '+' : ''}₹{todayPnl.toFixed(0)}
            </div>
          </div>

          {/* P&L Chart */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-2">P&L CHART</div>
            <PnLChart data={pnlChartData} />
          </div>

          {/* Trade Log */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-2">TRADE LOG</div>
            <TradeLog trades={trades} />
          </div>
        </div>

        {/* Right: AI Observer + Open Positions */}
        <div className="col-span-4 space-y-3">
          {/* Open Positions */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-2">OPEN POSITIONS</div>
            {[status?.ce, status?.pe].map((sm, i) => (
              sm && sm.state !== 'IDLE' && sm.state !== 'BLOCKED' && (
                <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-gray-800">
                  <span className={i === 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                    {i === 0 ? 'CE' : 'PE'}
                  </span>
                  <span className="text-gray-300">{sm.locked_instrument}</span>
                  <span className="text-gray-400">{sm.lots}L</span>
                  <span className={clsx('font-mono',
                    (sm.unrealized_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
                    {sm.unrealized_pnl != null
                      ? `${sm.unrealized_pnl >= 0 ? '+' : ''}₹${sm.unrealized_pnl.toFixed(0)}`
                      : '—'}
                  </span>
                </div>
              )
            ))}
            {(!status?.ce || status.ce.state === 'IDLE') && (!status?.pe || status.pe.state === 'IDLE') && (
              <div className="text-gray-600 text-xs text-center py-2">No open positions</div>
            )}
          </div>

          {/* Kite Connection Status */}
          <KiteStatus />

          {/* AI Observer */}
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-2">🤖 AI OBSERVER</div>
            <AIObserver />
          </div>
        </div>
      </div>

      {showSettings && <Settings onClose={() => { setShowSettings(false); qc.invalidateQueries() }} />}
    </div>
  )
}
