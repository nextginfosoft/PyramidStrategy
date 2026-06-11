export interface SideStatus {
  state: 'IDLE' | 'L1_ENTERED' | 'L2_ENTERED' | 'L3_ENTERED' | 'BLOCKED'
  lots: number
  locked_strike: number | null
  locked_instrument: string | null
  entry_avg_price: number | null
  current_ltp: number | null
  unrealized_pnl: number | null
  realized_pnl: number
  blocked_levels: string[]
}

export interface StrategyStatus {
  is_running: boolean
  paper_trade: boolean
  nifty_ltp: number | null
  ce: SideStatus
  pe: SideStatus
  entries_allowed: boolean
  squareoff_triggered: boolean
}

export interface Trade {
  id: number
  trade_date: string
  side: 'CE' | 'PE'
  level: string
  instrument: string
  strike: number
  expiry: string
  action: 'BUY' | 'EXIT'
  lots: number
  qty: number
  avg_price: number | null
  status: string
  pnl: number | null
  is_paper_trade: boolean
  created_at: string
}

export interface StrategyConfig {
  id: number
  r1: number; r2: number; r3: number
  s1: number; s2: number; s3: number
  lot_size: number
  target_points: number
  sl_points: number
  is_active: boolean
}

export type WSMessage =
  | { type: 'strategy_status'; data: StrategyStatus }
  | { type: 'trade_event'; data: Record<string, unknown> }
  | { type: 'ai_suggestion'; data: { suggestion: string; event: string; side: string } }
  | { type: 'error'; data: { message: string } }
  | { type: 'pong' }
