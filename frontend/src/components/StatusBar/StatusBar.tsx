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

  interface TickerPart {
    text: string;
    colorClass: string;
  }

  const tickerMessageParts = useMemo<TickerPart[]>(() => {
    if (!status) {
      return [{ text: 'Connecting to backend services...', colorClass: 'text-navy-300' }];
    }

    if (isCriticalError) {
      let errStr = '❌ KITE SYSTEM CONGESTION: Connection error detected.';
      if (!authenticated) {
        errStr = '❌ CRITICAL: Zerodha Kite credentials not authenticated. Save API key/secret in settings and complete login.';
      } else if (apiError) {
        errStr = `❌ KITE REST API ERROR: ${apiError}. Check network or rate-limits.`;
      } else if (tickerError) {
        errStr = `❌ KITE TICKER WEBSOCKET ERROR: ${tickerError}. Reconnecting...`;
      } else if (!tickerConnected) {
        errStr = '❌ DISCONNECTED: Live Zerodha market feed WebSocket down. Attempting auto-recovery...';
      } else if (lastNiftyTickSec !== null && lastNiftyTickSec > 15) {
        errStr = `❌ DATA HEARTBEAT FAILURE: Live Nifty feed hasn't pushed ticks in ${lastNiftyTickSec} seconds. Connection check recommended.`;
      }
      return [{ text: errStr, colorClass: 'text-red-400 font-bold' }];
    }

    const parts: TickerPart[] = [];

    // 0. Engine Start/Stop Time Status
    if (isRunning) {
      parts.push({
        text: `🚀 ENGINE ACTIVE (Started at: ${status.started_at || '—'})`,
        colorClass: 'text-cyan-400 font-bold'
      });
    } else {
      parts.push({
        text: `⏹️ ENGINE INACTIVE${status.stopped_at ? ` (Stopped at: ${status.stopped_at})` : ' (Ready to start)'}`,
        colorClass: 'text-orange-400 font-bold'
      });
    }

    // 1. Connection mode
    if (paperTrade) {
      parts.push({
        text: `🎮 SIMULATION ACTIVE: Real-time price tracker running in Paper Trading mode.`,
        colorClass: 'text-yellow-400'
      });
    } else {
      parts.push({
        text: `🟢 KITE LIVE FEED: Authenticated & Connected to Zerodha Ticker.`,
        colorClass: 'text-emerald-400'
      });
    }

    // 2. Nifty Spot price
    if (status.nifty_ltp != null) {
      const ltpStr = status.nifty_ltp.toLocaleString('en-IN', { minimumFractionDigits: 2 });
      const isUp = (status.nifty_ltp >= (status.nifty_prev_close ?? 0));
      parts.push({
        text: `NIFTY 50: ₹${ltpStr}${lastNiftyTickSec !== null ? ` (${lastNiftyTickSec}s ago)` : ''}`,
        colorClass: isUp ? 'text-green-400' : 'text-red-400'
      });
    } else {
      parts.push({
        text: `NIFTY 50: Awaiting tick...`,
        colorClass: 'text-navy-300'
      });
    }

    // 3. CE details
    if (status.ce) {
      const ce = status.ce;
      if (ce.state !== 'IDLE') {
        const pnl = ce.unrealized_pnl ?? 0;
        const pnlStr = `${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(0)}`;
        parts.push({
          text: `CE Position: ${ce.state} | Strike: ${ce.locked_strike || '—'} | ${ce.lots} Lots | Unrealized P&L: ${pnlStr}`,
          colorClass: pnl >= 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'
        });
      } else {
        parts.push({
          text: `CE Leg: IDLE (Monitoring Support S1/S2/S3)`,
          colorClass: 'text-navy-300 opacity-90'
        });
      }
    }

    // 4. PE details
    if (status.pe) {
      const pe = status.pe;
      if (pe.state !== 'IDLE') {
        const pnl = pe.unrealized_pnl ?? 0;
        const pnlStr = `${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(0)}`;
        parts.push({
          text: `PE Position: ${pe.state} | Strike: ${pe.locked_strike || '—'} | ${pe.lots} Lots | Unrealized P&L: ${pnlStr}`,
          colorClass: pnl >= 0 ? 'text-green-400 font-bold' : 'text-red-400 font-bold'
        });
      } else {
        parts.push({
          text: `PE Leg: IDLE (Monitoring Resistance R1/R2/R3)`,
          colorClass: 'text-navy-300 opacity-90'
        });
      }
    }

    // 5. System details
    parts.push({
      text: `Websocket Link: ${wsConnected ? 'Connected' : 'Disconnected'}`,
      colorClass: wsConnected ? 'text-emerald-400' : 'text-red-400'
    });
    if (health?.instruments_loaded) {
      parts.push({
        text: `NFO Instruments: Cached & Loaded`,
        colorClass: 'text-sky-400'
      });
    }
    if (health?.subscribed_options != null && health.subscribed_options > 0) {
      parts.push({
        text: `Streaming options: ${health.subscribed_options}`,
        colorClass: 'text-purple-400'
      });
    }

    // 6. Wealth Ladder & Life Goals Ticker Items
    parts.push({
      text: `👑 WEALTH TARGET: Level 1 (₹25 Lakh Focus)`,
      colorClass: 'text-amber-400 font-extrabold'
    });
    parts.push({
      text: `🏢 GOAL #1: Own a penthouse`,
      colorClass: 'text-rose-400 font-bold'
    });
    parts.push({
      text: `💸 GOAL #1: Pay ₹1 Crore in income tax within a year`,
      colorClass: 'text-rose-400 font-bold'
    });
    parts.push({
      text: `🏎️ GOAL #2: Own a BMW`,
      colorClass: 'text-amber-300 font-bold'
    });
    parts.push({
      text: `✈️ GOAL #3: Visit Dubai`,
      colorClass: 'text-amber-300 font-bold'
    });
    parts.push({
      text: `🗺️ GOAL #3: Travel across India`,
      colorClass: 'text-amber-300 font-bold'
    });
    parts.push({
      text: `🏖️ GOAL #5: Visit Goa once every year`,
      colorClass: 'text-cyan-300 font-bold'
    });
    parts.push({
      text: `🌍 GOAL #6: Take at least one international trip every year`,
      colorClass: 'text-cyan-300 font-bold'
    });
    parts.push({
      text: `🗽 GOAL #7: Visit the Statue of Liberty`,
      colorClass: 'text-cyan-300 font-bold'
    });
    parts.push({
      text: `🏡 GOAL #8: Own a farmhouse`,
      colorClass: 'text-emerald-400 font-bold'
    });
    parts.push({
      text: `❤️ GOAL #9: Start an NGO`,
      colorClass: 'text-emerald-400 font-bold'
    });

    return parts;
  }, [status, isCriticalError, paperTrade, lastNiftyTickSec, apiError, tickerError, wsConnected, health]);

  return (
    <div className="w-full h-11 bg-transparent flex items-center px-4 select-none font-mono text-[13px] overflow-hidden">
      
      {/* 1. Static status badge (Left side) */}
      <div className="flex-shrink-0 flex items-center gap-2 mr-4 py-1 px-3 border border-navy-800 rounded-full font-bold uppercase tracking-wider text-[10px] shadow-sm select-none z-10 bg-navy-950">
        <span className={clsx('w-2 h-2 rounded-full inline-block', badgeInfo.dotClass)} />
        <span className={badgeInfo.bgClass.split(' ')[1]}>{badgeInfo.text}</span>
      </div>

      {/* 2. Message Area (Scrolling) */}
      <div className="flex-1 overflow-hidden relative flex items-center h-full">
        {isCriticalError ? (
          // Critical Alert State: Static flashing red banner
          <div className="w-full text-left font-bold text-red-400 animate-pulse select-text">
            {tickerMessageParts[0]?.text}
          </div>
        ) : (
          // Healthy State: Smooth horizontally scrolling marquee with color coded items
          <div className="w-full whitespace-nowrap overflow-hidden">
            <div 
              className="animate-marquee hover:pause cursor-help select-text inline-block animate-marquee-hover font-semibold"
              style={{ animationDuration: '85s' }}
            >
              {tickerMessageParts.map((part, idx) => (
                <span key={idx} className={clsx("inline-block", part.colorClass)}>
                  {idx > 0 && <span className="mx-4 text-navy-700 font-bold select-none">•</span>}
                  {part.text}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3. Small websocket indicator dot (Right side) */}
      <div 
        title={wsConnected ? 'WebSocket Client Link OK' : 'WebSocket Client Link Offline'} 
        className="flex-shrink-0 ml-4 flex items-center gap-2 text-xs text-navy-400 select-none hidden md:flex"
      >
        <span>WS</span>
        <span className="inline-flex relative items-center justify-center h-2.5 w-2.5">
          {wsConnected ? (
            <>
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500"></span>
            </>
          ) : (
            <>
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
            </>
          )}
        </span>
      </div>
    </div>
  )
}
