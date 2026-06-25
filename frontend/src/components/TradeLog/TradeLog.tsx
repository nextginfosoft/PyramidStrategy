import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Trade } from '../../types'
import { tradesApi, configApi } from '../../services/api'
import clsx from 'clsx'
import { format } from 'date-fns'

const getLocalDateString = (date: Date) => {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const getRangeDates = (range: string) => {
  const today = new Date()
  switch (range) {
    case 'today':
      return { from: getLocalDateString(today), to: getLocalDateString(today) }
    case 'yesterday': {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      return { from: getLocalDateString(yesterday), to: getLocalDateString(yesterday) }
    }
    case 'last7': {
      const last7 = new Date()
      last7.setDate(last7.getDate() - 6)
      return { from: getLocalDateString(last7), to: getLocalDateString(today) }
    }
    case 'last30': {
      const last30 = new Date()
      last30.setDate(last30.getDate() - 29)
      return { from: getLocalDateString(last30), to: getLocalDateString(today) }
    }
    default:
      return { from: '', to: '' }
  }
}

export function TradeLog() {
  const [dateRange, setDateRange] = useState('today')
  const [customFrom, setCustomFrom] = useState('')
  const [customTo, setCustomTo] = useState('')
  const [sideFilter, setSideFilter] = useState('all')
  const [levelFilter, setLevelFilter] = useState('all')
  const [outcomeFilter, setOutcomeFilter] = useState('all')

  // Calculate API parameters
  const apiParams = useMemo(() => {
    if (dateRange === 'today') return { isToday: true }
    if (dateRange === 'custom') {
      return {
        isToday: false,
        from_date: customFrom || undefined,
        to_date: customTo || undefined,
      }
    }
    const { from, to } = getRangeDates(dateRange)
    return {
      isToday: false,
      from_date: from,
      to_date: to,
    }
  }, [dateRange, customFrom, customTo])

  // Fetch strategy configuration to calculate target & SL prices
  const { data: config } = useQuery({
    queryKey: ['strategy-config'],
    queryFn: configApi.getStrategy,
  })

  const targetPoints = config?.target_points ?? 20
  const slPoints = config?.sl_points ?? 10

  // Fetch trades
  const { data: allTrades = [] as Trade[], isLoading } = useQuery<Trade[]>({
    queryKey: ['trades-log-data', apiParams],
    queryFn: async (): Promise<Trade[]> => {
      if (apiParams.isToday) {
        return tradesApi.getToday()
      } else {
        return tradesApi.getHistory({
          from_date: apiParams.from_date,
          to_date: apiParams.to_date,
          limit: 200,
        })
      }
    },
    refetchInterval: apiParams.isToday ? 3000 : false,
  })

  // Pre-calculate running average, target, and stop loss prices chronologically
  const decoratedTrades = useMemo(() => {
    // Sort chronologically by ID to calculate correctly
    const sorted = [...allTrades].sort((a, b) => a.id - b.id)

    // Track running average details per trade date, side, and instrument
    const positionStates: Record<string, {
      totalQty: number
      totalInvested: number
      runningAvgPrice: number
      level3EntryPrice: number | null
    }> = {}

    const decorated = sorted.map((t) => {
      const key = `${t.trade_date}_${t.side}_${t.instrument}`
      if (!positionStates[key]) {
        positionStates[key] = {
          totalQty: 0,
          totalInvested: 0,
          runningAvgPrice: 0,
          level3EntryPrice: null
        }
      }

      const state = positionStates[key]
      const actualPrice = t.avg_price ?? 0

      let rowAvgPrice = 0
      let rowTargetPrice: number | null = null
      let rowSlPrice: number | null = null

      if (t.action === 'BUY') {
        state.totalQty += t.qty
        state.totalInvested += t.qty * actualPrice
        state.runningAvgPrice = state.totalInvested / state.totalQty
        rowAvgPrice = state.runningAvgPrice

        // Target is relative to the calculated Average Entry Price at this level
        rowTargetPrice = state.runningAvgPrice + targetPoints

        // Stop Loss is active and calculated at Level 3 (R3/S3), based on Level 3 entry price
        const isL3 = t.level === 'L3' || t.level === 'R3' || t.level === 'S3'
        if (isL3) {
          state.level3EntryPrice = actualPrice
          rowSlPrice = actualPrice - slPoints
        }
      } else if (t.action === 'EXIT') {
        // Exit shows the average entry price of the position when it was open
        rowAvgPrice = state.runningAvgPrice

        if (state.level3EntryPrice) {
          rowSlPrice = state.level3EntryPrice - slPoints
        }

        // Reset the running position state for this side/instrument
        positionStates[key] = {
          totalQty: 0,
          totalInvested: 0,
          runningAvgPrice: 0,
          level3EntryPrice: null
        }
      }

      return {
        ...t,
        actual_price: actualPrice,
        avg_entry_price: rowAvgPrice,
        target_price: rowTargetPrice,
        sl_price: rowSlPrice
      }
    })

    return decorated
  }, [allTrades, targetPoints, slPoints])

  // Apply filters locally on the decorated trades
  const filteredTrades = useMemo(() => {
    return decoratedTrades.filter((t) => {
      // 1. Side filter
      if (sideFilter !== 'all' && t.side !== sideFilter) {
        return false
      }

      // 2. Level filter
      if (levelFilter !== 'all') {
        const matchesLevel = 
          (levelFilter === 'L1' && (t.level === 'L1' || t.level === 'R1' || t.level === 'S1')) ||
          (levelFilter === 'L2' && (t.level === 'L2' || t.level === 'R2' || t.level === 'S2')) ||
          (levelFilter === 'L3' && (t.level === 'L3' || t.level === 'R3' || t.level === 'S3'))
        if (!matchesLevel) return false
      }

      // 3. Outcome filter
      if (outcomeFilter !== 'all') {
        const hasPnl = t.pnl != null
        const isExit = t.action === 'EXIT'
        if (outcomeFilter === 'wins') {
          if (!isExit || !hasPnl || t.pnl! <= 0) return false
        } else if (outcomeFilter === 'losses') {
          if (!isExit || !hasPnl || t.pnl! > 0) return false
        } else if (outcomeFilter === 'open') {
          if (t.status !== 'OPEN') return false
        }
      }

      return true
    })
  }, [decoratedTrades, sideFilter, levelFilter, outcomeFilter])

  const selectClass = "bg-navy-800 border border-navy-700/60 text-[11px] text-navy-100 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-brand cursor-pointer hover:border-navy-600 transition-colors"

  return (
    <div className="space-y-3">
      {/* Filters Container */}
      <div className="flex flex-col gap-2.5 p-2 bg-navy-950/40 rounded-lg border border-navy-800/80">
        <div className="flex flex-wrap gap-2 items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-navy-300 font-bold uppercase tracking-wider">Range:</span>
            <select
              value={dateRange}
              onChange={e => setDateRange(e.target.value)}
              className={selectClass}
            >
              <option value="today">Today</option>
              <option value="yesterday">Yesterday</option>
              <option value="last7">Last 7 Days</option>
              <option value="last30">Last 30 Days</option>
              <option value="custom">Custom Range</option>
            </select>

            {dateRange === 'custom' && (
              <div className="flex items-center gap-1 animate-fade-in">
                <input
                  type="date"
                  value={customFrom}
                  onChange={e => setCustomFrom(e.target.value)}
                  className="bg-navy-800 border border-navy-700 text-[10px] text-white rounded px-1.5 py-0.5 focus:ring-1 focus:ring-orange-500 focus:outline-none font-mono"
                />
                <span className="text-[10px] text-navy-400">to</span>
                <input
                  type="date"
                  value={customTo}
                  onChange={e => setCustomTo(e.target.value)}
                  className="bg-navy-800 border border-navy-700 text-[10px] text-white rounded px-1.5 py-0.5 focus:ring-1 focus:ring-orange-500 focus:outline-none font-mono"
                />
              </div>
            )}
          </div>

          <div className="text-[10px] text-navy-400 font-mono">
            {isLoading ? 'Loading...' : `${filteredTrades.length} / ${allTrades.length} trades`}
          </div>
        </div>

        <div className="flex flex-wrap gap-2.5 items-center border-t border-navy-800/40 pt-2">
          <span className="text-[10px] text-navy-300 font-bold uppercase tracking-wider">Filters:</span>
          
          <select
            value={sideFilter}
            onChange={e => setSideFilter(e.target.value)}
            className={selectClass}
          >
            <option value="all">All Sides</option>
            <option value="CE">CE Only</option>
            <option value="PE">PE Only</option>
          </select>

          <select
            value={levelFilter}
            onChange={e => setLevelFilter(e.target.value)}
            className={selectClass}
          >
            <option value="all">All Levels</option>
            <option value="L1">L1 (R1/S1)</option>
            <option value="L2">L2 (R2/S2)</option>
            <option value="L3">L3 (R3/S3)</option>
          </select>

          <select
            value={outcomeFilter}
            onChange={e => setOutcomeFilter(e.target.value)}
            className={selectClass}
          >
            <option value="all">All Outcomes</option>
            <option value="wins">Wins</option>
            <option value="losses">Losses</option>
            <option value="open">Open Positions</option>
          </select>
        </div>
      </div>

      {/* Table Container */}
      <div className="overflow-auto max-h-64 scrollbar-thin">
        {!filteredTrades.length ? (
          <div className="text-navy-300 text-xs text-center py-8">
            {isLoading ? 'Loading trades...' : 'No matching trades found'}
          </div>
        ) : (
          <table className="w-full min-w-[500px] sm:min-w-full text-xs">
            <thead className="sticky top-0 bg-navy-900 z-10 text-[10px] uppercase tracking-wider">
              <tr className="text-navy-300 border-b border-navy-700">
                <th className="text-left py-1.5 pr-2">Date/Time</th>
                <th className="text-left pr-2">Side</th>
                <th className="text-left pr-2 hidden sm:table-cell">Lvl</th>
                <th className="text-left pr-2">Action</th>
                <th className="text-right pr-2">Actual Price</th>
                <th className="text-right pr-2">AVG Price</th>
                <th className="text-right pr-2">Target Price</th>
                <th className="text-right pr-2">Stop Loss</th>
                <th className="text-right pr-2">Lots</th>
                <th className="text-right">P&L</th>
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((t) => {
                return (
                  <tr key={t.id} className="border-b border-navy-800 hover:bg-navy-900/50 transition-colors">
                    <td className="py-1.5 pr-2 text-navy-300 whitespace-nowrap">
                      {dateRange === 'today' 
                        ? format(new Date(t.created_at), 'HH:mm:ss')
                        : format(new Date(t.created_at), 'dd MMM HH:mm:ss')}
                    </td>
                    <td className={clsx('pr-2 font-bold', t.side === 'CE' ? 'text-green-400' : 'text-red-400')}>
                      {t.side === 'CE' ? '▲ CE' : '▼ PE'}
                    </td>
                    <td className="pr-2 text-navy-200 hidden sm:table-cell">
                      {t.level === 'L1'
                        ? (t.side === 'CE' ? 'S1' : 'R1')
                        : t.level === 'L2'
                        ? (t.side === 'CE' ? 'S2' : 'R2')
                        : t.level === 'L3'
                        ? (t.side === 'CE' ? 'S3' : 'R3')
                        : t.level}
                    </td>
                    <td className={clsx('pr-2 font-medium', t.action === 'BUY' ? 'text-blue-400' : 'text-orange-400')}>
                      {t.action}
                    </td>
                    <td className="text-right pr-2 text-navy-100 font-mono">
                      {t.actual_price ? `₹${t.actual_price.toFixed(2)}` : '—'}
                    </td>
                    <td className="text-right pr-2 text-navy-200 font-mono">
                      {t.avg_entry_price ? `₹${t.avg_entry_price.toFixed(2)}` : '—'}
                    </td>
                    <td className="text-right pr-2 text-green-400/90 font-mono">
                      {t.action === 'BUY' && t.target_price ? `₹${t.target_price.toFixed(2)}` : '—'}
                    </td>
                    <td className="text-right pr-2 text-red-400/90 font-mono">
                      {t.sl_price ? `₹${t.sl_price.toFixed(2)}` : '—'}
                    </td>
                    <td className="text-right pr-2 text-navy-200 font-mono">{t.lots}</td>
                    <td className={clsx('text-right font-mono font-semibold',
                      t.pnl == null ? 'text-navy-300'
                      : t.pnl >= 0 ? 'text-green-400' : 'text-red-400')}>
                      {t.pnl != null
                        ? `${t.pnl >= 0 ? '+' : ''}₹${t.pnl.toFixed(0)}`
                        : (t.status === 'OPEN' ? <span className="text-yellow-400 font-bold uppercase tracking-wider text-[10px] bg-yellow-950/40 px-1 py-0.5 rounded border border-yellow-500/20">OPEN</span> : '—')}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
