import type { Trade } from '../../types'
import clsx from 'clsx'
import { format } from 'date-fns'

interface Props { trades: Trade[] }

export function TradeLog({ trades }: Props) {
  if (!trades.length) {
    return <div className="text-gray-500 text-sm text-center py-8">No trades today</div>
  }

  return (
    <div className="overflow-auto max-h-64">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-gray-500 border-b border-gray-800">
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
            <tr key={t.id} className="border-b border-gray-900 hover:bg-gray-900/50">
              <td className="py-1 pr-2 text-gray-400">
                {format(new Date(t.created_at), 'HH:mm:ss')}
              </td>
              <td className={clsx('pr-2 font-bold', t.side === 'CE' ? 'text-green-400' : 'text-red-400')}>
                {t.side}
              </td>
              <td className="pr-2 text-gray-300">{t.level}</td>
              <td className={clsx('pr-2', t.action === 'BUY' ? 'text-blue-400' : 'text-orange-400')}>
                {t.action}
              </td>
              <td className="text-right pr-2 text-gray-200">
                {t.avg_price?.toFixed(2) ?? '—'}
              </td>
              <td className="text-right pr-2 text-gray-300">{t.lots}</td>
              <td className={clsx('text-right font-mono',
                t.pnl == null ? 'text-gray-500'
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
