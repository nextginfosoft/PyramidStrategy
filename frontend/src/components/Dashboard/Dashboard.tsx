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
import { AdminPanel } from '../AdminPanel/AdminPanel'
import { UserSession } from '../../App'
import { BacktestModal } from '../BacktestModal/BacktestModal'
import { Analytics } from '../Analytics/AnalyticsModal'
import { Notification } from '../Notification/Notification'
import type { SideStatus, StrategyStatus, StrategyConfig } from '../../types'
import { UserGuide } from '../UserGuide/UserGuide'
import { StatusBar } from '../StatusBar/StatusBar'
import { DevotionalHeaderBar } from '../DevotionalHeaderBar/DevotionalHeaderBar'
import { ChartModal } from '../ChartModal/ChartModal'
import { LevelHistoryModal } from '../LevelPanel/LevelHistoryModal'
import { GoalsModal } from '../GoalsModal/GoalsModal'
import { AreaChart as SparkAreaChart, Area as SparkArea, ResponsiveContainer as SparkContainer } from 'recharts'

const formatTimeTo12Hour = (timeStr: string): string => {
  try {
    const [hStr, mStr] = timeStr.split(':')
    const h = parseInt(hStr, 10)
    const m = parseInt(mStr, 10)
    const period = h >= 12 ? 'PM' : 'AM'
    const displayH = h % 12 === 0 ? 12 : h % 12
    const displayM = m < 10 ? `0${m}` : m
    return `${displayH}:${displayM} ${period}`
  } catch (e) {
    return timeStr
  }
}

const getCutoffTimeStr = (squareoffTime: string): string => {
  try {
    const [hStr, mStr] = squareoffTime.split(':')
    const h = parseInt(hStr, 10)
    const m = parseInt(mStr, 10)
    const totalMinutes = h * 60 + m - 15
    const cutoffH = Math.floor(totalMinutes / 60)
    const cutoffM = totalMinutes % 60
    const period = cutoffH >= 12 ? 'PM' : 'AM'
    const displayH = cutoffH % 12 === 0 ? 12 : cutoffH % 12
    const displayM = cutoffM < 10 ? `0${cutoffM}` : cutoffM
    return `${displayH}:${displayM} ${period}`
  } catch (e) {
    return '11:15 AM'
  }
}

