import type { StrategyStatus, StrategyConfig } from '../../types'
import clsx from 'clsx'

interface Props {
  status: StrategyStatus | null
  config: StrategyConfig | null
}

const STATE_COLORS: Record<string, string> = {
  IDLE: 'text-navy-300',
  L1_ENTERED: 'text-yellow-400',
  L2_ENTERED: 'text-orange-400',
  L3_ENTERED: 'text-red-400',
  BLOCKED: 'text-navy-400',
}

function formatState(state: string | undefined, side: 'CE' | 'PE'): string {
  if (!state) return 'IDLE'
  if (state.startsWith('L')) {
    const prefix = side === 'CE' ? 'S' : 'R'
    return state.replace('L', prefix)
  }
  return state
}

export function LevelPanel({ status, config }: Props) {
  if (!config) return <div className="text-navy-300 text-sm">No config — set levels in Settings</div>

  const pe = status?.pe
  const ce = status?.ce

  const levels = [
    { label: 'R3', value: config.r3, side: 'PE', lvl: 'L3', color: 'border-red-800 bg-red-950/30' },
    { label: 'R2', value: config.r2, side: 'PE', lvl: 'L2', color: 'border-red-900 bg-red-950/20' },
    { label: 'R1', value: config.r1, side: 'PE', lvl: 'L1', color: 'border-red-950 bg-red-950/10' },
    { label: '─── NIFTY ───', value: status?.nifty_ltp ?? '─', side: null, lvl: null, color: 'border-blue-700 bg-blue-950/30' },
    { label: 'S1', value: config.s1, side: 'CE', lvl: 'L1', color: 'border-green-950 bg-green-950/10' },
    { label: 'S2', value: config.s2, side: 'CE', lvl: 'L2', color: 'border-green-900 bg-green-950/20' },
    { label: 'S3', value: config.s3, side: 'CE', lvl: 'L3', color: 'border-green-800 bg-green-950/30' },
  ]

  const isActive = (side: string | null, lvl: string | null) => {
    if (!side || !lvl || !status) return false
    const sm = side === 'PE' ? pe : ce
    return sm?.state === `${lvl}_ENTERED`
  }

  const isBlocked = (side: string | null, lvl: string | null) => {
    if (!side || !lvl || !status) return false
    const sm = side === 'PE' ? pe : ce
    return sm?.blocked_levels.includes(lvl) ?? false
  }

  return (
    <div className="space-y-1">
      {levels.map((l, i) => (
        <div
          key={i}
          className={clsx(
            'flex items-center justify-between px-3 py-1.5 rounded border text-sm',
            l.color,
            isActive(l.side, l.lvl) && 'ring-1 ring-yellow-400',
            isBlocked(l.side, l.lvl) && 'opacity-40'
          )}
        >
          <span className="font-bold w-16">{l.label}</span>
          <span className="text-white font-mono">
            {typeof l.value === 'number' ? l.value.toLocaleString('en-IN') : l.value}
          </span>
          <span className="w-6 text-right">
            {isActive(l.side, l.lvl) && <span className="text-yellow-400 animate-pulse">●</span>}
            {isBlocked(l.side, l.lvl) && <span className="text-gray-500">✗</span>}
          </span>
        </div>
      ))}

      {/* CE / PE status badges */}
      <div className="flex gap-2 mt-3">
        <div className={clsx('flex-1 text-center py-1 rounded text-xs font-bold border',
          'border-green-800 bg-green-950/30', STATE_COLORS[ce?.state ?? 'IDLE'])}>
          ▲ CE: {formatState(ce?.state, 'CE')}
          {(ce?.lots ?? 0) > 0 && <span className="ml-1 text-white">{ce!.lots}L</span>}
        </div>
        <div className={clsx('flex-1 text-center py-1 rounded text-xs font-bold border',
          'border-red-800 bg-red-950/30', STATE_COLORS[pe?.state ?? 'IDLE'])}>
          ▼ PE: {formatState(pe?.state, 'PE')}
          {(pe?.lots ?? 0) > 0 && <span className="ml-1 text-white">{pe!.lots}L</span>}
        </div>
      </div>
    </div>
  )
}
