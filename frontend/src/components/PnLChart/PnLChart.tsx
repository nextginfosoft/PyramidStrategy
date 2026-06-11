import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface Props {
  data: Array<{ time: string; pnl: number }>
}

export function PnLChart({ data }: Props) {
  if (!data.length) {
    return (
      <div className="flex items-center justify-center h-32 text-gray-600 text-sm">
        P&L chart — starts when first trade exits
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={120}>
      <LineChart data={data} margin={{ top: 5, right: 10, bottom: 0, left: 10 }}>
        <XAxis dataKey="time" tick={{ fontSize: 10, fill: '#6b7280' }} />
        <YAxis tick={{ fontSize: 10, fill: '#6b7280' }} tickFormatter={(v) => `₹${v}`} />
        <Tooltip
          contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 11 }}
          formatter={(v: number) => [`₹${v.toFixed(0)}`, 'P&L']}
        />
        <ReferenceLine y={0} stroke="#374151" strokeDasharray="3 3" />
        <Line
          type="monotone"
          dataKey="pnl"
          stroke="#f97316"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