export function Dashboard({ onLogout, user }: { onLogout?: () => void; user?: UserSession | null }) {
  useWebSocket()
  const qc = useQueryClient()
  const { status, wsConnected, setStatus, clearAISuggestions } = useStrategyStore()
  const addToast = useToastStore(state => state.addToast)
  const [showSettings, setShowSettings] = useState(false)
  const [showAdminPanel, setShowAdminPanel] = useState(false)
  const [showUserGuide, setShowUserGuide] = useState(false)
  const [showLiveLogs, setShowLiveLogs] = useState(false)
  const [showPDFReports, setShowPDFReports] = useState(false)
  const [showBacktest, setShowBacktest] = useState(false)
  const [showAnalytics, setShowAnalytics] = useState(false)
  const [showChart, setShowChart] = useState(false)
  const [showLevelHistory, setShowLevelHistory] = useState(false)
  const [showGoals, setShowGoals] = useState(false)
  const [simPrice, setSimPrice] = useState('')
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    return localStorage.getItem('sidebar_collapsed') === 'true'
  })
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    const saved = localStorage.getItem('pyramid_theme')
    if (saved === 'light') {
      document.documentElement.setAttribute('data-theme', 'light')
      return 'light'
    }
    document.documentElement.setAttribute('data-theme', 'dark')
    return 'dark'
  })

  const handleToggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(nextTheme)
    document.documentElement.setAttribute('data-theme', nextTheme)
    localStorage.setItem('pyramid_theme', nextTheme)
  }
  const [exportingTrades, setExportingTrades] = useState(false)
  const [exportingLogs, setExportingLogs] = useState(false)
  const [exportPeriod, setExportPeriod] = useState('all')
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

  const handleEmergencyExitClick = () => {
    setConfirmAction({
      title: '🚨 EMERGENCY EXIT CONFIRMATION 🚨',
      message: 'Are you absolutely sure you want to trigger EMERGENCY EXIT? This will immediately stop the engine and exit ALL open positions at MARKET price.',
      confirmText: 'Yes, Exit All Positions',
      cancelText: 'Cancel',
      variant: 'danger',
      confirmButtonId: 'confirm-emergency-btn',
      cancelButtonId: 'cancel-emergency-btn',
      onConfirm: () => {
        emergencyExitMut.mutate()
        setConfirmAction(null)
      },
    })
  }

  const handleResetClick = () => {
    setConfirmAction({
      title: 'Reset Daily Strategy State',
      message: 'Are you sure you want to manually RESET the daily CE and PE state machines? This will clear all level monitoring, locked strikes, and set states to IDLE.',
      confirmText: 'Yes, Reset Strategy',
      cancelText: 'Cancel',
      variant: 'warning',
      confirmButtonId: 'confirm-reset-btn',
      cancelButtonId: 'cancel-reset-btn',
      onConfirm: () => {
        resetMut.mutate()
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

  const handleExportTrades = async (period: string = 'all') => {
    setExportingTrades(true)
    try {
      const blob = await tradesApi.exportTrades(period)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `pyramid_trades_${period}.csv`)
      document.body.appendChild(link)
      link.click()
      link.parentNode?.removeChild(link)
      window.URL.revokeObjectURL(url)
      addToast(`Trades (${period}) exported successfully.`, 'success')
    } catch (err) {
      console.error(err)
      addToast(`Failed to export trades (${period}).`, 'error')
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

  const { data: config, isLoading: isConfigLoading } = useQuery<StrategyConfig>({
    queryKey: ['strategy-config'],
    queryFn: () => configApi.getStrategy(),
    retry: false,
    enabled: user?.is_approved !== false,
  })

  const { data: trades = [] } = useQuery({
    queryKey: ['trades-today'],
    queryFn: tradesApi.getToday,
    refetchInterval: wsConnected ? 15000 : 3000,
    enabled: user?.is_approved !== false,
  })

  const { data: pnl, isLoading: isPnlLoading } = useQuery({
    queryKey: ['pnl-today'],
    queryFn: tradesApi.getTodayPnl,
    refetchInterval: wsConnected ? 15000 : 3000,
    enabled: user?.is_approved !== false,
  })

  const { data: queryStatus } = useQuery({
    queryKey: ['strategy-status'],
    queryFn: strategyApi.getStatus,
    refetchInterval: wsConnected ? 15000 : 3000,
    enabled: user?.is_approved !== false,
  })

  useEffect(() => {
    if (queryStatus) {
      setStatus(queryStatus)
    }
  }, [queryStatus, setStatus])

  const startMut = useMutation({
    mutationFn: strategyApi.start,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategy-status'] }),
  })
  const stopMut = useMutation({
    mutationFn: strategyApi.stop,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['strategy-status'] }),
  })
  const emergencyExitMut = useMutation({
    mutationFn: strategyApi.emergencyExit,
    onSuccess: (data: any) => {
      qc.invalidateQueries({ queryKey: ['strategy-status'] })
      qc.invalidateQueries({ queryKey: ['trades-today'] })
      qc.invalidateQueries({ queryKey: ['pnl-today'] })
      qc.invalidateQueries({ queryKey: ['trades-log-data'] })
      addToast(`Emergency Exit Completed! Exited ${data?.exited_count || 0} position(s).`, 'success')
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      addToast(detail || 'Emergency exit failed. Check broker terminal manually!', 'error')
    }
  })
  const simMut = useMutation({
    mutationFn: (p: number) => strategyApi.simulateTick(p),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['trades-today'] })
      qc.invalidateQueries({ queryKey: ['pnl-today'] })
    },
  })

  const resetMut = useMutation({
    mutationFn: strategyApi.reset,
    onSuccess: (data) => {
      // Clear client store states
      clearAISuggestions()
      
      // Invalidate all daily data queries
      qc.invalidateQueries({ queryKey: ['strategy-status'] })
      qc.invalidateQueries({ queryKey: ['trades-today'] })
      qc.invalidateQueries({ queryKey: ['pnl-today'] })
      qc.invalidateQueries({ queryKey: ['ai-suggestions'] })
      qc.invalidateQueries({ queryKey: ['trades-log-data'] })
      qc.invalidateQueries({ queryKey: ['ai-pre-market'] })
      qc.invalidateQueries({ queryKey: ['ai-post-session'] })
      
      addToast(data?.message || 'Daily reset successfully triggered.', 'success')
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail
      addToast(detail || 'Failed to trigger reset.', 'error')
    }
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
  const [niftyTicks, setNiftyTicks] = useState<number[]>([])

  useEffect(() => {
    if (niftyLtp != null) {
      setNiftyTicks(prev => {
        if (prev.length > 0 && prev[prev.length - 1] === niftyLtp) {
          return prev
        }
        const next = [...prev, niftyLtp]
        if (next.length > 30) {
          return next.slice(next.length - 30)
        }
        return next
      })
    }
  }, [niftyLtp])

  const sparklineData = useMemo(() => {
    return niftyTicks.map((val, idx) => ({ id: idx, value: val }))
  }, [niftyTicks])

  const todayPnl = pnl?.gross_pnl ?? 0
  const hasOpenPositions = (status?.ce?.lots ?? 0) > 0 || (status?.pe?.lots ?? 0) > 0

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

  const estimatedCharges = useMemo(() => {
    let totalBrokerage = 0
    let totalExchangeTaxes = 0
    let totalStt = 0
    let totalStampDuty = 0
    let totalSlippage = 0 // Est. 0.1% slippage on exit order fills

    trades.forEach(t => {
      const price = t.avg_price ?? 0
      const qty = t.qty ?? 0
      const value = price * qty

      // Only count completed/filled trades
      if (t.status === 'COMPLETED' || t.status === 'FILLED' || !t.status) {
        // Zerodha Brokerage: Flat ₹20 per executed order
        totalBrokerage += 20

        // Exchange Transaction Charges (approx. 0.05% of turnover value for options)
        totalExchangeTaxes += value * 0.0005

        if (t.action === 'EXIT') {
          // STT (Securities Transaction Tax) is 0.125% of option premium value on Sell side
          totalStt += value * 0.00125
        } else if (t.action === 'BUY') {
          // Stamp duty is 0.003% of option premium value on Buy side
          totalStampDuty += value * 0.00003
        }

        // Slippage: Let's estimate an average slippage of approx. 0.1% of option turnover value
        totalSlippage += value * 0.001
      }
    })

    // GST is 18% of (Brokerage + Exchange Transaction Charges)
    const gst = (totalBrokerage + totalExchangeTaxes) * 0.18

    // SEBI Charges: 0.0001% of turnover
    const turnover = trades.reduce((acc, t) => acc + ((t.avg_price ?? 0) * (t.qty ?? 0)), 0)
    const sebiCharges = turnover * 0.000001

    const totalCharges = totalBrokerage + totalExchangeTaxes + totalStt + totalStampDuty + gst + sebiCharges
    const netPnl = todayPnl - totalCharges - totalSlippage

    return {
      brokerage: totalBrokerage,
      taxes: totalExchangeTaxes + totalStt + totalStampDuty + gst + sebiCharges,
      slippage: totalSlippage,
      total: totalCharges + totalSlippage,
      netPnl,
    }
  }, [trades, todayPnl])

  const { data: pnlHistory = [] } = useQuery({
    queryKey: ['pnl-history'],
    queryFn: tradesApi.getPnlHistory,
    refetchInterval: wsConnected ? 60000 : 15000,
    enabled: user?.is_approved !== false,
  })

  const stats = useMemo(() => {
    if (!pnlHistory || !pnlHistory.length) {
      return { winRate: 0, streak: 0, profitFactor: 0.0 }
    }
    const winningDays = pnlHistory.filter(day => (day.net_pnl ?? 0) > 0).length
    const winRate = (winningDays / pnlHistory.length) * 100

    let streak = 0
    // Count consecutive winning days (pnlHistory is sorted desc: latest first)
    for (let i = 0; i < pnlHistory.length; i++) {
      const net = pnlHistory[i].net_pnl ?? 0
      if (net > 0) {
        streak++
      } else if (net < 0) {
        break
      }
    }

    let grossProfits = 0
    let grossLosses = 0
    pnlHistory.forEach(day => {
      const p = day.net_pnl ?? 0
      if (p > 0) {
        grossProfits += p
      } else if (p < 0) {
        grossLosses += Math.abs(p)
      }
    })
    const profitFactor = grossLosses > 0 ? (grossProfits / grossLosses) : grossProfits > 0 ? 9.9 : 0.0

    return {
      winRate: Math.round(winRate),
      streak,
      profitFactor: parseFloat(profitFactor.toFixed(2))
    }
  }, [pnlHistory])

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
    
    if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60)
      const remainingSeconds = seconds % 60
      if (remainingSeconds === 0) return `${minutes} min ago`
      return `${minutes} min ${remainingSeconds}s ago`
    } else {
      const hours = Math.floor(seconds / 3600)
      const remainingMinutes = Math.floor((seconds % 3600) / 60)
      const remainingSeconds = seconds % 60
      
      const parts: string[] = [`${hours} hr`]
      if (remainingMinutes > 0) parts.push(`${remainingMinutes} min`)
      if (remainingSeconds > 0) parts.push(`${remainingSeconds}s`)
      return `${parts.join(' ')} ago`
    }
  }

  if (user && user.is_approved === false) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
        <div className="max-w-md w-full bg-navy-950/40 backdrop-blur-md border border-navy-500/30 rounded-2xl p-8 text-center shadow-2xl relative overflow-hidden">
          {/* Decorative glowing gradient background circles */}
          <div className="absolute -top-24 -left-24 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl" />
          <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-rose-500/10 rounded-full blur-3xl" />

          {/* Verification icon */}
          <div className="w-20 h-20 bg-gradient-to-tr from-cyan-500 to-emerald-500 rounded-full flex items-center justify-center mx-auto mb-6 shadow-[0_0_20px_rgba(6,182,212,0.3)] animate-pulse">
            <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>

          <h2 className="text-2xl font-bold text-white mb-3 tracking-wide">Verification Pending</h2>
          
          <div className="bg-navy-900/60 rounded-xl p-4 mb-6 border border-navy-500/20 text-left">
            <p className="text-xs text-navy-300 font-bold uppercase tracking-wider mb-1">Registered Username</p>
            <p className="text-sm font-semibold text-cyan-400">{user.username}</p>
          </div>

          <p className="text-gray-300 text-sm leading-relaxed mb-8">
            Your registration is currently pending administrator review. 
            An automated notification has been sent to our system moderator. 
            You will be granted immediate dashboard access as soon as your account is approved.
          </p>

          <div className="flex gap-4">
            <button 
              onClick={onLogout}
              className="flex-1 py-3 px-5 bg-navy-800 hover:bg-navy-700 text-white font-semibold rounded-xl text-sm transition-all border border-navy-500/20 active:scale-[0.98]"
            >
              Sign In with Other Account
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen overflow-hidden bg-navy-950 text-navy-100 flex">
      {/* Sidebar navigation */}
      <aside className={clsx(
        "bg-navy-900 border-r border-navy-800 flex flex-col shrink-0 select-none transition-all duration-300 overflow-hidden",
        sidebarCollapsed ? "w-0" : "w-60"
      )}>
        {/* Brand / Connection */}
        <div className="p-4 border-b border-navy-800 space-y-2">
          <div className="flex items-center gap-2">
            <img src="/destiny-shield-icon.png" alt="Destiny Shield Icon" className="w-7 h-7 object-contain filter drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
            <span className="text-base font-black uppercase tracking-wider bg-gradient-to-r from-amber-200 via-amber-400 to-amber-500 bg-clip-text text-transparent whitespace-nowrap">
              DESTINY
            </span>
            <span className="text-[8px] bg-navy-950/60 border border-navy-850 text-navy-400 px-1 py-0.5 rounded font-mono font-bold select-none ml-0.5">
              2026
            </span>
          </div>
          <div className="flex items-center justify-between gap-1.5 pt-0.5">
            <span className={clsx('text-[10px] flex items-center gap-1.5 font-bold tracking-wide select-none',
              wsConnected ? 'text-green-400' : 'text-red-400')}>
              <span className="relative flex h-2.5 w-2.5 items-center justify-center">
                {wsConnected && (
                  <span key={niftyLtp} className="absolute inline-flex h-full w-full rounded-full bg-green-400/60 animate-tick-ripple" />
                )}
                <span className={clsx('relative inline-flex rounded-full h-1.5 w-1.5',
                  wsConnected ? 'bg-green-400' : 'bg-red-400'
                )} />
              </span>
              {wsConnected ? 'LIVE FEED' : 'OFFLINE'}
            </span>
            {paperTrade && (
              <span className="text-[9px] bg-yellow-950/40 border border-yellow-700/30 text-yellow-500 px-1.5 py-0.5 rounded font-bold uppercase tracking-wider">
                Paper
              </span>
            )}
          </div>
        </div>

        {/* Engine Controls Block */}
        <div className="p-3 border-b border-navy-800 bg-navy-950/20 space-y-2">
          <div className="text-[9px] text-navy-400 font-extrabold uppercase tracking-widest px-1">Engine Controls</div>
          <div className="flex gap-2">
            {isRunning ? (
              <button onClick={handleStopClick}
                className="flex-1 py-1.5 bg-red-800 hover:bg-red-700 rounded text-xs font-bold shadow-md shadow-red-950/20 focus:outline-none focus:ring-2 focus:ring-red-500 transition duration-150">
                <span aria-hidden="true">⏹</span> STOP
              </button>
            ) : (
              <button onClick={() => startMut.mutate()}
                disabled={!config}
                className="flex-1 py-1.5 bg-green-700 hover:bg-green-600 disabled:opacity-40 rounded text-xs font-bold shadow-md shadow-green-950/20 focus:outline-none focus:ring-2 focus:ring-green-500 transition duration-150">
                <span aria-hidden="true">▶</span> START
              </button>
            )}
            <button onClick={handleResetClick}
              disabled={isRunning || hasOpenPositions}
              title={isRunning ? 'Stop strategy before resetting' : hasOpenPositions ? 'Cannot reset with active positions' : 'Reset daily strategy state'}
              className="py-1.5 px-3 bg-yellow-700 hover:bg-yellow-600 disabled:opacity-30 disabled:hover:bg-yellow-700 rounded text-xs font-bold shadow-md shadow-yellow-950/20 focus:outline-none focus:ring-2 focus:ring-yellow-500 transition duration-150">
              <span aria-hidden="true">🔄</span> RESET
            </button>
          </div>
          {hasOpenPositions && (
            <button onClick={handleEmergencyExitClick}
              className="w-full py-1.5 mt-2 bg-red-650 hover:bg-red-600 text-white font-extrabold text-[10px] uppercase tracking-wider rounded border border-red-500/30 shadow-md shadow-red-950/20 animate-pulse transition duration-150 focus:outline-none focus:ring-2 focus:ring-red-500">
              🚨 Emergency Exit
            </button>
          )}
        </div>

        {/* Navigation links */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <div className="text-[9px] text-navy-400 font-extrabold uppercase tracking-widest px-1 mb-2">Navigation</div>
          
          <button onClick={() => setShowGoals(true)}
            className="w-full flex items-center px-3 py-2 bg-gradient-to-r from-amber-500/10 to-orange-500/10 hover:from-amber-500/20 hover:to-orange-500/20 text-amber-400 font-bold rounded-lg text-xs transition duration-150 border border-amber-500/20 mb-2">
            <span aria-hidden="true" className="mr-2 text-sm">🏆</span> Wealth & Life Goals
          </button>

          <button onClick={() => setShowLiveLogs(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">📄</span> Trade Log
          </button>

          <button onClick={() => setShowPDFReports(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">📋</span> PDF Reports
          </button>

          <button onClick={() => setShowBacktest(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">📊</span> Backtesting
          </button>

          <button onClick={() => setShowAnalytics(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">📈</span> P&L Analytics
          </button>

          <button onClick={() => setShowChart(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">🕯️</span> Live Nifty Chart
          </button>

          <button onClick={() => setShowLevelHistory(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">📜</span> Level History
          </button>

          <button onClick={() => setShowUserGuide(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">📖</span> User Guide
          </button>

          <button onClick={() => setShowSettings(true)}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800">
            <span aria-hidden="true" className="mr-2 text-sm">⚙️</span> Settings
          </button>

          {user?.is_admin && (
            <button onClick={() => setShowAdminPanel(true)}
              className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none focus:bg-navy-800 border-t border-navy-800/40 mt-1 pt-2">
              <span aria-hidden="true" className="mr-2 text-sm">🛡️</span> Admin Panel
            </button>
          )}
        </nav>

        {/* Bottom Panel */}
        <div className="p-3 border-t border-navy-800 space-y-1.5">
          <button onClick={handleToggleTheme}
            title={theme === 'dark' ? 'Switch to Obsidian Amethyst Theme' : 'Switch to Midnight Dark Theme'}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-navy-800 hover:text-navy-100 rounded-lg text-xs text-navy-300 transition duration-150 focus:outline-none">
            {theme === 'dark' ? <><span aria-hidden="true" className="mr-2 text-sm">🔮</span> Amethyst Theme</> : <><span aria-hidden="true" className="mr-2 text-sm">🌙</span> Midnight Theme</>}
          </button>

          <button onClick={handleLogout}
            className="w-full flex items-center px-3 py-2 bg-transparent hover:bg-red-950/20 hover:text-red-400 rounded-lg text-xs text-navy-400 transition duration-150 focus:outline-none">
            <span aria-hidden="true" className="mr-2 text-sm">⇥</span> Logout
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden h-screen">
        {/* Dedicated Devotional Mantra Top Banner (Option B) */}
        <DevotionalHeaderBar />

        {/* Top ribbon container with collapse trigger & Status Marquee */}
        <div className="flex items-center bg-navy-950 border-b border-navy-800 select-none pr-4 sticky top-0 z-20 shadow-md">
          <button
            onClick={() => {
              const next = !sidebarCollapsed;
              setSidebarCollapsed(next);
              localStorage.setItem('sidebar_collapsed', String(next));
            }}
            title={sidebarCollapsed ? 'Expand sidebar panel' : 'Collapse sidebar panel'}
            className="h-11 px-4 bg-navy-900 hover:bg-navy-800 border-r border-navy-800 text-xs uppercase font-bold tracking-wider text-navy-300 hover:text-navy-100 flex items-center justify-center gap-1.5 focus:outline-none transition duration-150"
          >
            <span>{sidebarCollapsed ? '▶' : '◀'}</span>
            <span>Menu</span>
          </button>
          
          {sidebarCollapsed && (
            <div className="flex items-center gap-1.5 pl-3 pr-3 h-11 shrink-0 select-none animate-fade-in">
              <img src="/destiny-shield-icon.png" alt="Destiny Shield Icon" className="w-6 h-6 object-contain filter drop-shadow-[0_0_6px_rgba(245,158,11,0.5)]" />
              <span className="text-xs font-black uppercase tracking-wider bg-gradient-to-r from-amber-200 via-amber-400 to-amber-500 bg-clip-text text-transparent whitespace-nowrap">
                DESTINY
              </span>
              <span className="text-[8px] bg-navy-850/60 border border-navy-800 text-navy-450 px-1 py-0.5 rounded font-mono font-bold select-none ml-0.5">
                2026
              </span>
            </div>
          )}

          <div className="flex-1 overflow-hidden">
            <StatusBar />
          </div>
        </div>

        {/* Scrollable content container */}
        <div className="flex-1 overflow-y-auto p-3 min-h-0">

          {/* Error messages */}
        {startMut.isError && (
          <div className="px-4 py-2 border-b border-red-800 bg-red-950/20">
            <Notification
              type="error"
              message={
                <span>
                  {(() => {
                    const errData = (startMut.error as any)?.response?.data?.detail;
                    if (errData?.errors && Array.isArray(errData.errors)) {
                      return `Safety Checks Failed: ${errData.errors.join('; ')}`;
                    }
                    return errData?.message || errData || startMut.error?.message;
                  })()}
                </span>
              }
              onClose={() => startMut.reset()}
            />
          </div>
        )}

        {stopMut.isError && (
          <div className="px-4 py-2 border-b border-red-800 bg-red-950/20">
            <Notification
              type="error"
              message={
                <span>
                  Failed to stop strategy: {(() => {
                    const errData = (stopMut.error as any)?.response?.data?.detail;
                    return errData?.message || errData || stopMut.error?.message;
                  })()}
                </span>
              }
              onClose={() => stopMut.reset()}
            />
          </div>
        )}

        {emergencyExitMut.isError && (
          <div className="px-4 py-2 border-b border-red-800 bg-red-950/20">
            <Notification
              type="error"
              message={
                <span>
                  Emergency exit failed: {(() => {
                    const errData = (emergencyExitMut.error as any)?.response?.data?.detail;
                    return errData?.message || errData || emergencyExitMut.error?.message;
                  })()}
                </span>
              }
              onClose={() => emergencyExitMut.reset()}
            />
          </div>
        )}

          {/* Main grid */}
          <div className="grid grid-cols-12 gap-3">
        {/* Left: NIFTY + Levels */}
        <div className="col-span-12 lg:col-span-3 space-y-3">
          {/* NIFTY price */}
          <div className="glass-card rounded-xl p-4 flex flex-col gap-2 relative overflow-hidden">
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
              {niftyLtp ? (
                <span className="text-3xl font-extrabold text-white font-mono tracking-tight">
                  {niftyLtp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </span>
              ) : (
                <div className="h-9 w-44 bg-navy-800 rounded animate-pulse" />
              )}
            </div>

            {/* Price Tick Sparkline (last 30 ticks) */}
            {sparklineData.length > 1 && (
              <div className="h-9 w-full mt-1 overflow-hidden select-none">
                <SparkContainer width="100%" height="100%">
                  <SparkAreaChart data={sparklineData}>
                    <defs>
                      <linearGradient id="colorNiftySpark" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={niftyChange?.isUp ? '#10b981' : '#f87171'} stopOpacity={0.25}/>
                        <stop offset="95%" stopColor={niftyChange?.isUp ? '#10b981' : '#f87171'} stopOpacity={0.0}/>
                      </linearGradient>
                    </defs>
                    <SparkArea
                      type="monotone"
                      dataKey="value"
                      stroke={niftyChange?.isUp ? '#10b981' : '#f87171'}
                      strokeWidth={1.5}
                      fill="url(#colorNiftySpark)"
                      dot={false}
                      isAnimationActive={false}
                    />
                  </SparkAreaChart>
                </SparkContainer>
              </div>
            )}

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
            ) : (
              <div className="h-6 w-32 bg-navy-800 rounded-full animate-pulse my-0.5" />
            )}

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

            {/* Inline time status warnings inside the card */}
            {status && !status.entries_allowed && (
              <div className="flex items-center gap-1.5 mt-2 text-[11px] text-yellow-500 font-bold bg-yellow-950/20 px-2 py-1.5 rounded border border-yellow-800/40">
                <span aria-hidden="true">⚡</span>
                <span>{getCutoffTimeStr(config?.squareoff_time ?? '15:15')} Passed (No Entries)</span>
              </div>
            )}
            {status?.squareoff_triggered && (
              <div className="flex items-center gap-1.5 mt-2 text-[11px] text-red-400 font-bold bg-red-950/20 px-2 py-1.5 rounded border border-red-800/40 animate-pulse">
                <span aria-hidden="true">⚠️</span>
                <span>Squareoff Triggered ({formatTimeTo12Hour(config?.squareoff_time ?? '15:30')})</span>
              </div>
            )}
          </div>

          {/* Option LTP Tracker */}
          <div className="glass-card rounded-xl p-4 flex flex-col gap-3 relative overflow-hidden shadow-lg border border-navy-800/40">
            <div className="flex items-center justify-between border-b border-navy-800 pb-2">
              <span className="text-xs text-navy-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
                <span>⚡</span> Option LTP Tracker
              </span>
              <span className="text-[10px] text-navy-400 font-mono">Real-time</span>
            </div>

            <div className="space-y-3">
              {/* CE Leg */}
              <div>
                <div className="flex items-center justify-between text-[11px] font-bold text-navy-300 mb-1">
                  <span className="flex items-center gap-1">
                    CALL OPTION (CE)
                    <span className="group relative inline-block cursor-help select-none text-navy-500 hover:text-navy-300">
                      ℹ️
                      <span className="pointer-events-none absolute bottom-full left-0 z-50 mb-1.5 w-52 rounded bg-navy-900 border border-navy-800 p-2 text-[9px] text-navy-200 opacity-0 transition-opacity duration-200 shadow-xl group-hover:opacity-100 leading-normal font-sans font-normal normal-case">
                        <strong>CE Leg State</strong><br/>
                        IDLE: Waiting for trigger.<br/>
                        L1/L2/L3: Active averaging tiers entered based on strategy support bounds.
                      </span>
                    </span>
                  </span>
                  {status?.ce && status.ce.state !== 'IDLE' ? (
                    <span className={clsx(
                      'text-[9px] px-1.5 py-0.5 rounded font-extrabold uppercase tracking-wide',
                      status.ce.state.includes('L3') ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                      status.ce.state.includes('L2') ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      'bg-green-500/10 text-green-400 border border-green-500/20'
                    )}>
                      {status.ce.state.replace('_ENTERED', '')}
                    </span>
                  ) : (
                    <span className="text-[9px] px-1.5 py-0.5 bg-navy-850 text-navy-400 border border-navy-800/40 rounded font-semibold uppercase tracking-wide">
                      IDLE
                    </span>
                  )}
                </div>
                {status?.ce && status.ce.state !== 'IDLE' ? (
                  <div className="bg-navy-950/40 border border-navy-800 rounded-lg p-2.5 space-y-1.5">
                    <div className="text-[10px] font-mono text-navy-300 truncate" title={status.ce.locked_instrument || ''}>
                      {status.ce.locked_instrument}
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className="text-lg font-bold text-white font-mono tracking-tight">
                        ₹{(status.ce.current_ltp ?? 0).toFixed(2)}
                      </span>
                      <span className="text-xs text-navy-400 font-mono">
                        Avg: ₹{(status.ce.entry_avg_price ?? 0).toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="text-navy-400 font-medium">{status.ce.lots} Lots ({status.ce.lots * (config?.lot_size ?? 50)} Qty)</span>
                      <span className={clsx('font-bold font-mono', (status.ce.unrealized_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
                        {status.ce.unrealized_pnl != null
                          ? `${status.ce.unrealized_pnl >= 0 ? '+' : ''}₹${status.ce.unrealized_pnl.toFixed(0)}`
                          : '—'}
                      </span>
                    </div>
                    <PositionRangeVisualizer 
                      status={status.ce}
                      targetPoints={config?.target_points ?? 20}
                      slPoints={config?.sl_points ?? 10}
                    />
                  </div>
                ) : (
                  <div className="bg-navy-950/20 border border-navy-850 border-dashed rounded-lg p-2 text-center text-xs text-navy-450 font-medium">
                    No active call positions
                  </div>
                )}
              </div>

              {/* PE Leg */}
              <div>
                <div className="flex items-center justify-between text-[11px] font-bold text-navy-300 mb-1">
                  <span className="flex items-center gap-1">
                    PUT OPTION (PE)
                    <span className="group relative inline-block cursor-help select-none text-navy-500 hover:text-navy-300">
                      ℹ️
                      <span className="pointer-events-none absolute bottom-full left-0 z-50 mb-1.5 w-52 rounded bg-navy-900 border border-navy-800 p-2 text-[9px] text-navy-200 opacity-0 transition-opacity duration-200 shadow-xl group-hover:opacity-100 leading-normal font-sans font-normal normal-case">
                        <strong>PE Leg State</strong><br/>
                        IDLE: Waiting for trigger.<br/>
                        L1/L2/L3: Active averaging tiers entered based on strategy resistance bounds.
                      </span>
                    </span>
                  </span>
                  {status?.pe && status.pe.state !== 'IDLE' ? (
                    <span className={clsx(
                      'text-[9px] px-1.5 py-0.5 rounded font-extrabold uppercase tracking-wide',
                      status.pe.state.includes('L3') ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                      status.pe.state.includes('L2') ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      'bg-green-500/10 text-green-400 border border-green-500/20'
                    )}>
                      {status.pe.state.replace('_ENTERED', '')}
                    </span>
                  ) : (
                    <span className="text-[9px] px-1.5 py-0.5 bg-navy-850 text-navy-400 border border-navy-800/40 rounded font-semibold uppercase tracking-wide">
                      IDLE
                    </span>
                  )}
                </div>
                {status?.pe && status.pe.state !== 'IDLE' ? (
                  <div className="bg-navy-950/40 border border-navy-800 rounded-lg p-2.5 space-y-1.5">
                    <div className="text-[10px] font-mono text-navy-300 truncate" title={status.pe.locked_instrument || ''}>
                      {status.pe.locked_instrument}
                    </div>
                    <div className="flex items-baseline justify-between">
                      <span className="text-lg font-bold text-white font-mono tracking-tight">
                        ₹{(status.pe.current_ltp ?? 0).toFixed(2)}
                      </span>
                      <span className="text-xs text-navy-400 font-mono">
                        Avg: ₹{(status.pe.entry_avg_price ?? 0).toFixed(2)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-[10px]">
                      <span className="text-navy-400 font-medium">{status.pe.lots} Lots ({status.pe.lots * (config?.lot_size ?? 50)} Qty)</span>
                      <span className={clsx('font-bold font-mono', (status.pe.unrealized_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
                        {status.pe.unrealized_pnl != null
                          ? `${status.pe.unrealized_pnl >= 0 ? '+' : ''}₹${status.pe.unrealized_pnl.toFixed(0)}`
                          : '—'}
                      </span>
                    </div>
                    <PositionRangeVisualizer 
                      status={status.pe}
                      targetPoints={config?.target_points ?? 20}
                      slPoints={config?.sl_points ?? 10}
                    />
                  </div>
                ) : (
                  <div className="bg-navy-950/20 border border-navy-850 border-dashed rounded-lg p-2 text-center text-xs text-navy-450 font-medium">
                    No active put positions
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Level panel */}
          <div className="glass-card rounded-xl p-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs text-navy-300 font-semibold">LEVELS</div>
              <span className="text-[10px] px-1.5 py-0.5 rounded font-extrabold uppercase tracking-wide bg-navy-850 text-navy-300 border border-navy-700/60">
                {config?.strategy_type === 'DESTINY' ? 'Destiny Strategy' : 'Pyramid Strategy'}
              </span>
            </div>
            <LevelPanel status={status} config={config ?? null} isLoading={isConfigLoading} />
          </div>

          {/* Paper trade simulator */}
          {paperTrade && (
            <div className="glass-card rounded-xl p-3">
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
          {/* P&L Summary */}
          <div className="glass-card rounded-xl p-3.5 space-y-2 border border-navy-800/40 shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs text-navy-300 font-semibold uppercase tracking-wider">TODAY'S P&L</span>
              {isPnlLoading ? (
                <div className="h-3.5 w-24 bg-navy-850 rounded animate-pulse" />
              ) : (
                <span className="text-xs text-navy-300 font-mono">{pnl?.total_exits ?? 0} exits | {pnl?.winning_trades ?? 0} wins</span>
              )}
            </div>
            
            <div className="grid grid-cols-2 gap-4 pt-1">
              <div>
                <span className="text-[10px] text-navy-400 font-semibold uppercase tracking-wide block">Gross Return</span>
                {isPnlLoading ? (
                  <div className="h-7 w-24 bg-navy-800 rounded animate-pulse mt-0.5" />
                ) : (
                  <div className={clsx('text-xl font-bold font-mono tracking-tight',
                    todayPnl > 0 ? 'text-green-400' : todayPnl < 0 ? 'text-red-400' : 'text-navy-300')}>
                    {todayPnl >= 0 ? '+' : ''}₹{todayPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                )}
              </div>
              
              <div>
                <span className="text-[10px] text-navy-400 font-semibold uppercase tracking-wide block">Est. Net Return</span>
                {isPnlLoading ? (
                  <div className="h-7 w-24 bg-navy-800 rounded animate-pulse mt-0.5" />
                ) : (
                  <div className={clsx('text-xl font-bold font-mono tracking-tight',
                    estimatedCharges.netPnl > 0 ? 'text-green-400' : estimatedCharges.netPnl < 0 ? 'text-red-400' : 'text-navy-300')}>
                    {estimatedCharges.netPnl >= 0 ? '+' : ''}₹{estimatedCharges.netPnl.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </div>
                )}
              </div>
            </div>

            <div className="pt-2 border-t border-navy-850/80 grid grid-cols-3 gap-2 text-[10px] text-navy-350 select-none">
              <div>
                <span className="text-navy-400">Brokerage:</span>
                <span className="font-mono ml-1 font-bold text-navy-200">₹{estimatedCharges.brokerage.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-navy-400">Taxes & GST:</span>
                <span className="font-mono ml-1 font-bold text-navy-200">₹{estimatedCharges.taxes.toFixed(2)}</span>
              </div>
              <div>
                <span className="text-navy-400">Est. Slippage:</span>
                <span className="font-mono ml-1 font-bold text-navy-200" title="Estimated at 0.1% transaction value">₹{estimatedCharges.slippage.toFixed(2)}</span>
              </div>
            </div>

            {lastPnlTime && !isPnlLoading && (
              <div className="text-[9px] text-navy-400 font-mono text-right pt-0.5 select-none">
                Last calculated {formatTimeAgo(lastPnlTime)}
              </div>
            )}
          </div>

          {/* P&L Chart */}
          <div className="glass-card rounded-xl p-3.5 space-y-3 border border-navy-800/40 shadow-lg">
            <div className="flex items-center justify-between border-b border-navy-800 pb-2">
              <span className="text-xs text-navy-300 font-semibold uppercase tracking-wider">P&L CHART</span>
              <span className="text-[10px] text-navy-400 font-mono">Performance Analytics</span>
            </div>

            {/* Key Stats Bar */}
            <div className="grid grid-cols-3 gap-2 select-none">
              <div className="bg-navy-950/40 border border-navy-800/60 rounded-lg p-2.5 flex flex-col items-center justify-center text-center">
                <span className="text-[8px] text-navy-450 font-bold uppercase tracking-wider block mb-0.5">Win Rate</span>
                <span className="text-xs font-bold text-green-400 font-mono">{stats.winRate}%</span>
              </div>
              <div className="bg-navy-950/40 border border-navy-800/60 rounded-lg p-2.5 flex flex-col items-center justify-center text-center">
                <span className="text-[8px] text-navy-450 font-bold uppercase tracking-wider block mb-0.5">Win Streak</span>
                <span className="text-xs font-bold text-orange-400 font-mono">🔥 {stats.streak} Days</span>
              </div>
              <div className="bg-navy-950/40 border border-navy-800/60 rounded-lg p-2.5 flex flex-col items-center justify-center text-center">
                <span className="text-[8px] text-navy-450 font-bold uppercase tracking-wider block mb-0.5">Profit Factor</span>
                <span className={clsx('text-xs font-bold font-mono', 
                  stats.profitFactor >= 1.5 ? 'text-green-400' : stats.profitFactor >= 1.0 ? 'text-yellow-400' : 'text-red-400'
                )}>
                  {stats.profitFactor}
                </span>
              </div>
            </div>

            <PnLChart data={pnlChartData} />
          </div>

          {/* Trade Log */}
          <div className="glass-card rounded-xl p-3">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-navy-200">TRADE LOG</span>
              <div className="flex items-center gap-2">
                <select
                  value={exportPeriod}
                  onChange={(e) => setExportPeriod(e.target.value)}
                  className="bg-navy-800 border border-navy-700/60 text-[10px] text-navy-200 rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-orange-500 cursor-pointer hover:border-navy-600 transition-colors"
                >
                  <option value="all">All Time</option>
                  <option value="today">Today</option>
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                </select>
                <button
                  onClick={() => handleExportTrades(exportPeriod)}
                  disabled={exportingTrades}
                  className="px-2.5 py-1 bg-navy-850 hover:bg-navy-700 disabled:opacity-40 text-navy-250 hover:text-white rounded text-[10px] font-semibold border border-navy-700 transition flex items-center gap-1 shadow-sm focus:outline-none focus:ring-2 focus:ring-orange-500"
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

          {/* Post-Exit Target Performance Card */}
          <div className="glass-card rounded-xl p-3 space-y-2 border border-navy-800/40 shadow-lg">
            <div className="flex items-center justify-between border-b border-navy-800 pb-2">
              <div className="flex items-center gap-1.5">
                <span className="text-xs select-none">🎯</span>
                <span className="text-xs text-navy-200 font-bold uppercase tracking-wider">Post-Target Performance</span>
              </div>
              <span className="text-[9px] text-emerald-400 font-extrabold uppercase tracking-wider bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 shadow-sm animate-pulse select-none">LIVE TRACKING</span>
            </div>
            
            <div className="space-y-2 max-h-[300px] overflow-auto scrollbar-thin">
              {(() => {
                const targetTrades = trades.filter(t => t.action === 'EXIT' && t.status === 'TARGET');
                
                if (targetTrades.length === 0) {
                  return (
                    <div className="text-navy-450 text-xs text-center py-6 border border-dashed border-navy-850 rounded-lg bg-navy-950/20 select-none">
                      <div className="text-sm mb-0.5 opacity-55">🏁</div>
                      No target exits achieved today yet.
                    </div>
                  );
                }
                
                return targetTrades.map((t) => {
                  const hasPostExit = t.post_exit_high != null && t.post_exit_low != null;
                  const exitPrice = t.avg_price ?? 0;
                  const low = t.post_exit_low ?? exitPrice;
                  const high = t.post_exit_high ?? exitPrice;
                  
                  const range = high - low;
                  const pct = range > 0 ? Math.max(0, Math.min(100, ((exitPrice - low) / range) * 100)) : 50;
                  
                  // Premium Analytics
                  const missedRally = high - exitPrice;
                  const missedRallyPct = exitPrice > 0 ? (missedRally / exitPrice) * 100 : 0;
                  
                  const savedDrop = exitPrice - low;
                  const savedDropPct = exitPrice > 0 ? (savedDrop / exitPrice) * 100 : 0;
                  
                  const formatTime = (timeStrStr: string | null | undefined) => {
                    if (!timeStrStr) return '';
                    try {
                      const d = new Date(timeStrStr);
                      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true });
                    } catch (e) {
                      return '';
                    }
                  };
                  
                  return (
                    <div key={t.id} className="bg-navy-950/50 border border-navy-800 rounded-lg p-2.5 space-y-2 hover:border-navy-700/80 hover:bg-navy-950/70 transition duration-150 shadow-sm">
                      {/* Top Symbol Block */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className={clsx('text-[9px] font-extrabold px-1.5 py-0.5 rounded uppercase tracking-wider border',
                            t.side === 'CE' ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20')}>
                            {t.side === 'CE' ? '▲ CE' : '▼ PE'}
                          </span>
                          <span className="font-mono text-[11px] font-bold text-white tracking-wide" title={t.instrument}>
                            {t.instrument}
                          </span>
                        </div>
                        <span className="text-[9px] font-mono text-navy-450 bg-navy-900/60 border border-navy-800/40 px-1.5 rounded">
                          Level Done
                        </span>
                      </div>
                      
                      {/* Stats Grid */}
                      <div className="grid grid-cols-3 gap-1.5 select-none">
                        <div className="text-center bg-navy-900/50 p-1.5 rounded-md border border-navy-850">
                          <span className="text-navy-450 block text-[8px] uppercase tracking-wider font-semibold mb-0.5">🏁 Target Exit</span>
                          <span className="font-mono font-bold text-white text-xs">₹{exitPrice.toFixed(2)}</span>
                        </div>
                        <div className="text-center bg-emerald-950/10 p-1.5 rounded-md border border-emerald-950/20">
                          <span className="text-emerald-400/90 block text-[8px] uppercase tracking-wider font-bold mb-0.5">📈 Post High</span>
                          <span className="font-mono font-bold text-emerald-400 text-xs">₹{high.toFixed(2)}</span>
                        </div>
                        <div className="text-center bg-rose-950/10 p-1.5 rounded-md border border-rose-950/20">
                          <span className="text-rose-400/90 block text-[8px] uppercase tracking-wider font-bold mb-0.5">📉 Post Low</span>
                          <span className="font-mono font-bold text-rose-400 text-xs">₹{low.toFixed(2)}</span>
                        </div>
                      </div>
                      
                      {/* Advanced Analytics */}
                      <div className="flex gap-1.5 text-[9px] select-none">
                        <div className="flex-1 bg-navy-900/30 border border-navy-850/60 rounded-md p-1.5 flex items-center justify-between">
                          <span className="text-navy-400 font-medium">Missed Run:</span>
                          <span className={clsx('font-mono font-bold', missedRally > 0 ? 'text-emerald-400' : 'text-navy-400')}>
                            {missedRally > 0 ? `+₹${missedRally.toFixed(1)} (+${missedRallyPct.toFixed(0)}%)` : 'None'}
                          </span>
                        </div>
                        <div className="flex-1 bg-navy-900/30 border border-navy-850/60 rounded-md p-1.5 flex items-center justify-between">
                          <span className="text-navy-450 font-medium">Saved Drop:</span>
                          <span className={clsx('font-mono font-bold', savedDrop > 0 ? 'text-amber-400' : 'text-navy-450')}>
                            {savedDrop > 0 ? `-₹${savedDrop.toFixed(1)} (-${savedDropPct.toFixed(0)}%)` : 'None'}
                          </span>
                        </div>
                      </div>
                      
                      {/* Visual Range Slider */}
                      {hasPostExit && range > 0 && (
                        <div className="space-y-1.5 pt-0.5">
                          <div className="flex-1 h-1.5 rounded-full bg-navy-950 border border-navy-850/80 relative overflow-visible shadow-inner">
                            <div className="absolute inset-0 rounded-full bg-gradient-to-r from-rose-500/10 via-emerald-500/5 to-emerald-500/25"></div>
                            <div 
                              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 transition-all duration-300" 
                              style={{ left: `${pct}%` }}
                            >
                              <span className="absolute -inset-1 rounded-full bg-brand/35 animate-ping opacity-75"></span>
                              <div className="w-2.5 h-2.5 rounded-full bg-brand ring-2 ring-navy-950 shadow-lg relative z-10"></div>
                            </div>
                          </div>
                          
                          <div className="flex justify-between text-[9px] text-navy-400 font-mono px-0.5">
                            <span className="flex items-center gap-0.5">
                              <span>Low:</span>
                              <strong className="text-navy-300">{formatTime(t.post_exit_low_time) || '—'}</strong>
                            </span>
                            <span className="text-navy-350 bg-navy-900/50 px-1.5 py-0.5 rounded border border-navy-850/40 select-none text-[9px]">
                              Exit at <strong className="text-white font-bold">{pct.toFixed(0)}%</strong> of range
                            </span>
                            <span className="flex items-center gap-0.5">
                              <span>High:</span>
                              <strong className="text-navy-300">{formatTime(t.post_exit_high_time) || '—'}</strong>
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                });
              })()}
            </div>
          </div>
        </div>

        {/* Right: AI Observer + Open Positions */}
        <div className="col-span-12 lg:col-span-4 space-y-3">
          {/* Open Positions */}
          <div className="glass-card rounded-xl p-3">
            <div className="text-xs text-navy-300 mb-2 font-semibold">OPEN POSITIONS</div>
            {[status?.ce, status?.pe].map((sm, i) => (
              sm && sm.state !== 'IDLE' && sm.state !== 'BLOCKED' && (
                <div key={i} className="flex items-center justify-between text-xs py-1.5 border-b border-navy-850">
                  <span className={i === 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                    {i === 0 ? '▲ CE' : '▼ PE'}
                  </span>
                  <span className="text-navy-100">{sm.locked_instrument}</span>
                  <span className="text-navy-300">{sm.lots}L</span>
                  <span className={clsx('tabular-nums font-bold',
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

          {/* Active High/Low Tracker */}
          <ActiveHighLowTracker status={status} trades={trades} />

          {/* Kite Connection Status */}
          <KiteStatus />

          {/* AI Observer */}
          <div className="glass-card rounded-xl p-3">
            <div className="text-xs text-navy-300 mb-2 font-semibold"><span aria-hidden="true">🤖</span> AI OBSERVER</div>
            <AIObserver />
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="mt-2.5 border-t border-navy-800/80 py-1.5 text-[10px] text-navy-400 w-full">
        <div className="flex flex-col sm:flex-row justify-between items-center gap-1 px-1">
          <span>Copyright © 2026. All rights reserved.</span>
          <span>
            Developed by{' '}
            <a
              href="https://nextginfosoft.com/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand font-bold hover:underline hover:text-brand-dark transition-all duration-150"
            >
              NextG Infosoft Technology(P)
            </a>
          </span>
        </div>
      </footer>
        </div>

      {showSettings && <Settings user={user} onClose={() => { setShowSettings(false); qc.invalidateQueries() }} />}
      {showLiveLogs && <LiveLogModal onClose={() => setShowLiveLogs(false)} />}
      {showAdminPanel && <AdminPanel onClose={() => setShowAdminPanel(false)} />}
      {showPDFReports && <PDFReportsModal onClose={() => setShowPDFReports(false)} />}
      {showBacktest && <BacktestModal onClose={() => setShowBacktest(false)} />}
      {showUserGuide && <UserGuide onClose={() => setShowUserGuide(false)} />}
      {showAnalytics && <Analytics onClose={() => setShowAnalytics(false)} />}
      {showChart && <ChartModal onClose={() => setShowChart(false)} />}
      {showLevelHistory && <LevelHistoryModal isOpen={showLevelHistory} onClose={() => setShowLevelHistory(false)} />}
      <GoalsModal isOpen={showGoals} onClose={() => setShowGoals(false)} />

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
      </main>
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

interface PositionRangeVisualizerProps {
  status: SideStatus
  targetPoints: number
  slPoints: number
}

export function PositionRangeVisualizer({ status, targetPoints, slPoints }: PositionRangeVisualizerProps) {
  const currentLtp = status.current_ltp
  const entryAvgPrice = status.entry_avg_price
  const activeLow = status.active_low
  const activeHigh = status.active_high

  if (currentLtp == null || entryAvgPrice == null) return null

  // Determine Stop Loss price. 
  // It is active at L3. We use the level3 entry price if available, otherwise fallback to average entry price.
  const isL3 = status.state.includes('L3')
  const slBasePrice = (isL3 && status.level3_entry_price) ? status.level3_entry_price : entryAvgPrice
  const slPrice = slBasePrice - slPoints
  const targetPrice = entryAvgPrice + targetPoints

  // Track low and high
  const lowPrice = activeLow != null ? activeLow : Math.min(currentLtp, entryAvgPrice)
  const highPrice = activeHigh != null ? activeHigh : Math.max(currentLtp, entryAvgPrice)

  // Calculate percentages (clamped between 0 and 100)
  const getPercent = (price: number) => {
    const range = targetPrice - slPrice
    if (range <= 0) return 0
    const pct = ((price - slPrice) / range) * 100
    return Math.min(Math.max(pct, 0), 100)
  }

  const ltpPct = getPercent(currentLtp)
  const avgPct = getPercent(entryAvgPrice)
  const lowPct = getPercent(lowPrice)
  const highPct = getPercent(highPrice)

  return (
    <div className="mt-3.5 space-y-1.5 border-t border-navy-800/80 pt-2.5">
      <div className="flex justify-between text-[9px] text-navy-400 font-mono">
        <span>SL: ₹{slPrice.toFixed(1)} {!isL3 && <span className="text-[8px] text-navy-500 font-sans italic">(Inactive)</span>}</span>
        <span>Target: ₹{targetPrice.toFixed(1)}</span>
      </div>

      <div className="relative h-1.5 bg-navy-900 border border-navy-850 rounded-full my-2.5">
        {/* Active high/low range bar */}
        <div 
          className="absolute h-full bg-blue-500/10 rounded-full border-x border-blue-500/20"
          style={{ left: `${lowPct}%`, right: `${100 - highPct}%` }}
        />

        {/* Active Low marker (Red dot) */}
        <div 
          className="absolute -top-[3px] w-2.5 h-2.5 bg-red-500 rounded-full border border-navy-950 -ml-1.25 shadow-lg shadow-red-500/30 cursor-help"
          style={{ left: `${lowPct}%` }}
          title={`Active Low: ₹${lowPrice.toFixed(2)}`}
        />

        {/* Active High marker (Green dot) */}
        <div 
          className="absolute -top-[3px] w-2.5 h-2.5 bg-green-500 rounded-full border border-navy-950 -ml-1.25 shadow-lg shadow-green-500/30 cursor-help"
          style={{ left: `${highPct}%` }}
          title={`Active High: ₹${highPrice.toFixed(2)}`}
        />

        {/* Avg entry price marker (Yellow diamond/square) */}
        <div 
          className="absolute -top-[3px] w-2.5 h-2.5 bg-amber-400 rotate-45 border border-navy-950 -ml-1.25 shadow-lg shadow-amber-400/30 cursor-help"
          style={{ left: `${avgPct}%` }}
          title={`Avg Price: ₹${entryAvgPrice.toFixed(2)}`}
        />

        {/* Current price marker (Glow blue pulse) */}
        <div 
          className="absolute -top-1 w-3.5 h-3.5 bg-blue-400 rounded-full border-2 border-navy-950 -ml-1.75 shadow-lg shadow-blue-400/80 animate-pulse cursor-help"
          style={{ left: `${ltpPct}%` }}
          title={`Current Price: ₹${currentLtp.toFixed(2)}`}
        />
      </div>

      <div className="flex justify-between text-[9px] text-navy-300 font-mono pt-0.5">
        <span className="text-red-400">Min: ₹{lowPrice.toFixed(1)}</span>
        <span className="text-amber-400 font-bold">Avg: ₹{entryAvgPrice.toFixed(1)}</span>
        <span className="text-green-400">Max: ₹{highPrice.toFixed(1)}</span>
      </div>
    </div>
  )
}

interface ActiveHighLowTrackerProps {
  status: StrategyStatus | null
  trades: any[]
}

export function ActiveHighLowTracker({ status, trades }: ActiveHighLowTrackerProps) {
  const [lastCE, setLastCE] = useState<SideStatus | null>(() => {
    try {
      const saved = localStorage.getItem('last_ce_tracking')
      return saved ? JSON.parse(saved) : null
    } catch (e) {
      return null
    }
  })

  const [lastPE, setLastPE] = useState<SideStatus | null>(() => {
    try {
      const saved = localStorage.getItem('last_pe_tracking')
      return saved ? JSON.parse(saved) : null
    } catch (e) {
      return null
    }
  })

  // Detect active state and store it
  useEffect(() => {
    if (status?.ce && status.ce.state !== 'IDLE') {
      setLastCE(status.ce)
      localStorage.setItem('last_ce_tracking', JSON.stringify(status.ce))
    }
  }, [status?.ce])

  useEffect(() => {
    if (status?.pe && status.pe.state !== 'IDLE') {
      setLastPE(status.pe)
      localStorage.setItem('last_pe_tracking', JSON.stringify(status.pe))
    }
  }, [status?.pe])

  // Clear stored last tracking when starting a fresh session or resetting (no trades in logs)
  useEffect(() => {
    if (trades.length === 0) {
      setLastCE(null)
      setLastPE(null)
      localStorage.removeItem('last_ce_tracking')
      localStorage.removeItem('last_pe_tracking')
    }
  }, [trades.length])

  if (!status) return null

  const activeCE = status.ce && status.ce.state !== 'IDLE'
  const activePE = status.pe && status.pe.state !== 'IDLE'

  const formatTime = (timeStr: string | null | undefined) => {
    if (!timeStr) return ''
    try {
      const d = new Date(timeStr)
      if (isNaN(d.getTime())) return ''
      return d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })
    } catch (e) {
      return ''
    }
  }

  const renderLegRange = (leg: SideStatus, side: 'CE' | 'PE', isLive: boolean) => {
    const current = leg.current_ltp
    const avg = leg.entry_avg_price
    const low = leg.active_low
    const high = leg.active_high

    if (current == null || avg == null || low == null || high == null) {
      return (
        <div className="text-[10px] text-navy-450 italic py-2 text-center bg-navy-950/20 border border-navy-850/40 rounded-lg">
          Awaiting real-time price metrics for {side} leg...
        </div>
      )
    }

    const range = high - low
    // Calculate percentage position of current ltp within [low, high] range
    const pct = range > 0 ? Math.max(0, Math.min(100, ((current - low) / range) * 100)) : 50
    // Calculate percentage position of average entry price within [low, high] range
    const avgPct = range > 0 ? Math.max(0, Math.min(100, ((avg - low) / range) * 100)) : 50

    const isCE = side === 'CE'

    return (
      <div className={clsx(
        'border rounded-lg p-3 space-y-2.5 transition duration-150 shadow-sm relative overflow-hidden',
        isLive 
          ? 'bg-navy-950/50 border-navy-800 hover:border-navy-700/60' 
          : 'bg-navy-950/30 border-navy-850/60 opacity-75'
      )}>
        {/* watermark/indicator for historical data */}
        {!isLive && (
          <div className="absolute top-0 right-0 left-0 h-[2px] bg-navy-700/50" />
        )}

        {/* Title / Symbol */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <span className={clsx('text-[9px] font-extrabold px-1.5 py-0.5 rounded border uppercase tracking-wider',
              isCE ? 'bg-green-500/10 text-green-400 border-green-500/20' : 'bg-red-500/10 text-red-400 border-red-500/20',
              !isLive && 'filter saturate-50 opacity-80')}>
              {isCE ? '▲ CE' : '▼ PE'}
            </span>
            <span className={clsx('font-mono text-xs font-bold tracking-wide truncate max-w-[130px]',
              isLive ? 'text-white' : 'text-navy-300')} title={leg.locked_instrument || ''}>
              {leg.locked_instrument}
            </span>
          </div>
          <span className={clsx('text-[8.5px] font-extrabold px-1.5 py-0.5 border rounded uppercase tracking-wide',
            isLive 
              ? 'bg-navy-850 border-navy-800 text-navy-300' 
              : 'bg-navy-900 border-navy-850 text-navy-450')}>
            {isLive ? leg.state.replace('_ENTERED', '') : 'SQUARED OFF'}
          </span>
        </div>

        {/* Live LTP & PNL */}
        <div className="flex justify-between items-baseline select-none">
          <div className="space-y-0.5">
            <span className="text-[9px] text-navy-450 uppercase font-semibold block">{isLive ? 'Current LTP' : 'Final LTP'}</span>
            <span className={clsx('text-base font-extrabold font-mono tracking-tight',
              isLive ? 'text-white' : 'text-navy-200')}>₹{current.toFixed(2)}</span>
          </div>
          <div className="text-right space-y-0.5">
            <span className="text-[9px] text-navy-450 uppercase font-semibold block">{isLive ? 'Unrealized P&L' : 'Final P&L'}</span>
            <span className={clsx('font-mono text-sm font-extrabold tracking-tight',
              !isLive ? 'text-navy-400' : (leg.unrealized_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400')}>
              {isLive 
                ? (leg.unrealized_pnl != null ? `${leg.unrealized_pnl >= 0 ? '+' : ''}₹${leg.unrealized_pnl.toFixed(0)}` : '—')
                : 'Closed'
              }
            </span>
          </div>
        </div>

        {/* Min/Max Grid */}
        <div className="grid grid-cols-2 gap-2 pt-1.5 border-t border-navy-850/60 select-none">
          <div className="bg-rose-950/10 p-2 rounded-md border border-rose-950/20 flex flex-col justify-between">
            <div>
              <span className="text-rose-400 block text-[8px] uppercase tracking-wider font-bold mb-0.5">📉 Active Low</span>
              <span className="font-mono font-bold text-rose-450 text-xs">₹{low.toFixed(2)}</span>
            </div>
            {leg.active_low_time && (
              <span className="text-[8px] text-navy-400 font-mono mt-1 block opacity-75">
                {formatTime(leg.active_low_time)}
              </span>
            )}
          </div>
          <div className="bg-emerald-950/10 p-2 rounded-md border border-emerald-950/20 flex flex-col justify-between">
            <div>
              <span className="text-emerald-400 block text-[8px] uppercase tracking-wider font-bold mb-0.5">📈 Active High</span>
              <span className="font-mono font-bold text-emerald-450 text-xs">₹{high.toFixed(2)}</span>
            </div>
            {leg.active_high_time && (
              <span className="text-[8px] text-navy-400 font-mono mt-1 block opacity-75">
                {formatTime(leg.active_high_time)}
              </span>
            )}
          </div>
        </div>

        {/* Visual Progress Bar representing the range between Low and High */}
        <div className="space-y-1.5 pt-1.5">
          <div className="flex justify-between text-[8.5px] text-navy-450 font-mono select-none font-medium">
            <span>Min: ₹{low.toFixed(1)}</span>
            <span>Max: ₹{high.toFixed(1)}</span>
          </div>
          <div className="relative h-1.5 bg-navy-950 border border-navy-850 rounded-full overflow-visible shadow-inner">
            {/* The active range highlight between Low and High */}
            <div className="absolute inset-y-0 bg-blue-500/5 rounded-full left-0 right-0"></div>
            
            {/* Avg entry price marker */}
            <div 
              className="absolute -top-[3px] w-2.5 h-2.5 bg-amber-400 rotate-45 border border-navy-950 -ml-1.25 shadow-md shadow-amber-400/30 cursor-help"
              style={{ left: `${avgPct}%` }}
              title={`Avg: ₹${avg.toFixed(2)}`}
            />

            {/* Current LTP marker with pulsing glow */}
            <div 
              className={clsx(
                'absolute -top-[3.5px] w-2.5 h-2.5 rounded-full border border-navy-950 -ml-1.25 shadow-lg cursor-help flex items-center justify-center',
                isLive ? 'bg-blue-400 shadow-blue-400/80' : 'bg-navy-400 shadow-none'
              )}
              style={{ left: `${pct}%` }}
              title={`LTP: ₹${current.toFixed(2)}`}
            >
              {isLive && (
                <span className="absolute w-4 h-4 rounded-full bg-blue-400/35 animate-ping opacity-60"></span>
              )}
            </div>
          </div>
          <div className="flex justify-between text-[8px] font-mono text-navy-400 pt-0.5 select-none">
            <span className="text-amber-400/80 font-bold">Avg Entry: ₹{avg.toFixed(1)}</span>
            <span>LTP at <strong className={isLive ? 'text-white font-bold' : 'text-navy-300'}>{pct.toFixed(0)}%</strong> of range</span>
          </div>
        </div>
      </div>
    )
  }

  // Display conditions:
  // If there are active positions, show live range tracking.
  // If there are NO active positions, but we have stored last active ranges, show them.
  // Otherwise, show the idle placeholder.

  const showCE = activeCE || lastCE != null
  const showPE = activePE || lastPE != null

  const isDisplayingSaved = !activeCE && !activePE && (lastCE != null || lastPE != null)
  const isCurrentlyActive = activeCE || activePE

  return (
    <div className="glass-card rounded-xl p-3.5 flex flex-col gap-3 relative overflow-hidden shadow-lg border border-navy-800/40">
      <div className="flex items-center justify-between border-b border-navy-800 pb-2.5 select-none">
        <span className="text-xs text-navy-300 font-bold uppercase tracking-wider flex items-center gap-1.5">
          <span className={clsx('text-sky-400', isCurrentlyActive && 'animate-pulse')}>📊</span> 
          {isDisplayingSaved ? 'Last Tracked Range' : 'Live Range Tracking'}
        </span>
        <span className={clsx('text-[8.5px] font-extrabold uppercase tracking-wider px-1.5 py-0.5 rounded border shadow-sm transition-all duration-150 flex items-center gap-1.5',
          isCurrentlyActive 
            ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20 animate-pulse' 
            : isDisplayingSaved
              ? 'text-navy-450 bg-navy-900 border-navy-850'
              : 'text-green-400 bg-green-500/10 border-green-500/20 animate-pulse'
        )}>
          {!isDisplayingSaved && (
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500"></span>
            </span>
          )}
          {isCurrentlyActive ? 'Active Extremes' : isDisplayingSaved ? 'Stopped / Saved' : 'Live Tracking'}
        </span>
      </div>

      {!showCE && !showPE ? (
        <div className="text-navy-450 text-[11px] text-center py-6 border border-dashed border-navy-850 rounded-lg bg-navy-950/20 select-none">
          <div className="text-sm mb-1 opacity-55">⏳</div>
          No active positions. Tracking will activate automatically upon entry.
        </div>
      ) : (
        <div className="space-y-3">
          {activeCE ? renderLegRange(status.ce, 'CE', true) : (lastCE && renderLegRange(lastCE, 'CE', false))}
          {activePE ? renderLegRange(status.pe, 'PE', true) : (lastPE && renderLegRange(lastPE, 'PE', false))}
        </div>
      )}
    </div>
  )
}

