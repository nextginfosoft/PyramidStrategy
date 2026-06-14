# PyramidStrategy — High-Level System Architecture

---

## 1. SYSTEM OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER BROWSER                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    React Frontend (Vite)                  │   │
│  │                                                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │   │
│  │  │Dashboard │ │Settings  │ │TradeLog  │ │AI Observer │  │   │
│  │  │+ Chart   │ │Panel     │ │+ P&L     │ │Panel       │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │   │
│  │         │            │           │              │         │   │
│  │         └────────────┴───────────┴──────────────┘        │   │
│  │                      REST API + WebSocket                 │   │
│  └──────────────────────────────┬────────────────────────────┘  │
└─────────────────────────────────┼───────────────────────────────┘
                                  │ HTTPS / WSS
┌─────────────────────────────────▼───────────────────────────────┐
│                        FASTAPI BACKEND                           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    API Layer (Routes)                    │    │
│  │  /auth  /config  /trades  /strategy  /ai  /ws           │    │
│  └─────────────────────────────┬───────────────────────────┘    │
│                                 │                                │
│  ┌──────────────────────────────▼──────────────────────────┐    │
│  │                    Core Business Logic                   │    │
│  │                                                          │    │
│  │  ┌─────────────────────┐   ┌────────────────────────┐   │    │
│  │  │  Strategy Engine    │   │   Risk Manager         │   │    │
│  │  │  ┌───────────────┐  │   │  • SL enforcement      │   │    │
│  │  │  │CE State Mach. │  │   │  • Time cutoffs        │   │    │
│  │  │  └───────────────┘  │   │  • Position limits     │   │    │
│  │  │  ┌───────────────┐  │   └────────────────────────┘   │    │
│  │  │  │PE State Mach. │  │                                 │    │
│  │  │  └───────────────┘  │   ┌────────────────────────┐   │    │
│  │  └─────────────────────┘   │   Option Selector      │   │    │
│  │                             │  • ATM±50 finder       │   │    │
│  │  ┌─────────────────────┐   │  • Expiry resolver     │   │    │
│  │  │  Order Manager      │   │  • Tuesday rule        │   │    │
│  │  │  • Buy/Exit orders  │   └────────────────────────┘   │    │
│  │  │  • Paper trade sim  │                                 │    │
│  │  │  • Order tracking   │   ┌────────────────────────┐   │    │
│  │  └─────────────────────┘   │   AI Service           │   │    │
│  │                             │  • Async observer      │   │    │
│  │                             │  • Multi-provider      │   │    │
│  │                             │  • Non-blocking        │   │    │
│  │                             └────────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Data Layer                            │    │
│  │                                                          │    │
│  │   ┌─────────────────┐        ┌──────────────────────┐   │    │
│  │   │   PostgreSQL     │        │       Redis           │   │    │
│  │   │ • Trades         │        │ • NIFTY price cache  │   │    │
│  │   │ • Config         │        │ • Strategy state     │   │    │
│  │   │ • Daily P&L      │        │ • Session store      │   │    │
│  │   │ • API keys (enc) │        │ • Rate limit counter │   │    │
│  │   └─────────────────┘        └──────────────────────┘   │    │
│  └──────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
┌────────▼──────┐    ┌─────────▼──────┐    ┌────────▼──────┐
│ Zerodha Kite  │    │   AI Provider  │    │   Telegram    │
│ Connect API   │    │                │    │   Bot API     │
│               │    │ • OpenAI       │    │ (Optional     │
│ • WebSocket   │    │ • Anthropic    │    │  Alerts)      │
│   (NIFTY LTP) │    │ • Gemini       │    └───────────────┘
│ • REST        │    └────────────────┘
│   (Orders,    │
│    Options)   │
└───────────────┘
```

---

## 2. COMPONENT DEEP DIVE

### 2.1 Strategy Engine (Core — `strategy_engine.py`)

This is the heart of the system. It runs as a continuous background process:

```
Market Data Feed (WebSocket)
        │
        ▼
  NIFTY LTP Received
        │
        ▼
  ┌─────────────────────────────────────────────────────┐
  │              Level Detector                          │
  │  • Compare LTP against R1, R2, R3, S1, S2, S3      │
  │  • Detect first crossing (not continuous trigger)   │
  │  • Debounce: level must hold for 1 tick             │
  └──────────────────┬──────────────────────────────────┘
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
  ┌───────────────┐    ┌───────────────┐
  │  PE State     │    │  CE State     │
  │  Machine      │    │  Machine      │
  │               │    │               │
  │  IDLE         │    │  IDLE         │
  │  L1_ENTERED   │    │  L1_ENTERED   │
  │  L2_ENTERED   │    │  L2_ENTERED   │
  │  L3_ENTERED   │    │  L3_ENTERED   │
  │  BLOCKED      │    │  BLOCKED      │
  └──────┬────────┘    └───────┬───────┘
         │                     │
         ▼                     ▼
  ┌─────────────────────────────────────────────────────┐
  │              Order Manager                           │
  │  • Resolve option symbol (ATM±50, expiry)           │
  │  • Place MARKET order via Kite Connect              │
  │  • OR simulate (paper trade mode)                   │
  │  • Update trade log in PostgreSQL                   │
  └──────────────────┬──────────────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────────────┐
  │              Target / SL Monitor                     │
  │  • Poll option LTP every second                     │
  │  • Check if (current_ltp - entry_avg) ≥ target_pts │
  │  • At Level 3: check SL (entry_avg - current_ltp)  │
  │  • On trigger: place EXIT MARKET order              │
  └──────────────────┬──────────────────────────────────┘
                     │
                     ▼
  ┌─────────────────────────────────────────────────────┐
  │         Event Bus (Redis Pub/Sub)                    │
  │  • Publish trade events to WebSocket broadcaster    │
  │  • Async notify AI Observer                         │
  │  • Async send Telegram alert                        │
  └─────────────────────────────────────────────────────┘
