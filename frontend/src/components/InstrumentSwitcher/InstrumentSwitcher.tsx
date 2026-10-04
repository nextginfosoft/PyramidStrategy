import { useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { useStrategyStore } from '../../store/strategyStore'
import { INSTRUMENT_LIST, type Underlying } from '../../utils/instruments'

/**
 * Switches the whole dashboard between instruments. Every instrument keeps its
 * own engine, levels, trades and P&L on the backend; this only changes which one
 * the UI is showing (and which one API calls are scoped to).
 */
export function InstrumentSwitcher() {
  const qc = useQueryClient()
  const underlying = useStrategyStore(s => s.underlying)
  const statuses = useStrategyStore(s => s.statuses)
  const selectUnderlying = useStrategyStore(s => s.selectUnderlying)

  const handleSelect = (u: Underlying) => {
    if (u === underlying) return
    selectUnderlying(u)
    // Drop instrument-scoped data so nothing from the previous instrument flashes
    // on screen; account-wide data (API keys) is left alone.
    qc.resetQueries({ predicate: q => q.queryKey[0] !== 'api-keys' })
  }

  return (
    <div role="tablist" aria-label="Instrument" className="flex gap-1 p-0.5 bg-navy-950/60 border border-navy-800 rounded-lg">
      {INSTRUMENT_LIST.map(inst => {
        const selected = inst.id === underlying
        const running = statuses[inst.id]?.is_running
        return (
          <button
            key={inst.id}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => handleSelect(inst.id)}
            className={clsx(
              'flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-md text-[10px] font-bold uppercase tracking-wider transition-colors focus:outline-none focus:ring-1 focus:ring-amber-500/50',
              selected ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30' : 'text-navy-300 hover:text-navy-100 border border-transparent',
            )}
          >
            {running && <span aria-label="running" className="h-1.5 w-1.5 rounded-full bg-green-400" />}
            {inst.short}
            {inst.paperOnly && <span className="text-[7px] text-yellow-500/80">PAPER</span>}
          </button>
        )
      })}
    </div>
  )
}
