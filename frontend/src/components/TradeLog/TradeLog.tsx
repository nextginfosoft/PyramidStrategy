import type { Trade } from '../../types'
import clsx from 'clsx'
import { format } from 'date-fns'

interface Props { trades: Trade[] }

export function TradeLog({ trades }: Props) {
  if (!trades.length) {
    return <div className="text-navy-300 text-sm text-center py-8">No trades today</div>
  }

  return (
    <div className="overflow-auto max-h-64">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-navy-300 border-b border-navy-700">
            <th className="text-left py-1 pr-2">Time</th>
            <th className="text-left pr-2">Side</th>
            <th className="text-left pr-2">Lvl</th>
            <th className="text-left pr-2">Action</th>
            <th className="text-right pr-2">Price</th>
            <th className="text-right pr-2">Lots</th>
            <th className="text-right">P&L</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} className="border-b border-navy-800 hover:bg-navy-900/50">
              <td className="py-1 pr-2 text-navy-300">
                {format(new Date(t.created_at), 'HH:mm:ss')}
              </td>
              <td className={clsx('pr-2 font-bold', t.side === 'CE' ? 'text-green-400' : 'text-red-400')}>
                {t.side}
              </td>
              <td className="pr-2 text-navy-200">{t.level}</td>
              <td className={clsx('pr-2', t.action === 'BUY' ? 'text-blue-400' : 'text-orange-400')}>
                {t.action}
              </td>
              <td className="text-right pr-2 text-navy-100">
                {t.avg_price?.toFixed(2) ?? '—'}
              </td>
              <td className="text-right pr-2 text-navy-200">{t.lots}</td>
              <td className={clsx('text-right font-mono',
                t.pnl == null ? 'text-navy-300'
                : t.pnl >= 0 ? 'text-green-400' : 'text-red-400')}>
                {t.pnl != null
                  ? `${t.pnl >= 0 ? '+' : ''}₹${t.pnl.toFixed(0)}`
                  : (t.status === 'OPEN' ? <span className="text-yellow-400">OPEN</span> : '—')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
