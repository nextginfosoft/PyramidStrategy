import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, CartesianGrid } from 'recharts'

interface Props {
  data: Array<{ time: string; pnl: number }>
}

export function PnLChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-36 text-navy-400 text-xs select-none">
        P&L chart — starts when first trade exits
      </div>
    )
  }

  // Determine if overall net P&L is currently positive
  const lastVal = data[data.length - 1]?.pnl ?? 0
  const isPositive = lastVal >= 0
  const strokeColor = isPositive ? '#10b981' : '#f87171'
  const fillColor = isPositive ? 'url(#colorPnlGreen)' : 'url(#colorPnlRed)'

  return (
    <div className="w-full select-none">
      <ResponsiveContainer width="100%" height={180}>
        <AreaChart data={data} margin={{ top: 10, right: 10, bottom: 5, left: 5 }}>
          <defs>
            {/* Emerald green gradient */}
            <linearGradient id="colorPnlGreen" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10b981" stopOpacity={0.35}/>
              <stop offset="95%" stopColor="#10b981" stopOpacity={0.0}/>
            </linearGradient>
            {/* Red gradient */}
            <linearGradient id="colorPnlRed" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#f87171" stopOpacity={0.35}/>
              <stop offset="95%" stopColor="#f87171" stopOpacity={0.0}/>
            </linearGradient>
          </defs>
          
          <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
          
          <XAxis 
            dataKey="time" 
            tick={{ fontSize: 9, fill: '#64748b' }} 
            axisLine={{ stroke: '#334155' }}
            tickLine={{ stroke: '#334155' }}
          />
          
          <YAxis 
            tick={{ fontSize: 9, fill: '#64748b' }} 
            tickFormatter={(v) => `₹${v}`} 
            axisLine={{ stroke: '#334155' }}
            tickLine={{ stroke: '#334155' }}
            width={40}
          />
          
          <Tooltip
            contentStyle={{ 
              background: '#0f172a', 
              border: '1px solid #334155', 
              borderRadius: '8px',
              fontSize: '11px',
              boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)'
            }}
            itemStyle={{ color: strokeColor }}
            formatter={(v: number) => [`₹${v.toLocaleString('en-IN')}`, 'Net P&L']}
            labelFormatter={(label) => `Time: ${label}`}
          />
          
          <ReferenceLine y={0} stroke="#475569" strokeWidth={1} strokeDasharray="3 3" />
          
          <Area
            type="monotone"
            dataKey="pnl"
            stroke={strokeColor}
            strokeWidth={2}
            fill={fillColor}
            dot={{ r: 2, fill: strokeColor, strokeWidth: 1 }}
            activeDot={{ r: 4, fill: strokeColor, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
