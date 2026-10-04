// Frontend mirror of backend/app/core/instruments.py (display metadata only).
// The backend stays the source of truth: lot sizes, expiry and the paper-only
// rule are enforced server-side regardless of what is shown here.

export type Underlying = 'NIFTY' | 'BANKNIFTY'

export interface InstrumentMeta {
  id: Underlying
  /** Name of the spot index as traders know it */
  label: string
  /** Short tag used in tabs and badges */
  short: string
  /** TradingView symbol for the embedded chart */
  tvSymbol: string
  /** Default lot size (matches backend registry) */
  lotSize: number
  /** BANKNIFTY can never trade live — paper only */
  paperOnly: boolean
}

export const INSTRUMENTS: Record<Underlying, InstrumentMeta> = {
  NIFTY: { id: 'NIFTY', label: 'NIFTY 50', short: 'NIFTY', tvSymbol: 'NSE:NIFTY', lotSize: 65, paperOnly: false },
  BANKNIFTY: { id: 'BANKNIFTY', label: 'BANK NIFTY', short: 'BANKNIFTY', tvSymbol: 'NSE:BANKNIFTY', lotSize: 30, paperOnly: true },
}

export const INSTRUMENT_LIST: InstrumentMeta[] = [INSTRUMENTS.NIFTY, INSTRUMENTS.BANKNIFTY]

export const DEFAULT_UNDERLYING: Underlying = 'NIFTY'

const STORAGE_KEY = 'pyramid_underlying'

export function isUnderlying(v: unknown): v is Underlying {
  return v === 'NIFTY' || v === 'BANKNIFTY'
}

export function loadStoredUnderlying(): Underlying {
  try {
    const v = localStorage.getItem(STORAGE_KEY)
    return isUnderlying(v) ? v : DEFAULT_UNDERLYING
  } catch {
    return DEFAULT_UNDERLYING
  }
}

export function storeUnderlying(u: Underlying) {
  try {
    localStorage.setItem(STORAGE_KEY, u)
  } catch {
    /* storage unavailable (private mode) — selection just won't persist */
  }
}