```

### 2.2 Option Selector (`option_selector.py`)

```python
# Logic flow:
# 1. Get current NIFTY spot from Redis cache
# 2. Round to nearest 50 → ATM strike
# 3. For PE: ATM + 50; For CE: ATM - 50
# 4. Determine expiry:
#    - If Tuesday → next weekly Thursday expiry
#    - Else → same-day expiry (if today is Thursday = weekly expiry)
# 5. Build instrument symbol: NIFTY{DDMMMYY}{STRIKE}{CE/PE}
#    e.g., NIFTY26JUN2523200PE
# 6. Validate against kite.instruments('NFO') cache (refreshed at 9:00 AM)
# 7. Return tradeable symbol + lot_size
```

### 2.3 Real-Time Data Flow

```
Kite WebSocket (KiteTicker)
    │
    ├─ Subscribe: NSE:NIFTY 50 (spot price)
    ├─ Subscribe: NFO:NIFTY{option} (option LTP — added dynamically after entry)
    │
    ▼
on_ticks callback (Python async)
    │
    ├─ Write NIFTY LTP → Redis (key: nifty:ltp, TTL: 5s)
    ├─ Write option LTP → Redis (key: option:{symbol}:ltp, TTL: 5s)
    │
    └─ Trigger strategy engine evaluation
            │
            ▼
    Strategy Engine checks levels → takes action if needed
            │
            ▼
    Publish to Redis Pub/Sub → Frontend WebSocket broadcaster
```

### 2.4 Frontend Dashboard Layout

```
┌──────────────────────────────────────────────────────────┐
│  🔺 PyramidStrategy          [●LIVE] [⏸ PAUSE] [⚙ SETTINGS]│
├──────────────────┬───────────────────────────────────────┤
│  NIFTY: 23,186   │         TODAY'S P&L                   │
│  ████████████    │  ┌────────────────────────────────┐   │
│  [TradingView    │  │  +₹2,400  (2 trades | 2 wins)  │   │
│   Price Chart]   │  └────────────────────────────────┘   │
│                  │                                        │
│  R3: 23,300  🔴 │  P&L CHART (intraday line chart)      │
│  R2: 23,220  🔴 │  ┌────────────────────────────────┐   │
│  R1: 23,170  🟡 │  │  ▁▂▃▅▇▇▆▆▄▄▄▅▆▆▇▇▇▇▇          │   │
│  ─── NIFTY ──── │  └────────────────────────────────┘   │
│  S1: 23,070  🟡 │                                        │
│  S2: 23,025  ⚪ │  OPEN POSITIONS                        │
│  S3: 22,950  ⚪ │  ┌────────────────────────────────┐   │
│                  │  │ NIFTY 23150 PE │ 1L │ +12pts  │   │
│  CE: 🟢 IDLE    │  └────────────────────────────────┘   │
│  PE: 🟡 L1 OPEN │                                        │
├──────────────────┴───────────────────────────────────────┤
│  TRADE LOG              AI OBSERVER                       │
│  ┌─────────────────┐   ┌──────────────────────────────┐  │
│  │ 10:23 BUY PE    │   │ 🤖 IV is elevated at 15.2%.  │  │
│  │ 1L @ 23150PE    │   │ Time decay risk after 10:30  │  │
│  │ 10:31 EXIT      │   │ AM. Monitor closely at R2.   │  │
│  │ +20pts ✅       │   └──────────────────────────────┘  │
│  └─────────────────┘                                      │
└──────────────────────────────────────────────────────────┘
```

---

## 3. DATA FLOW DIAGRAMS

### 3.1 Trade Execution Flow (Happy Path — PE, R1 hit)

```
1. NIFTY LTP = 24,101 (crosses R1 = 24,100)
        │
