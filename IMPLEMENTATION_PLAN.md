# PyramidStrategy — Phase-wise Implementation Plan

> **Rule:** Every phase must pass all tests before Phase N+1 begins.  
> **Paper Trade Mode** must be ON for all phases until Phase 4 live validation.

---

## PHASE 1 — Foundation & Paper Trade Engine
**Duration:** 2–3 weeks  
**Goal:** Working strategy engine in paper trade mode. No real money.

### 1.1 Project Setup
- [ ] Initialize monorepo: `pyramid-strategy/frontend` + `pyramid-strategy/backend`
- [ ] Setup Docker Compose: PostgreSQL 15 + Redis 7
- [ ] FastAPI project skeleton with folder structure per CLAUDE.md
- [ ] React + Vite + TypeScript + Tailwind + shadcn/ui setup
- [ ] Configure `alembic` for DB migrations
- [ ] Create all DB tables (strategy_config, trades, daily_pnl, api_config)
- [ ] `.env.example` with all required variables documented

### 1.2 Strategy Configuration API
- [ ] `POST /config/strategy` — save R1/R2/R3/S1/S2/S3
- [ ] `GET /config/strategy` — fetch current config
- [ ] `PUT /config/strategy` — update levels
- [ ] Validate: R3 > R2 > R1, S1 > S2 > S3
- [ ] Settings UI page — input fields for all 6 levels + lot size

### 1.3 Strategy Engine Core (Paper Trade Mode)
- [ ] `CEStateMachine` class with states: IDLE, L1, L2, L3, BLOCKED
- [ ] `PEStateMachine` class (identical structure, separate instance)
- [ ] Level detector: compare NIFTY price against R/S levels
- [ ] Entry logic per CLAUDE.md rules (Cases 1–5 for both CE/PE)
- [ ] Strike locking mechanism (locked after Level 1 entry)
- [ ] Target calculation: `(current_ltp - avg_entry) × lots × lot_size`
- [ ] SL check: only at Level 3, 10 pts below avg_entry
- [ ] Exit logic: full position exit on target/SL

### 1.4 Time Rules
- [ ] `TimeRulesEngine` class
- [ ] `is_entry_allowed()` → False after 11:15 AM IST
- [ ] `should_squareoff()` → True at/after 11:30 AM IST
- [ ] `get_expiry_for_today()` → same-day OR next weekly (Tuesday rule)
- [ ] APScheduler job: force squareoff at 11:30 AM
- [ ] APScheduler job: log "no fresh entries" warning at 11:15 AM
- [ ] Unit tests: test all time-based rules with mocked datetime

### 1.5 Option Selector (Paper Trade — Mock Kite)
- [ ] `OptionSelector.get_option_symbol(side, current_nifty, expiry)`
- [ ] ATM calculation: `round(nifty / 50) * 50`
- [ ] PE strike: ATM + 50; CE strike: ATM - 50
- [ ] Mock Kite instruments list for testing
- [ ] Symbol format: `NIFTYDDMMMYYSTRIKEPE/CE`
- [ ] Unit tests for ATM calculation and symbol generation

### 1.6 Paper Trade Order Manager
- [ ] `OrderManager` class with `PAPER_TRADE` flag
- [ ] `place_buy_order()` — logs trade at mock price (ATM option LTP ≈ estimated)
- [ ] `place_exit_order()` — exits at target price
- [ ] Persist all paper trades to `trades` table
- [ ] Calculate and store P&L per trade

### 1.7 Mock Market Data Feed
- [ ] `MockDataFeed` class — simulates NIFTY price movements
- [ ] Configurable: feed price sequence from JSON file (for testing)
- [ ] Replays historical data to test strategy logic
- [ ] WebSocket broadcaster: push simulated ticks to frontend

### 1.8 Basic Frontend Dashboard
- [ ] NIFTY price display (from WebSocket)
- [ ] R/S level panel with status indicators (active/triggered/blocked)
- [ ] CE/PE state display (IDLE / L1 / L2 / L3 / BLOCKED)
- [ ] Trade log table (timestamp, side, level, action, P&L)
- [ ] Today's P&L summary card
- [ ] Paper Trade Mode indicator (prominent warning banner)

### Phase 1 Acceptance Criteria
- [ ] Full simulated trading day runs correctly with test data
- [ ] All 10 general rules verified with unit tests
- [ ] Tuesday rule correctly selects next weekly expiry
- [ ] 11:15 AM cutoff and 11:30 AM squareoff working
- [ ] Max 3 lots never exceeded
- [ ] Strike locked after Level 1 — confirmed in tests
- [ ] No re-entry after target achieved — confirmed in tests
- [ ] CE and PE states are fully independent

---

## PHASE 2 — Zerodha Kite Connect Integration
**Duration:** 1–2 weeks  
**Goal:** Real market data + Paper trade orders (no real money yet)

