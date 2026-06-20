import { useState, useMemo, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useStrategyStore } from '../../store/strategyStore'
import { useToastStore } from '../../store/toastStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import { strategyApi, configApi, tradesApi, sessionApi } from '../../services/api'
import { LevelPanel } from '../LevelPanel/LevelPanel'
import { TradeLog } from '../TradeLog/TradeLog'
import { PnLChart } from '../PnLChart/PnLChart'
import { AIObserver } from '../AIObserver/AIObserver'
import { Settings } from '../Settings/Settings'
import KiteStatus from '../KiteStatus/KiteStatus'
import { LiveLogModal } from '../LiveLogModal/LiveLogModal'
import { PDFReportsModal } from '../PDFReportsModal/PDFReportsModal'
import { BacktestModal } from '../BacktestModal/BacktestModal'
import { Notification } from '../Notification/Notification'

export function Dashboard({ onLogout }: { onLogout?: () => void }) {
  useWebSocket()
  const qc = useQueryClient()
  const { status, wsConnected } = useStrategyStore()
  const addToast = useToastStore(state => state.addToast)
  const [showSettings, setShowSettings] = useState(false)
  const [showLiveLogs, setShowLiveLogs] = useState(false)
  const [showPDFReports, setShowPDFReports] = useState(false)
  const [showBacktest, setShowBacktest] = useState(false)
  const [simPrice, setSimPrice] = useState('')
  const [exportingTrades, setExportingTrades] = useState(false)
  const [exportingLogs, setExportingLogs] = useState(false)
  const [lastLtpTime, setLastLtpTime] = useState<number | null>(null)
  const [lastPnlTime, setLastPnlTime] = useState<number | null>(null)
  const [secondsTicker, setSecondsTicker] = useState(0)
  const [confirmAction, setConfirmAction] = useState<{
    title: string
    message: string
    confirmText?: string
    cancelText?: string
    variant?: 'danger' | 'warning' | 'info'
    onConfirm: () => void
    confirmButtonId?: string
    cancelButtonId?: string
  } | null>(null)

  const handleStopClick = () => {
    setConfirmAction({
      title: 'Stop Strategy Confirmation',
      message: 'Are you sure you want to STOP the trading strategy? This will stop all active level monitoring and order placement.',
      confirmText: 'Yes, Stop Strategy',
      cancelText: 'Cancel',
      variant: 'danger',
      confirmButtonId: 'confirm-stop-btn',
      cancelButtonId: 'cancel-stop-btn',
      onConfirm: () => {
        stopMut.mutate()
        setConfirmAction(null)
      },
    })
  }

  const handleSimulateTick = () => {
    if (!simPrice) return
    const priceVal = +simPrice
    setConfirmAction({
      title: 'Simulate Tick Confirmation',
      message: `Are you sure you want to simulate a price tick of ₹${priceVal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}? This may trigger automated order placement or exits if it breaches configured strategy levels.`,
      confirmText: 'Yes, Inject Tick',
      cancelText: 'Cancel',
      variant: 'warning',
      confirmButtonId: 'confirm-sim-btn',
      cancelButtonId: 'cancel-sim-btn',
      onConfirm: () => {
        simMut.mutate(priceVal)
        setSimPrice('')
        setConfirmAction(null)
      },
    })
  }

  const handleLogout = () => {
    sessionApi.logout()
    onLogout?.()
  }

  const handleExportTrades = async () => {
    setExportingTrades(true)
    try {
      const blob = await tradesApi.exportTrades()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'pyramid_trades.csv')
      document.body.appendChild(link)
      link.click()
      link.parentNode?.removeChild(link)
      window.URL.revokeObjectURL(url)
      addToast('Trades exported successfully.', 'success')
    } catch (err) {
      console.error(err)
      addToast('Failed to export trades.', 'error')
    } finally {
      setExportingTrades(false)
    }
  }

  const handleExportLogs = async () => {
    setExportingLogs(true)
    try {
      const blob = await tradesApi.exportLogs()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', 'trade_engine.log')
      document.body.appendChild(link)
      link.click()
      link.parentNode?.removeChild(link)
      window.URL.revokeObjectURL(url)
      addToast('System logs exported successfully.', 'success')
    } catch (err: any) {
      console.error(err)
      const detail = err.response?.data?.detail
      addToast(detail || 'Failed to download execution logs. Make sure the strategy engine has run.', 'error')
    } finally {
      setExportingLogs(false)
    }
  }

  const { data: config } = useQuery({
    queryKey: ['strategy-config'],
    queryFn: configApi.getStrategy,
    retry: false,
  })

  const { data: trades = [] } = useQuery({
    queryKey: ['trades-today'],
    queryFn: tradesApi.getToday,
    refetchInterval: wsConnected ? 15000 : 3000,
  })

  const { data: pnl } = useQuery({
    queryKey: ['pnl-today'],
    queryFn: tradesApi.getTodayPnl,
    refetchInterval: wsConnected ? 15000 : 3000,
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

  const niftyPrevClose = status?.nifty_prev_close
  const niftyChange = useMemo(() => {
    if (niftyLtp == null || niftyPrevClose == null || niftyPrevClose === 0) return null
    const diff = niftyLtp - niftyPrevClose
    const pct = (diff / niftyPrevClose) * 100
    return {
      diff,
      pct,
      isUp: diff >= 0,
      formattedDiff: Math.abs(diff).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      formattedPct: Math.abs(pct).toFixed(2) + '%',
    }
  }, [niftyLtp, niftyPrevClose])

  const marketTimestamp = useMemo(() => {
    if (!lastLtpTime) return null
    const date = new Date(lastLtpTime)
    return date.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: true,
    }).toUpperCase() + ' IST'
  }, [lastLtpTime])

  useEffect(() => {
    if (niftyLtp != null) {
      setLastLtpTime(Date.now())
    }
  }, [niftyLtp])

  useEffect(() => {
    if (pnl != null) {
      setLastPnlTime(Date.now())
    }
  }, [pnl])

  useEffect(() => {
    const interval = setInterval(() => {
      setSecondsTicker(t => t + 1)
    }, 1000)
    return () => clearInterval(interval)
  }, [])

  const formatTimeAgo = (lastTime: number | null) => {
    if (!lastTime) return 'never'
    const seconds = Math.floor((Date.now() - lastTime) / 1000)
    if (seconds < 1) return 'just now'
    if (seconds < 60) return `${seconds}s ago`
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    if (remainingSeconds === 0) return `${minutes} min ago`
    return `${minutes} min ${remainingSeconds}s ago`
  }

  return (
    <div className="min-h-screen bg-navy-950 text-navy-100">
      {/* Header */}
      <header className="border-b border-navy-700 bg-navy-900/60 backdrop-blur-md px-4 py-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-orange-400 font-bold text-lg"><span aria-hidden="true">🔺</span> PyramidStrategy</span>
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
            <button onClick={handleStopClick}
              className="px-3 py-1 bg-red-800 hover:bg-red-700 rounded text-xs font-bold shadow-md shadow-red-950/20 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:ring-offset-navy-950">
              <span aria-hidden="true">⏹</span> STOP
            </button>
          ) : (
            <button onClick={() => startMut.mutate()}
              disabled={!config}
              className="px-3 py-1 bg-green-700 hover:bg-green-600 disabled:opacity-40 rounded text-xs font-bold shadow-md shadow-green-950/20 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 focus:ring-offset-navy-950">
              <span aria-hidden="true">▶</span> START
            </button>
          )}
          <button onClick={() => setShowLiveLogs(true)}
            className="px-3 py-1 bg-navy-800 hover:bg-navy-700 border border-navy-700 rounded text-xs text-navy-100 transition duration-150 focus:outline-none focus:ring-2 focus:ring-orange-500">
            <span aria-hidden="true">📄</span> Trade Log
          </button>
          <button onClick={() => setShowPDFReports(true)}
            className="px-3 py-1 bg-navy-800 hover:bg-navy-700 border border-navy-700 rounded text-xs text-navy-100 transition duration-150 focus:outline-none focus:ring-2 focus:ring-orange-500">
            <span aria-hidden="true">📋</span> PDF Reports
          </button>
          <button onClick={() => setShowBacktest(true)}
            className="px-3 py-1 bg-navy-800 hover:bg-navy-700 border border-navy-700 rounded text-xs text-navy-100 transition duration-150 focus:outline-none focus:ring-2 focus:ring-orange-500">
            <span aria-hidden="true">📊</span> Backtest
          </button>
          <button onClick={() => setShowSettings(true)}
            className="px-3 py-1 bg-navy-800 hover:bg-navy-700 border border-navy-700 rounded text-xs text-navy-100 transition duration-150 focus:outline-none focus:ring-2 focus:ring-orange-500">
            <span aria-hidden="true">⚙</span> Settings
          </button>
          <button onClick={handleLogout}
            className="px-3 py-1 bg-navy-900 hover:bg-navy-800 border border-navy-700 rounded text-xs text-navy-300 hover:text-navy-100 transition duration-150 focus:outline-none focus:ring-2 focus:ring-orange-500">
            <span aria-hidden="true">⇥</span> Logout
          </button>
        </div>
      </header>

      {/* Error messages */}
      {startMut.isError && (
        <div className="px-4 py-2 border-b border-red-800 bg-red-950/20">
          <Notification
            type="error"
            message={
              <span>
                Safety Checks Failed: {(() => {
                  const errData = (startMut.error as any)?.response?.data?.detail;
                  if (errData?.errors && Array.isArray(errData.errors)) {
                    return errData.errors.join('; ');
                  }
                  return errData?.message || errData || startMut.error?.message;
                })()}
              </span>
            }
            onClose={() => startMut.reset()}
          />
        </div>
      )}

      {/* Time warnings */}
      {status && !status.entries_allowed && (
        <div className="px-4 py-1.5 border-b border-yellow-800 bg-yellow-950/20">
          <Notification
            type="warning"
            message="11:15 AM passed — No new entries allowed"
            className="justify-center"
          />
        </div>
      )}
      {status?.squareoff_triggered && (
        <div className="px-4 py-1.5 border-b border-red-800 bg-red-950/20">
          <Notification
            type="error"
            pulse
            message="11:30 AM — SQUAREOFF TRIGGERED"
            className="justify-center font-bold"
          />
        </div>
      )}

      {/* Main grid */}
      <div className="grid grid-cols-12 gap-3 p-3">
        {/* Left: NIFTY + Levels */}
        <div className="col-span-12 lg:col-span-3 space-y-3">
          {/* NIFTY price */}
          <div className="bg-navy-900 border border-navy-700/60 rounded-xl p-4 shadow-lg flex flex-col gap-2 relative overflow-hidden transition-all duration-300 hover:border-navy-600">
            <div className="flex items-center justify-between">
              <span className="text-xs text-navy-300 font-bold uppercase tracking-wider">NIFTY 50</span>
              <span className={clsx(
                'text-[10px] px-1.5 py-0.5 rounded font-bold uppercase tracking-wider',
                wsConnected ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
              )}>
                {wsConnected ? 'LIVE' : 'OFFLINE'}
              </span>
            </div>
            
            <div className="flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-white font-mono tracking-tight">
                {niftyLtp ? niftyLtp.toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '—'}
              </span>
            </div>

            {/* Point / % change pill badge */}
            {niftyChange ? (
              <div className="flex items-center gap-2">
                <span className={clsx(
                  'inline-flex items-center gap-1 text-xs font-bold px-2.5 py-1 rounded-full border shadow-sm transition-colors',
                  niftyChange.isUp 
                    ? 'bg-green-500/10 text-green-400 border-green-500/20' 
                    : 'bg-red-500/10 text-red-400 border-red-500/20'
                )}>
                  <span>{niftyChange.isUp ? '↑' : '↓'}</span>
                  <span>{niftyChange.formattedDiff}</span>
                  <span className="opacity-80">({niftyChange.formattedPct})</span>
                </span>
                <span className="text-[10px] text-navy-300 font-medium">today</span>
              </div>
            ) : niftyLtp ? (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center text-xs font-bold px-2.5 py-1 rounded-full border border-navy-700 bg-navy-800 text-navy-300 shadow-sm font-mono">
                  — (—%)
                </span>
                <span className="text-[10px] text-navy-300 font-medium">today</span>
              </div>
            ) : null}

            {/* Market timestamp */}
            <div className="mt-1 pt-2 border-t border-navy-800 flex items-center justify-between text-[10px] text-navy-300">
              <span>
                {marketTimestamp ? `As of ${marketTimestamp}` : 'Awaiting data...'}
              </span>
              {lastLtpTime && (
                <span className="font-mono text-navy-300 bg-navy-850 px-1 py-0.5 rounded border border-navy-800/40">
                  {formatTimeAgo(lastLtpTime)}
                </span>
              )}
            </div>
          </div>

          {/* Level panel */}
          <div className="bg-navy-900 border border-navy-700 rounded-xl p-3 shadow-lg">
            <div className="text-xs text-navy-300 mb-2 font-semibold">LEVELS</div>
            <LevelPanel status={status} config={config ?? null} />
          </div>

          {/* Paper trade simulator */}
          {paperTrade && (
            <div className="bg-navy-900 border border-navy-700 rounded-xl p-3 shadow-lg">
              <div className="text-xs text-yellow-500 mb-2 font-bold uppercase tracking-wide"><span aria-hidden="true">🎮</span> Simulate Tick</div>
              <div className="flex gap-1">
                <input
                  type="number"
                  className="flex-1 bg-navy-800 border border-navy-700 focus:border-transparent focus:ring-2 focus:ring-orange-500 focus:outline-none rounded px-2 py-1 text-xs text-white"
                  placeholder="NIFTY price"
                  value={simPrice}
                  onChange={e => setSimPrice(e.target.value)}
                />
                <button
                  onClick={handleSimulateTick}
                  disabled={!simPrice}
                  className="px-2 py-1 bg-orange-700 hover:bg-orange-600 text-white rounded text-xs font-semibold disabled:opacity-40 transition duration-150 focus:outline-none focus:ring-2 focus:ring-orange-500">
                  <span aria-hidden="true">→</span>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Center: P&L + Trade Log */}
        <div className="col-span-12 lg:col-span-5 space-y-3">
          {/* P&L Summary */}
          <div className="bg-navy-900 border border-navy-700 rounded-xl p-3 shadow-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-navy-300 font-semibold">TODAY'S P&L</span>
              <span className="text-xs text-navy-300 font-mono">{pnl?.total_exits ?? 0} exits | {pnl?.winning_trades ?? 0} wins</span>
            </div>
            <div className="flex items-end justify-between">
              <div className={clsx('text-2xl font-bold font-mono',
                todayPnl > 0 ? 'text-green-400' : todayPnl < 0 ? 'text-red-400' : 'text-navy-300')}>
                {todayPnl >= 0 ? '+' : ''}₹{todayPnl.toFixed(0)}
              </div>
              {lastPnlTime && (
                <span className="text-[10px] text-navy-300 font-mono">
                  {formatTimeAgo(lastPnlTime)}
                </span>
              )}
            </div>
          </div>

          {/* P&L Chart */}
          <div className="bg-navy-900 border border-navy-700 rounded-xl p-3 shadow-lg">
            <div className="text-xs text-navy-300 mb-2 font-semibold">P&L CHART</div>
            <PnLChart data={pnlChartData} />
          </div>

          {/* Trade Log */}
          <div className="bg-navy-900 border border-navy-700 rounded-xl p-3 shadow-lg">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-navy-200">TRADE LOG</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleExportTrades}
                  disabled={exportingTrades}
                  className="px-2.5 py-1 bg-navy-800 hover:bg-navy-700 disabled:opacity-40 text-navy-200 rounded text-[10px] font-semibold border border-navy-700 transition flex items-center gap-1 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  {exportingTrades ? (
                    <span className="w-2.5 h-2.5 border border-navy-300 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <span aria-hidden="true">📥</span>
                  )}
                  Export CSV
                </button>
                <button
                  onClick={handleExportLogs}
                  disabled={exportingLogs}
                  className="px-2.5 py-1 bg-navy-800 hover:bg-navy-700 disabled:opacity-40 text-navy-200 rounded text-[10px] font-semibold border border-navy-700 transition flex items-center gap-1 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
                >
                  {exportingLogs ? (
                    <span className="w-2.5 h-2.5 border border-navy-300 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <span aria-hidden="true">📄</span>
                  )}
                  System Logs
                </button>
              </div>
            </div>
            <TradeLog />
          </div>
        </div>

        {/* Right: AI Observer + Open Positions */}
        <div className="col-span-12 lg:col-span-4 space-y-3">
          {/* Open Positions */}
          <div className="bg-navy-900 border border-navy-700 rounded-xl p-3 shadow-lg">
            <div className="text-xs text-navy-300 mb-2 font-semibold">OPEN POSITIONS</div>
            {[status?.ce, status?.pe].map((sm, i) => (
              sm && sm.state !== 'IDLE' && sm.state !== 'BLOCKED' && (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-navy-850">
                  <span className={i === 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                    {i === 0 ? '▲ CE' : '▼ PE'}
                  </span>
                  <span className="text-navy-100">{sm.locked_instrument}</span>
                  <span className="text-navy-300">{sm.lots}L</span>
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
              <div className="text-navy-300 text-xs text-center py-2">No open positions</div>
            )}
          </div>

          {/* Kite Connection Status */}
          <KiteStatus />

          {/* AI Observer */}
          <div className="bg-navy-900 border border-navy-700 rounded-xl p-3 shadow-lg">
            <div className="text-xs text-navy-300 mb-2 font-semibold"><span aria-hidden="true">🤖</span> AI OBSERVER</div>
            <AIObserver />
          </div>
        </div>
      </div>

      {showSettings && <Settings onClose={() => { setShowSettings(false); qc.invalidateQueries() }} />}
      {showLiveLogs && <LiveLogModal onClose={() => setShowLiveLogs(false)} />}
      {showPDFReports && <PDFReportsModal onClose={() => setShowPDFReports(false)} />}
      {showBacktest && <BacktestModal onClose={() => setShowBacktest(false)} />}

      {confirmAction && (
        <ConfirmModal
          isOpen={!!confirmAction}
          title={confirmAction.title}
          message={confirmAction.message}
          confirmText={confirmAction.confirmText}
          cancelText={confirmAction.cancelText}
          variant={confirmAction.variant}
          confirmButtonId={confirmAction.confirmButtonId}
          cancelButtonId={confirmAction.cancelButtonId}
          onConfirm={confirmAction.onConfirm}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}

interface ConfirmModalProps {
  isOpen: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
  variant?: 'danger' | 'warning' | 'info'
  confirmButtonId?: string
  cancelButtonId?: string
}

function ConfirmModal({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'info',
  confirmButtonId,
  cancelButtonId,
}: ConfirmModalProps) {
  if (!isOpen) return null

  const variantStyles = {
    danger: {
      btnClass: 'bg-red-800 hover:bg-red-700 shadow-red-950/20 text-white focus:ring-red-500/50',
      icon: '⚠️',
      titleColor: 'text-red-400',
    },
    warning: {
      btnClass: 'bg-amber-600 hover:bg-amber-500 shadow-amber-950/20 text-white focus:ring-amber-500/50',
      icon: '⚡',
      titleColor: 'text-amber-400',
    },
    info: {
      btnClass: 'bg-orange-600 hover:bg-orange-500 shadow-orange-950/20 text-white focus:ring-orange-500/50',
      icon: 'ℹ️',
      titleColor: 'text-orange-400',
    },
  }

  const activeVariant = variantStyles[variant]

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-fade-in">
      <div className="bg-navy-950 border border-navy-700/80 rounded-2xl w-full max-w-md shadow-2xl shadow-blue-500/5 overflow-hidden flex flex-col backdrop-blur-xl animate-scale-up">
        {/* Header */}
        <div className="flex items-center gap-2 p-4 border-b border-navy-700 bg-navy-900/40">
          <span className="text-lg">{activeVariant.icon}</span>
          <h2 className={`text-base font-bold ${activeVariant.titleColor} tracking-wide uppercase`}>
            {title}
          </h2>
        </div>

        {/* Content */}
        <div className="p-5 text-sm text-navy-200">
          <p>{message}</p>
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2.5 p-4 border-t border-navy-800 bg-navy-900/20">
          <button
            type="button"
            id={cancelButtonId}
            onClick={onCancel}
            className="px-4 py-2 bg-navy-800 hover:bg-navy-700 text-navy-200 hover:text-navy-100 rounded-lg text-xs font-semibold border border-navy-700 transition duration-150 focus:outline-none focus:ring-2 focus:ring-navy-700"
          >
            {cancelText}
          </button>
          <button
            type="button"
            id={confirmButtonId}
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-xs font-bold transition duration-150 focus:outline-none focus:ring-2 ${activeVariant.btnClass}`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
