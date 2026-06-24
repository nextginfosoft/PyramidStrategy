import { useMemo } from 'react'
import { useStrategyStore } from '../../store/strategyStore'
import clsx from 'clsx'

export function StatusBar() {
  const { status, wsConnected } = useStrategyStore()

  // 1. Determine states and health details
  const health = status?.health
  const paperTrade = status?.paper_trade ?? true
  const isRunning = status?.is_running ?? false

  const authenticated = health?.authenticated ?? false
  const tickerConnected = health?.ticker_connected ?? false
  const apiError = health?.last_api_error ?? null
  const tickerError = health?.last_ticker_error ?? null
  const lastNiftyTickSec = health?.last_nifty_tick_seconds_ago ?? null

  // 2. Identify if there's a critical live error that should stop the scrolling marquee
  const isCriticalError = useMemo(() => {
    if (paperTrade) return false // Paper trade runs in local simulation mode
    
    // Live mode connection failures:
    return (
      !authenticated ||
      !tickerConnected ||
      !!apiError ||
      !!tickerError ||
      (lastNiftyTickSec !== null && lastNiftyTickSec > 15)
    );
  }, [paperTrade, authenticated, tickerConnected, apiError, tickerError, lastNiftyTickSec])

  // 3. Construct the static badge and message contents
  const badgeInfo = useMemo(() => {
    if (!status) {
      return {
        text: 'CONNECTING',
        bgClass: 'bg-navy-800 text-navy-400 border-navy-700/60',
        dotClass: 'bg-navy-500 animate-pulse'
      }
    }
    if (isCriticalError) {
      return {
        text: 'KITE ERROR',
        bgClass: 'bg-red-950/60 text-red-400 border-red-800/40 animate-pulse',
        dotClass: 'bg-red-400'
      }
    }
    if (paperTrade) {
      return {
        text: 'PAPER TRADE',
        bgClass: 'bg-yellow-950/50 text-yellow-400 border-yellow-700/40',
        dotClass: 'bg-yellow-400 animate-pulse'
      }
    }
    if (lastNiftyTickSec !== null && lastNiftyTickSec > 5) {
      return {
        text: 'FEED STALE',
        bgClass: 'bg-amber-950/60 text-amber-400 border-amber-800/40',
        dotClass: 'bg-amber-400 animate-bounce'
      }
    }
    return {
      text: isRunning ? 'LIVE MONITOR' : 'KITE READY',
      bgClass: 'bg-green-950/50 text-green-400 border-green-700/40',
      dotClass: 'bg-green-400 animate-pulse'
    }
  }, [status, isCriticalError, paperTrade, lastNiftyTickSec, isRunning])

  const tickerMessage = useMemo(() => {
    if (!status) {
      return 'Connecting to backend services...';
    }

    if (isCriticalError) {
      // Return static error banner details
      if (!authenticated) {
        return '❌ CRITICAL: Zerodha Kite credentials not authenticated. Save API key/secret in settings and complete login.';
      }
      if (apiError) {
        return `❌ KITE REST API ERROR: ${apiError}. Check network or rate-limits.`;
      }
      if (tickerError) {
        return `❌ KITE TICKER WEBSOCKET ERROR: ${tickerError}. Reconnecting...`;
      }
      if (!tickerConnected) {
        return '❌ DISCONNECTED: Live Zerodha market feed WebSocket down. Attempting auto-recovery...';
      }
      if (lastNiftyTickSec !== null && lastNiftyTickSec > 15) {
        return `❌ DATA HEARTBEAT FAILURE: Live Nifty feed hasn't pushed ticks in ${lastNiftyTickSec} seconds. Connection check recommended.`;
      }
      return '❌ KITE SYSTEM CONGESTION: Connection error detected.';
    }

    // Healthy running state message compilation
    const parts: string[] = []

    // Connection mode
    if (paperTrade) {
      parts.push(`🎮 SIMULATION ACTIVE: Real-time price tracker running in Paper Trading mode.`)
    } else {
      parts.push(`🟢 KITE LIVE FEED: Authenticated & Connected to Zerodha Ticker.`)
    }

    // Nifty Spot price
    if (status.nifty_ltp != null) {
      parts.push(`NIFTY 50: ₹${status.nifty_ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`)
      if (lastNiftyTickSec !== null) {
        parts.push(`Last update: ${lastNiftyTickSec}s ago`)
      }
    } else {
      parts.push(`NIFTY 50: Awaiting tick...`)
    }

    // CE details
    if (status.ce) {
      const ce = status.ce
      if (ce.state !== 'IDLE') {
        const pnlStr = ce.unrealized_pnl != null
          ? `${ce.unrealized_pnl >= 0 ? '+' : ''}₹${ce.unrealized_pnl.toFixed(0)}`
          : '—'
        parts.push(`CE Position: ${ce.state} | Strike: ${ce.locked_strike || '—'} | ${ce.lots} Lots | Unrealized P&L: ${pnlStr}`)
      } else {
        parts.push(`CE Leg: IDLE (Monitoring Support S1/S2/S3)`)
      }
    }

    // PE details
    if (status.pe) {
      const pe = status.pe
      if (pe.state !== 'IDLE') {
        const pnlStr = pe.unrealized_pnl != null
          ? `${pe.unrealized_pnl >= 0 ? '+' : ''}₹${pe.unrealized_pnl.toFixed(0)}`
          : '—'
        parts.push(`PE Position: ${pe.state} | Strike: ${pe.locked_strike || '—'} | ${pe.lots} Lots | Unrealized P&L: ${pnlStr}`)
      } else {
        parts.push(`PE Leg: IDLE (Monitoring Resistance R1/R2/R3)`)
      }
    }

    // System details
    parts.push(`Websocket Link: ${wsConnected ? 'Connected' : 'Disconnected'}`)
    if (health?.instruments_loaded) {
      parts.push(`NFO Instruments: Cached & Loaded`)
    }
    if (health?.subscribed_options != null && health.subscribed_options > 0) {
      parts.push(`Streaming options: ${health.subscribed_options}`)
    }

    return parts.join('  •  ')
  }, [status, isCriticalError, paperTrade, lastNiftyTickSec, apiError, tickerError, wsConnected, health])

  return (
    <div className="w-full h-9 bg-navy-900/40 border-b border-navy-800/50 backdrop-blur-sm flex items-center px-4 select-none font-mono text-[11px] overflow-hidden">
      
      {/* 1. Static status badge (Left side) */}
      <div className="flex-shrink-0 flex items-center gap-1.5 mr-4 py-0.5 px-2 border rounded-full font-bold uppercase tracking-wider text-[9px] shadow-sm select-none z-10 bg-navy-950">
        <span className={clsx('w-1.5 h-1.5 rounded-full inline-block', badgeInfo.dotClass)} />
        <span className={badgeInfo.bgClass.split(' ')[1]}>{badgeInfo.text}</span>
      </div>

      {/* 2. Message Area (Static or Scrolling) */}
      <div className="flex-1 overflow-hidden relative flex items-center h-full">
        {isCriticalError ? (
          // Critical Alert State: Static flashing red banner
          <div className="w-full text-left font-bold text-red-400 animate-pulse select-text">
            {tickerMessage}
          </div>
        ) : (
          // Healthy State: Smooth horizontally scrolling marquee
          <div className="w-full whitespace-nowrap overflow-hidden">
            <div 
              className="animate-marquee hover:pause cursor-help text-navy-200 select-text inline-block animate-marquee-hover"
              style={{ animationDuration: '30s' }}
            >
              {tickerMessage}
            </div>
          </div>
        )}
      </div>

      {/* 3. Small websocket indicator dot (Right side) */}
      <div 
        title={wsConnected ? 'WebSocket Client Link OK' : 'WebSocket Client Link Offline'} 
        className="flex-shrink-0 ml-4 flex items-center gap-1 text-[10px] text-navy-400 select-none hidden md:flex"
      >
        <span>WS</span>
        <span className={clsx('w-1.5 h-1.5 rounded-full inline-block', wsConnected ? 'bg-green-400' : 'bg-red-400 animate-pulse')} />
      </div>
    </div>
  )
}