### 2.1 Kite Authentication
- [ ] Kite Connect OAuth flow (login URL → request_token → access_token)
- [ ] `GET /auth/kite/login` — returns Kite login URL
- [ ] `GET /auth/kite/callback` — handles redirect, stores token
- [ ] AES-256-GCM encryption for access_token storage
- [ ] Token validity check (expires 6 AM daily)
- [ ] "Reconnect Zerodha" UI button with token expiry indicator
- [ ] Settings UI: API Key + API Secret input (encrypted storage)

### 2.2 Kite Market Data (Live NIFTY Price)
- [ ] `KiteService` class wrapping kiteconnect SDK
- [ ] `KiteTicker` WebSocket connection
- [ ] Subscribe to `NSE:NIFTY 50` instrument token
- [ ] `on_ticks` callback: write LTP to Redis (`nifty:ltp`)
- [ ] Replace `MockDataFeed` with `KiteDataFeed` (keep mock for testing)
- [ ] Connection status monitoring + auto-reconnect on disconnect
- [ ] Frontend: show live NIFTY price from real Kite feed

### 2.3 Kite Option Chain Integration
- [ ] Fetch and cache `kite.instruments('NFO')` at 9:00 AM daily
- [ ] Store instruments in Redis (search by symbol prefix)
- [ ] `OptionSelector` updated to use real instrument tokens
- [ ] Validate selected option exists and is tradeable
- [ ] Subscribe to option instrument token in KiteTicker after entry

### 2.4 Option LTP Monitoring
- [ ] After entry: subscribe to option symbol in KiteTicker
- [ ] Target monitor: checks each tick for `(ltp - avg_entry) × lots ≥ target_pts`
- [ ] Level 3 SL monitor: checks `(avg_entry - ltp) × lots ≥ sl_pts`
- [ ] Unsubscribe from option KiteTicker after exit

### 2.5 Paper Trade with Real Prices
- [ ] Strategy engine uses REAL Kite NIFTY LTP for level triggering
- [ ] Entry price = actual option LTP at moment of entry (from Kite)
- [ ] Exit price = actual option LTP at moment of exit
- [ ] Orders still simulated (no real Kite order placement yet)
- [ ] P&L calculated using real prices

### 2.6 TradingView Chart Integration
- [ ] Integrate TradingView Lightweight Charts in frontend
- [ ] NIFTY candlestick chart with WebSocket updates
- [ ] Plot R1/R2/R3 as horizontal red lines
- [ ] Plot S1/S2/S3 as horizontal green lines
- [ ] Mark trade entry/exit points on chart
- [ ] Chart auto-adjusts when levels changed in Settings

### Phase 2 Acceptance Criteria
- [ ] Real NIFTY price flowing through system (verify during market hours)
- [ ] Correct option symbols generated for live trading dates
- [ ] Option LTP updating in real-time via KiteTicker
- [ ] Paper trades executing at real prices
- [ ] P&L matches manual calculation from real prices
- [ ] No connection errors during 3-hour simulated session

---

## PHASE 3 — Settings UI, AI Observer & Notifications
**Duration:** 1 week  
**Goal:** Complete user-facing configuration + AI integration

### 3.1 Settings UI (Complete)
- [ ] Zerodha section: API Key, Secret, Connect button, status
- [ ] Strategy Levels section: R1-R3, S1-S3 inputs with validation
- [ ] Execution section: Lot size, Paper Trade toggle, Auto Trade toggle
- [ ] AI section: Provider dropdown (OpenAI/Anthropic/Gemini), API key input
- [ ] AI Observer toggle (enable/disable)
- [ ] Notifications section: Telegram Bot Token, Chat ID
- [ ] Save button with success/error feedback
- [ ] All sensitive fields masked (show last 4 chars only)
- [ ] "Test Connection" buttons for Kite and AI provider

### 3.2 AI Observer Module
- [ ] `AIService` class with pluggable provider support
- [ ] Implement for OpenAI (`gpt-4o`)
- [ ] Implement for Anthropic (`claude-3-5-sonnet`)
- [ ] Implement for Google (`gemini-1.5-pro`)
- [ ] Async task queue: AI analysis never blocks strategy engine
- [ ] Trigger AI analysis on: entry, exit, SL hit, squareoff
- [ ] Context payload: NIFTY level, open positions, P&L, time, VIX (if available)
- [ ] Response parsing: extract suggestion text
- [ ] Store AI suggestions in DB (for session review)
- [ ] Frontend: AI Observer panel shows latest 3 suggestions
- [ ] Graceful degradation: if AI call fails, log error — strategy continues

