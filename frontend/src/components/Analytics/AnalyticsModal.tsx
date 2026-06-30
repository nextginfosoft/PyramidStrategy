import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { analyticsApi } from '../../services/api'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'

export function Analytics({ onClose }: { onClose: () => void }) {
  const today = new Date()
  const startOfYear = new Date(today.getFullYear(), 0, 1) // Start of year
  
  const [startDate, setStartDate] = useState(startOfYear.toISOString().slice(0, 10))
  const [endDate, setEndDate] = useState(today.toISOString().slice(0, 10))
  const [selectedMonth, setSelectedMonth] = useState(today.getMonth()) // 0-11
  const [selectedYear, setSelectedYear] = useState(today.getFullYear())
  const [exporting, setExporting] = useState(false)

  // Query analytics data
  const { data, isLoading } = useQuery<any>({
    queryKey: ['pnl-analytics', startDate, endDate],
    queryFn: () => analyticsApi.getPnlSummary(startDate, endDate),
    placeholderData: (prev: any) => prev
  })

  // Format daily_data into a map keyed by YYYY-MM-DD
  const dailyDataMap = useMemo(() => {
    const map: Record<string, any> = {}
    if (data?.daily_data) {
      data.daily_data.forEach((r: any) => {
        map[r.date] = r
      })
    }
    return map
  }, [data])

  // Aggregate weekly net P&Ls for the active calendar view month
  const weeklyTotals = useMemo(() => {
    const totals: Record<number, number> = {} // maps week number (0-5) -> net pnl sum
    if (!data?.daily_data) return totals

    const totalDays = new Date(selectedYear, selectedMonth + 1, 0).getDate()
    for (let day = 1; day <= totalDays; day++) {
      const dateStr = `${selectedYear}-${String(selectedMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
      const dayData = dailyDataMap[dateStr]
      if (dayData) {
        // Find which calendar week row this day falls in
        const firstDayOfMonth = new Date(selectedYear, selectedMonth, 1).getDay()
        const weekIndex = Math.floor((day + firstDayOfMonth - 1) / 7)
        totals[weekIndex] = (totals[weekIndex] || 0) + dayData.net_pnl
      }
    }
    return totals
  }, [dailyDataMap, selectedMonth, selectedYear, data])

  const handleExportCSV = async () => {
    setExporting(true)
    try {
      const blob = await analyticsApi.exportCsv(startDate, endDate)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `pyramid_pnl_report_${startDate}_to_${endDate}.csv`)
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (err) {
      console.error("CSV Export failed:", err)
    } finally {
      setExporting(false)
    }
  }

  // Draw Calendar Cells
  const calendarCells = useMemo(() => {
    const firstDayOfMonth = new Date(selectedYear, selectedMonth, 1).getDay()
    const totalDays = new Date(selectedYear, selectedMonth + 1, 0).getDate()
    const cells = []

    // Empty cells at start of month
    for (let i = 0; i < firstDayOfMonth; i++) {
      cells.push({ id: `empty-${i}`, day: null, dateStr: '', netPnL: null, isTradeDay: false })
    }

    // Days of month
    for (let day = 1; day <= totalDays; day++) {
      const dateStr = `${selectedYear}-${String(selectedMonth + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
      const dayData = dailyDataMap[dateStr]
      cells.push({
        id: `day-${day}`,
        day,
        dateStr,
        netPnL: dayData ? dayData.net_pnl : null,
        isTradeDay: !!dayData,
        totalTrades: dayData ? dayData.total_trades : 0,
        winRate: dayData && dayData.total_trades > 0 
          ? (dayData.winning_trades / dayData.total_trades * 100).toFixed(0) + '%' 
          : 'N/A'
      })
    }

    return cells
  }, [selectedMonth, selectedYear, dailyDataMap])

  // Group cells into chunks of 7 (weekly rows)
  const calendarWeeks = useMemo(() => {
    const weeks: typeof calendarCells[] = []
    let currentWeek: typeof calendarCells = []
    
    calendarCells.forEach((cell, idx) => {
      currentWeek.push(cell)
      if (currentWeek.length === 7 || idx === calendarCells.length - 1) {
        // Pad the last week if it is incomplete
        while (currentWeek.length < 7) {
          currentWeek.push({ id: `pad-${currentWeek.length}`, day: null, dateStr: '', netPnL: null, isTradeDay: false })
        }
        weeks.push(currentWeek)
        currentWeek = []
      }
    })

    return weeks
  }, [calendarCells])

  const monthsList = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ]

  const changeMonth = (offset: number) => {
    let nextMonth = selectedMonth + offset
    let nextYear = selectedYear
    if (nextMonth < 0) {
      nextMonth = 11
      nextYear -= 1
    } else if (nextMonth > 11) {
      nextMonth = 0
      nextYear += 1
    }
    setSelectedMonth(nextMonth)
    setSelectedYear(nextYear)
  }

  const summary = data?.summary || {
    total_net_pnl: 0,
    total_gross_pnl: 0,
    total_brokerage: 0,
    win_rate: 0,
    max_drawdown: 0,
    total_days: 0
  }

  const equityCurve = data?.equity_curve || []

  return (
    <div className="fixed inset-0 bg-black/85 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-navy-950/95 border border-navy-700/80 rounded-2xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] backdrop-blur-xl">
        
        {/* Header */}
        <div className="flex justify-between items-center px-6 py-4 border-b border-navy-800 bg-navy-900/30">
          <div className="flex items-center gap-2">
            <span className="text-xl">📈</span>
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Performance Analytics</h2>
          </div>
          <button onClick={onClose} className="text-navy-400 hover:text-white transition text-xs font-mono">
            [ESC] CLOSE
          </button>
        </div>

        {/* Date Filter Bar */}
        <div className="px-6 py-3 border-b border-navy-800 bg-navy-950 flex flex-wrap gap-4 items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="text-[10px] text-navy-400 font-bold uppercase">Date Range:</span>
            <input 
              type="date" 
              className="bg-navy-900 border border-navy-800 text-white rounded px-2 py-1 text-xs focus:border-sky-500 focus:outline-none font-mono"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
            />
            <span className="text-navy-400 text-xs">to</span>
            <input 
              type="date" 
              className="bg-navy-900 border border-navy-800 text-white rounded px-2 py-1 text-xs focus:border-sky-500 focus:outline-none font-mono"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
            />
          </div>

          <div className="flex gap-2">
            <button 
              onClick={handleExportCSV} 
              disabled={exporting || isLoading}
              className="px-3.5 py-1.5 bg-navy-800 hover:bg-navy-700 disabled:opacity-40 text-xs font-semibold text-sky-400 border border-navy-700/80 rounded-lg flex items-center gap-1.5 transition"
            >
              📊 Export CSV
            </button>
          </div>
        </div>

        {/* Scrollable Content Container */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">

          {/* 1. Stat Summary Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-navy-900/20 border border-navy-800 rounded-xl p-3.5">
              <span className="text-[9px] text-navy-400 font-bold uppercase tracking-wider block">Net Profit / Loss</span>
              <span className={`text-lg font-bold font-mono block mt-1 ${summary.total_net_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {summary.total_net_pnl >= 0 ? '+' : ''}₹{summary.total_net_pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
              <span className="text-[9px] text-navy-500 block mt-0.5">Gross: ₹{summary.total_gross_pnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
            </div>

            <div className="bg-navy-900/20 border border-navy-800 rounded-xl p-3.5">
              <span className="text-[9px] text-navy-400 font-bold uppercase tracking-wider block">Win Rate</span>
              <span className="text-lg font-bold font-mono text-white block mt-1">{summary.win_rate}%</span>
              <span className="text-[9px] text-navy-500 block mt-0.5">{summary.winning_days} Green / {summary.total_days} Days</span>
            </div>

            <div className="bg-navy-900/20 border border-navy-800 rounded-xl p-3.5">
              <span className="text-[9px] text-navy-400 font-bold uppercase tracking-wider block">Max Drawdown</span>
              <span className="text-lg font-bold font-mono text-red-400 block mt-1">
                -₹{summary.max_drawdown.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
              <span className="text-[9px] text-navy-500 block mt-0.5">Deepest peak-to-trough dip</span>
            </div>

            <div className="bg-navy-900/20 border border-navy-800 rounded-xl p-3.5">
              <span className="text-[9px] text-navy-400 font-bold uppercase tracking-wider block">Brokerage & Taxes</span>
              <span className="text-lg font-bold font-mono text-amber-500 block mt-1">
                ₹{summary.total_brokerage.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
              <span className="text-[9px] text-navy-500 block mt-0.5">Exchange charges paid</span>
            </div>
          </div>

          {/* 2. Heatmap & Equity Charts Columns */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            
            {/* Calendar P&L Heatmap (Left - 7 Columns) */}
            <div className="lg:col-span-7 bg-navy-900/10 border border-navy-800 rounded-xl p-4 space-y-4">
              <div className="flex items-center justify-between pb-2 border-b border-navy-800">
                <span className="text-[10px] text-navy-300 font-bold uppercase tracking-wider">📅 Monthly P&L Calendar</span>
                
                {/* Month selectors */}
                <div className="flex items-center gap-3">
                  <button onClick={() => changeMonth(-1)} className="text-navy-400 hover:text-white text-xs px-1 font-bold font-mono">&lt;</button>
                  <span className="text-xs text-white font-bold min-w-[100px] text-center font-mono">
                    {monthsList[selectedMonth]} {selectedYear}
                  </span>
                  <button onClick={() => changeMonth(1)} className="text-navy-400 hover:text-white text-xs px-1 font-bold font-mono">&gt;</button>
                </div>
              </div>

              {/* Calendar Grid */}
              <div className="grid grid-cols-8 gap-1.5">
                {/* Day Labels */}
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                  <div key={d} className="text-[9px] text-navy-400 font-bold text-center uppercase py-0.5">
                    {d}
                  </div>
                ))}
                <div className="text-[9px] text-navy-400 font-bold text-center uppercase py-0.5 border-l border-navy-800/60">
                  Total
                </div>

                {/* Weeks Grid */}
                {calendarWeeks.map((week, wIdx) => {
                  const weekTotal = weeklyTotals[wIdx] || 0
                  
                  return (
                    <use key={wIdx} className="contents">
                      {week.map((cell, cIdx) => {
                        let colorClass = "bg-navy-950/20 text-navy-500 border-navy-900/10" // Default Empty
                        
                        if (cell.day) {
                          if (cell.netPnL !== null) {
                            if (cell.netPnL > 5000) {
                              colorClass = "bg-green-500/20 text-green-300 border-green-500/30 hover:bg-green-500/30"
                            } else if (cell.netPnL > 0) {
                              colorClass = "bg-green-800/15 text-green-400 border-green-800/20 hover:bg-green-800/25"
                            } else if (cell.netPnL < -3000) {
                              colorClass = "bg-red-500/15 text-red-300 border-red-500/20 hover:bg-red-500/25"
                            } else {
                              colorClass = "bg-red-900/10 text-red-400 border-red-900/15 hover:bg-red-900/20"
                            }
                          } else {
                            colorClass = "bg-navy-900/30 text-navy-400 border-navy-800/30"
                          }
                        }

                        return (
                          <div 
                            key={cell.id} 
                            title={cell.isTradeDay ? `Trades: ${cell.totalTrades} | Win Rate: ${cell.winRate}` : undefined}
                            className={`border rounded p-1 h-11 flex flex-col justify-between select-none transition ${colorClass}`}
                          >
                            <span className="text-[9px] font-bold text-left block">{cell.day || ''}</span>
                            {cell.netPnL !== null && (
                              <span className="text-[9px] font-mono font-bold block text-right">
                                {cell.netPnL > 0 ? '+' : ''}{cell.netPnL.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                              </span>
                            )}
                          </div>
                        )
                      })}

                      {/* Weekly summary cell */}
                      <div className={`border rounded p-1 h-11 flex flex-col justify-center text-center font-mono border-l border-navy-800/50 ${
                        weekTotal > 0 ? 'bg-green-950/20 text-green-400 border-green-950/20' : 
                        weekTotal < 0 ? 'bg-red-950/20 text-red-400 border-red-950/20' : 
                        'bg-navy-950/20 text-navy-500 border-navy-950/20'
                      }`}>
                        <span className="text-[9px] font-bold">
                          {weekTotal > 0 ? '+' : ''}{weekTotal.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                      </div>
                    </use>
                  )
                })}
              </div>

              {/* Legend Indicator */}
              <div className="flex items-center justify-end gap-3 text-[9px] text-navy-400 pt-2 border-t border-navy-800/40">
                <span>Loss</span>
                <span className="w-2.5 h-2.5 rounded bg-red-500/20" />
                <span className="w-2.5 h-2.5 rounded bg-red-900/10" />
                <span className="w-2.5 h-2.5 rounded bg-navy-900/30" />
                <span className="w-2.5 h-2.5 rounded bg-green-800/15" />
                <span className="w-2.5 h-2.5 rounded bg-green-500/20" />
                <span>Profit</span>
              </div>
            </div>

            {/* Equity Curve Charts (Right - 5 Columns) */}
            <div className="lg:col-span-5 bg-navy-900/10 border border-navy-800 rounded-xl p-4 space-y-4">
              <span className="text-[10px] text-navy-300 font-bold uppercase tracking-wider block pb-2 border-b border-navy-800">
                📈 Capital Growth & Equity Curve
              </span>

              {isLoading ? (
                <div className="h-56 flex items-center justify-center text-navy-500 text-xs">
                  Loading equity curve...
                </div>
              ) : equityCurve.length === 0 ? (
                <div className="h-56 flex items-center justify-center text-navy-500 text-xs">
                  No trade logs found in range
                </div>
              ) : (
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={equityCurve} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
                      <defs>
                        <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.25}/>
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorDrawdown" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.15}/>
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" opacity={0.2} />
                      <XAxis dataKey="date" tick={{ fill: '#475569', fontSize: 8 }} />
                      <YAxis tick={{ fill: '#475569', fontSize: 8 }} />
                      <Tooltip 
                        contentStyle={{ backgroundColor: '#0b1329', borderColor: '#1e293b', borderRadius: 8 }}
                        labelStyle={{ color: '#94a3b8', fontSize: 10, fontWeight: 'bold' }}
                        itemStyle={{ color: '#fff', fontSize: 10 }}
                      />
                      {/* Equity Curve (Green Area) */}
                      <Area 
                        type="monotone" 
                        dataKey="cumulative_pnl" 
                        stroke="#10b981" 
                        strokeWidth={1.5}
                        fillOpacity={1} 
                        fill="url(#colorEquity)" 
                        name="Net P&L" 
                      />
                      {/* Drawdown Curve (Red Area) */}
                      <Area 
                        type="monotone" 
                        dataKey="drawdown" 
                        stroke="#ef4444" 
                        strokeWidth={1.2}
                        fillOpacity={1} 
                        fill="url(#colorDrawdown)" 
                        name="Drawdown" 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

          </div>

        </div>

      </div>
    </div>
  )
}