2. Strategy Engine: PE State = IDLE → trigger L1 entry
        │
3. Option Selector: ATM = 24,100, ATM+50 = 24,150 PE
   Check expiry: Not Tuesday → same-day expiry
   Symbol: NIFTY11JUN2524150PE
        │
4. Risk Manager checks:
   ✅ Time < 11:15 AM
   ✅ PE side not blocked
   ✅ Lots < 3
        │
5. Order Manager: MARKET BUY 1 lot (75 qty) → Kite API
        │
6. Kite confirms order → order_id stored in DB
        │
7. Strike LOCKED: 24150 PE locked for this cycle
   PE State → LEVEL_1_ENTERED
        │
8. Subscribe to NIFTY11JUN2524150PE in KiteTicker
        │
9. Monitor option LTP:
   Entry price: ₹85 (example)
   Target: ₹85 + 20 = ₹105
        │
10. Option hits ₹105 → EXIT MARKET order → all 1 lot
        │
11. P&L: +₹1,500 (20pts × 75 qty)
    PE State → LEVEL_1_BLOCKED (no re-entry at R1 today)
        │
12. AI Observer (async, non-blocking):
    "Target achieved cleanly. R1 level respected well.
    Watch for R2 as next opportunity."
```

### 3.2 Authentication Flow (Kite Connect)

```
User clicks "Connect Zerodha"
        │
Backend generates Kite login URL
        │
User redirected to kite.zerodha.com/connect/login
        │
User logs in → Kite redirects to callback URL with request_token
        │
Backend: POST /session/token with (api_key, request_token, checksum)
        │
Kite returns access_token (valid until 6 AM next day)
        │
Backend encrypts and stores access_token in DB
Frontend shows "Connected ✅" status
```

---

## 4. SECURITY ARCHITECTURE

```
User Input (API Keys)
        │
        ▼
Frontend (masked display only)
        │ HTTPS POST
        ▼
Backend API endpoint /config/api-keys
        │
        ▼
AES-256-GCM Encryption (key from ENV)
        │
        ▼
PostgreSQL: api_config table (encrypted_value column)
        │
        ▼ (at runtime, decrypted in-memory only)
Kite Service / AI Service (never logged)
```

---

## 5. DEPLOYMENT ARCHITECTURE

### Development
```
localhost:5173  (React Vite dev server)
      ↕ proxy
localhost:8000  (FastAPI uvicorn)
      ↕
localhost:5432  (PostgreSQL via Docker)
localhost:6379  (Redis via Docker)
```

### Production (Single Server / VPS)
```
                    ┌─────────────┐
Internet ──HTTPS──► │   Nginx     │
                    │  Reverse    │
                    │  Proxy      │
                    └──────┬──────┘
                           │
               ┌───────────┼───────────┐
               │           │           │
           port 80/443  port 8000   Static
               │           │         Files
           Redirect    FastAPI      React Build
                       (Gunicorn
                        4 workers)
                           │
               ┌───────────┼───────────┐
               │           │           │
          PostgreSQL     Redis       Celery
          (port 5432)  (port 6379)  Worker
```

---

## 6. KEY TECHNICAL DECISIONS

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend language | Python | Kite Connect SDK is Python-native |
| API framework | FastAPI | Async support, WebSocket, auto-docs |
| Frontend | React + TS | Type safety for financial data |
| Real-time | WebSocket (not polling) | Sub-second latency needed |
| Cache | Redis | LTP updates every tick, need speed |
| DB | PostgreSQL | ACID compliance for trade records |
| Order type | MARKET | Speed over price for intraday exits |
| State persistence | Redis + PostgreSQL | Redis for speed, DB for durability |
| AI integration | Async, non-blocking | Never delay trade execution |
| Paper trade | Toggle in settings | Mandatory for safe testing |

---

## 7. MONITORING & OBSERVABILITY

- **Logging:** `loguru` with JSON output — every strategy decision logged
- **Key log events:** level_triggered, order_placed, target_hit, sl_hit, squareoff, error
- **Health endpoint:** `GET /health` — checks DB, Redis, Kite connection
- **Metrics (future):** Prometheus + Grafana for latency tracking
- **Error alerting:** Telegram notification on order failures or connection drops

---

## 8. LATENCY REQUIREMENTS

| Operation | Target Latency | Notes |
|-----------|---------------|-------|
| NIFTY LTP → Level detection | < 100ms | Via WebSocket tick |
| Level detection → Order placement | < 500ms | Critical path |
| Option LTP polling | Every 1 second | Via KiteTicker or REST |
| Target/SL check | < 200ms | After each LTP update |
| Frontend P&L update | < 1 second | Via WebSocket push |
| AI analysis | < 10 seconds | Async, non-blocking |
