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

export interface HealthStatus {
  authenticated: boolean
  ticker_connected: boolean
  ticker_running: boolean
  last_nifty_tick_seconds_ago: number | null
  last_api_error: string | null
  last_ticker_error: string | null
  instruments_loaded: boolean
  subscribed_options: number
}

export interface StrategyStatus {
  is_running: boolean
  paper_trade: boolean
  started_at?: string | null
  stopped_at?: string | null
  nifty_ltp: number | null
  nifty_prev_close: number | null
  ce: SideStatus
  pe: SideStatus
  entries_allowed: boolean
  squareoff_triggered: boolean
  health?: HealthStatus
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
  post_exit_high?: number | null
  post_exit_high_time?: string | null
  post_exit_low?: number | null
  post_exit_low_time?: string | null
  created_at: string
}

export interface StrategyConfig {
  id: number
  r1: number; r2: number; r3: number
  s1: number; s2: number; s3: number
  lot_size: number
  target_points: number
  sl_points: number
  paper_trade: boolean
  squareoff_time?: string
  is_active: boolean
}

export type WSMessage =
  | { type: 'strategy_status'; data: StrategyStatus }
  | { type: 'trade_event'; data: Record<string, unknown> }
  | { type: 'ai_suggestion'; data: { suggestion: string; event: string; side: string } }
  | { type: 'error'; data: { message: string } }
  | { type: 'pong' }

export interface DailyPnL {
  id: number
  user_id: number
  trade_date: string
  gross_pnl: number
  brokerage: number
  net_pnl: number
  total_trades: number
  winning_trades: number
  ce_pnl: number
  pe_pnl: number
  created_at: string
}