### 3.3 Telegram Notifications
- [ ] `NotificationService` class
- [ ] Notify on: trade entry, target achieved, SL hit, squareoff, errors
- [ ] Message format: `🟢 BUY NIFTY23150PE @₹85 | 1 Lot | 10:23 AM`
- [ ] Configurable: each event type can be toggled on/off
- [ ] Non-blocking: fire-and-forget async calls

### 3.4 Session Management
- [ ] `POST /auth/login` with username/password (single user app)
- [ ] JWT token issued, stored in HttpOnly cookie
- [ ] All API routes protected by auth middleware
- [ ] Settings page behind auth
- [ ] Auto-logout after 8 hours

### Phase 3 Acceptance Criteria
- [ ] All settings saved/loaded correctly (including after restart)
- [ ] AI suggestions appearing within 10 seconds of trade events
- [ ] AI failure doesn't affect strategy execution
- [ ] Telegram messages received on test events
- [ ] Auth protects all sensitive endpoints

---

## PHASE 4 — Live Trading Validation & Production Hardening
**Duration:** 2 weeks  
**Goal:** Safe transition to real order execution + production stability

### 4.1 Real Order Execution
- [ ] `OrderManager.place_buy_order()` → `kite.place_order()` when not paper trade
- [ ] Order type: `MARKET`, transaction_type: `BUY/SELL`, exchange: `NFO`
- [ ] Store Kite order_id in trades table
- [ ] Order status tracking: `kite.orders()` polling every 2 seconds
- [ ] Handle order rejection (log + alert + re-try once)
- [ ] Handle partial fills (log + alert + manual action required)
- [ ] `place_exit_order()` → MARKET sell for full position

### 4.2 Order Confirmation Loop
- [ ] After placing order: poll order status until COMPLETE or REJECTED
- [ ] Timeout: 10 seconds max (MARKET orders should fill in < 2s)
- [ ] On REJECTED: send Telegram alert, mark trade as FAILED, stop that cycle
- [ ] On COMPLETE: update avg_price from actual fill price

### 4.3 Crash Recovery
- [ ] On backend restart: reload strategy state from Redis
- [ ] Check open positions from Kite (`kite.positions()`) on startup
- [ ] Reconcile DB state with Kite positions
- [ ] If position exists but state=IDLE: alert user, don't auto-close
- [ ] Daily state reset at 9:00 AM (before market open)

### 4.4 Production Checklist
- [ ] Paper Trade mode ON → run for 5 live market sessions with zero errors
- [ ] All strategy rules verified against real option prices
- [ ] P&L calculation verified against Kite contract notes
- [ ] Rate limiting: verify < 3 REST calls/sec during peak
- [ ] Error handling tested: disconnect Kite mid-session, AI API down
- [ ] DB backups configured
- [ ] Nginx + SSL configured
- [ ] Environment variables secured (not in version control)
- [ ] `PAPER_TRADE=false` — enable only after above complete

### 4.5 Pre-Market Daily Checklist (Automated)
- [ ] 8:00 AM: Check Kite access_token validity → alert if expired
- [ ] 8:30 AM: Fetch and cache NFO instruments list
- [ ] 9:00 AM: Reset daily strategy state
- [ ] 9:15 AM: Confirm Kite WebSocket connected (market open)
- [ ] 11:15 AM: Block new entries (automated)
- [ ] 11:30 AM: Force squareoff all open positions (automated)
- [ ] 3:30 PM: Calculate and store daily P&L summary

### Phase 4 Acceptance Criteria
- [ ] 5 consecutive paper-trade sessions with zero errors
- [ ] All 10 strategy rules working with real market data and real prices
- [ ] Live order placement tested in real Kite environment (small qty)
- [ ] Crash recovery tested (restart mid-session)
- [ ] P&L matches Kite ledger within ₹10 tolerance (brokerage rounding)

---

## MILESTONE SUMMARY

| Phase | Duration | Key Deliverable |
|-------|----------|----------------|
| Phase 1 | 2–3 weeks | Paper trade engine, all rules tested, basic UI |
| Phase 2 | 1–2 weeks | Live NIFTY data, real option prices, chart |
| Phase 3 | 1 week | Settings UI, AI Observer, Telegram |
| Phase 4 | 2 weeks | Live order execution, production hardening |
| **Total** | **6–8 weeks** | **Production-ready trading system** |

---

## RISK MITIGATION

| Risk | Mitigation |
|------|-----------|
| Kite token expires mid-session | Alert at 8 AM, graceful degradation if expired |
| Order rejected by Kite | Alert + stop cycle, do not retry blindly |
| WebSocket disconnect | Auto-reconnect with exponential backoff, alert |
| AI API rate limit | Fallback: skip AI for that event, log it |
| Strategy bugs in production | Mandatory paper trade phase before live |
| Multiple lot positions on same strike | State machine prevents, tested in unit tests |
| Market gap (NIFTY jumps past level) | Level detection uses LTP crossing, not exact match |
