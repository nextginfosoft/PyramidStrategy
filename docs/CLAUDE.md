# PyramidStrategy — Project Rules for Claude Cowork
## Master Configuration & Development Guide

---

## 1. PROJECT IDENTITY

**App Name:** PyramidStrategy  
**Domain:** Automated NIFTY Options Trading — Intraday Pyramid Strategy  
**Owner:** Santosh Kumar  
**Stack:** React (Frontend) · FastAPI/Python (Backend) · PostgreSQL + Redis · Zerodha Kite Connect API  
**Primary Instrument:** NIFTY 50 Options (NSE)

---

## 2. STRATEGY RULES — NON-NEGOTIABLE (DO NOT DEVIATE)

> These rules are the SOURCE OF TRUTH. Every feature, module, and line of code must strictly conform.

### 2.1 PE Strategy (Resistance Levels — Bearish)
| Level | NIFTY Trigger | Action | Strike | Lots Total | Target | SL |
|-------|--------------|--------|--------|-----------|--------|-----|
| R1 | User-defined | Buy | ATM + 50 PE (same-day expiry) | 1 | 20 pts on 1 lot | None |
| R2 | User-defined | Add | Same strike as R1 | 2 | 20 pts on 2 lots | None |
| R3 | User-defined | Add | Same strike as R1 | 3 | 20 pts on 3 lots | 10 pts on 3 lots |

### 2.2 CE Strategy (Support Levels — Bullish)
| Level | NIFTY Trigger | Action | Strike | Lots Total | Target | SL |
|-------|--------------|--------|--------|-----------|--------|-----|
| S1 | User-defined | Buy | ATM - 50 CE (same-day expiry) | 1 | 20 pts on 1 lot | None |
| S2 | User-defined | Add | Same strike as S1 | 2 | 20 pts on 2 lots | None |
| S3 | User-defined | Add | Same strike as S1 | 3 | 20 pts on 3 lots | 10 pts on 3 lots |

### 2.3 General Rules (HARD-CODED, never make configurable)
1. Same-day expiry contract for all entries (EXCEPT Tuesdays — see Rule 9)
2. Strike selected at Level 1 (R1/S1) is LOCKED for all subsequent levels — never change
3. Max position = 3 lots total per side (CE or PE)
4. On target achieved at any level → exit ENTIRE position immediately
5. After target achieved at a level → NO re-entry from that same level on same day
6. Stop Loss applies ONLY at Level 3 (R3/S3) = 10 points; Levels 1 & 2 have NO SL
7. **Square-off deadline: 11:30 AM IST — all open positions must be closed**
8. **No fresh entries after 11:15 AM IST**
9. **Tuesday Rule:** Use NEXT weekly expiry contract instead of same-day expiry
10. After a target is achieved at any level, if NIFTY reaches the NEXT level, start a NEW cycle from 1 lot

### 2.4 Strategy Engine Invariants (enforce in code)
- Both CE and PE strategies run INDEPENDENTLY and SIMULTANEOUSLY
- A target/SL event on PE side does NOT affect the CE side and vice versa
- Target = 20 pts × number of lots at the time of exit (e.g., 2 lots = 40 total pts)
- The system tracks each side (CE/PE) separately with its own state machine

---

## 3. TECH STACK DECISIONS

### Frontend
- **Framework:** React 18 + TypeScript
- **UI Library:** Tailwind CSS + shadcn/ui
- **State:** Zustand (global) + React Query (server state)
- **Charts:** TradingView Lightweight Charts (NIFTY price) + Recharts (P&L)
- **WebSocket:** Native WebSocket client for real-time Kite data
- **Build Tool:** Vite

### Backend
- **Framework:** FastAPI (Python 3.11+)
- **Task Queue:** Celery + Redis (strategy engine runs as background tasks)
- **WebSocket Server:** FastAPI WebSocket for pushing updates to frontend
- **Database ORM:** SQLAlchemy + Alembic (migrations)
- **Scheduler:** APScheduler (time-based rules: 11:15/11:30 AM cutoffs)
- **Config:** Pydantic Settings + `.env` file

### Data & Persistence
- **PostgreSQL:** Trades, configuration, daily P&L, audit log
- **Redis:** Real-time NIFTY price cache, strategy state, session store
- **In-memory:** Strategy state machine (mirrored to Redis for crash recovery)

### Integrations
- **Zerodha Kite Connect API:** Market data (WebSocket + REST) + order execution
- **AI Provider:** Pluggable — supports OpenAI GPT-4o, Anthropic Claude, Google Gemini
- **Notifications:** Telegram Bot API (optional, configurable)

---

## 4. PROJECT FOLDER STRUCTURE

```
pyramid-strategy/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard/          # Main trading dashboard
│   │   │   ├── Settings/           # API keys, strategy config
│   │   │   ├── TradeLog/           # Live trade table
│   │   │   ├── PnLChart/           # P&L visualization
│   │   │   ├── LevelPanel/         # R1-R3, S1-S3 level display
│   │   │   └── AIObserver/         # AI suggestion panel
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── store/                  # Zustand stores
│   │   ├── services/               # API client, WebSocket
│   │   └── types/                  # TypeScript interfaces
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py         # Kite login, token management
│   │   │   │   ├── config.py       # Strategy config CRUD
│   │   │   │   ├── trades.py       # Trade history, P&L
│   │   │   │   ├── strategy.py     # Start/stop/status
│   │   │   │   └── ai.py           # AI observer endpoints
│   │   │   └── websocket.py        # WS endpoint for frontend
│   │   ├── core/
│   │   │   ├── strategy_engine.py  # THE PYRAMID LOGIC — core
│   │   │   ├── state_machine.py    # CE/PE state machines
│   │   │   ├── option_selector.py  # ATM+50/ATM-50 finder
│   │   │   ├── order_manager.py    # Kite order placement
│   │   │   ├── risk_manager.py     # SL, target, time rules
│   │   │   └── time_rules.py       # 11:15/11:30 cutoffs, Tuesday rule
│   │   ├── models/                 # SQLAlchemy models
│   │   ├── schemas/                # Pydantic schemas
│   │   ├── services/
│   │   │   ├── kite_service.py     # Kite Connect wrapper
│   │   │   ├── ai_service.py       # AI API abstraction
│   │   │   └── notification.py     # Telegram/email alerts
│   │   ├── db/                     # Database init, sessions
│   │   └── config.py               # App settings
│   ├── tests/
│   │   ├── test_strategy_engine.py
│   │   ├── test_state_machine.py
│   │   └── test_time_rules.py
│   └── requirements.txt
│
├── docker-compose.yml
├── .env.example
├── CLAUDE.md                       # This file
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
└── ROADMAP.md
```

---

## 5. DATABASE SCHEMA (Key Tables)

```sql
-- Strategy configuration (user-editable)
CREATE TABLE strategy_config (
    id SERIAL PRIMARY KEY,
    r1 NUMERIC NOT NULL, r2 NUMERIC NOT NULL, r3 NUMERIC NOT NULL,
    s1 NUMERIC NOT NULL, s2 NUMERIC NOT NULL, s3 NUMERIC NOT NULL,
    lot_size INTEGER DEFAULT 75,  -- NIFTY lot size
    target_points NUMERIC DEFAULT 20,
    sl_points NUMERIC DEFAULT 10,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Trade log
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    trade_date DATE NOT NULL,
    side VARCHAR(2) NOT NULL,          -- 'CE' or 'PE'
    level VARCHAR(2) NOT NULL,         -- 'R1','R2','R3','S1','S2','S3'
    instrument VARCHAR(50) NOT NULL,   -- 'NIFTY26JUN23150PE'
    strike INTEGER NOT NULL,
    expiry DATE NOT NULL,
    action VARCHAR(4) NOT NULL,        -- 'BUY' or 'EXIT'
    lots INTEGER NOT NULL,
    avg_price NUMERIC,
    trigger_nifty_level NUMERIC,
    kite_order_id VARCHAR(50),
    status VARCHAR(20),                -- 'OPEN','TARGET','SL','SQUAREOFF','CANCELLED'
    pnl NUMERIC,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Daily P&L summary
CREATE TABLE daily_pnl (
    id SERIAL PRIMARY KEY,
    trade_date DATE UNIQUE NOT NULL,
    gross_pnl NUMERIC DEFAULT 0,
    brokerage NUMERIC DEFAULT 0,
    net_pnl NUMERIC DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- API keys (encrypted at rest)
CREATE TABLE api_config (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(30) NOT NULL,    -- 'zerodha', 'openai', 'anthropic', 'telegram'
    api_key_encrypted TEXT,
    api_secret_encrypted TEXT,
    extra_config JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 6. STRATEGY ENGINE STATE MACHINE

Each side (CE and PE) runs an independent state machine:

```
IDLE
  │
  ▼ (NIFTY hits R1/S1)
LEVEL_1_ENTERED  [1 lot open, strike locked]
  │
  ├─ TARGET HIT → EXIT_ALL → LEVEL_BLOCKED (no re-entry this day from R1)
  │    └─ If next level hit → NEW CYCLE (back to IDLE for that leg)
  │
  └─ No target → wait
       │
       ▼ (NIFTY hits R2/S2)
  LEVEL_2_ENTERED  [2 lots open, same strike]
       │
       ├─ TARGET HIT → EXIT_ALL → LEVEL_BLOCKED
       │
       └─ No target → wait
            │
            ▼ (NIFTY hits R3/S3)
       LEVEL_3_ENTERED  [3 lots open, same strike, SL ACTIVE]
            │
            ├─ TARGET HIT → EXIT_ALL
            ├─ SL HIT → EXIT_ALL
            └─ 11:30 AM → FORCE_SQUAREOFF
```

---

## 7. KITE CONNECT API USAGE RULES

- **Authentication:** OAuth flow — redirect user to Kite login, capture `request_token`, exchange for `access_token`. Store encrypted in DB.
- **Market Data:** Use Kite WebSocket (`KiteTicker`) for real-time NIFTY spot price — subscribe to `NSE:NIFTY 50` instrument.
- **Option Chain:** Use `kite.ltp()` or `kite.quote()` to fetch option prices. Use `kite.instruments('NFO')` to find correct option symbol.
- **Order Type:** MARKET order for all entries and exits (speed over price for intraday options).
- **Paper Trade Mode:** When `PAPER_TRADE=true` in config, simulate orders without calling Kite — log as if executed at LTP.
- **Rate Limits:** Respect Kite rate limits (3 req/sec for REST, WebSocket for streaming). Use Redis to cache option prices with 1-second TTL.

---

## 8. AI OBSERVER MODULE

- AI observes ALL trades in real-time (non-blocking — never delays trade execution)
- AI API key is user-provided via Settings UI (stored encrypted in `api_config` table)
- Supported providers: OpenAI (gpt-4o), Anthropic (claude-3-5-sonnet), Google (gemini-2.5-flash)
- AI receives context: current NIFTY level, open positions, P&L, market conditions
- AI outputs: trade suggestion, risk warning, pattern observation (displayed in "AI Observer" panel)
- AI is ADVISORY ONLY — it NEVER triggers or blocks trades automatically
- AI analysis runs asynchronously (non-blocking) after each trade event

### AI System Prompt (Base)
```
You are an expert NIFTY options trading analyst observing the PyramidStrategy.
Strategy: Pyramid position sizing at predefined R/S levels, buying ATM±50 options.
Your job: Observe live trades and provide concise, actionable insights.
Rules you must follow:
- Never suggest deviating from the defined pyramid rules
- Flag if market conditions look unfavorable for the strategy
- Provide post-trade analysis after each exit
- Keep suggestions to 2-3 sentences max
- Focus on: volatility, IV crush risk, time decay (after 11 AM), market breadth
```

---

## 9. SETTINGS UI — CONFIGURABLE PARAMETERS

All user-configurable settings must go through the Settings page. Nothing should require code changes.

| Category | Setting | Type | Notes |
|----------|---------|------|-------|
| Strategy Levels | R1, R2, R3 | Number | Resistance levels (PE trigger) |
| Strategy Levels | S1, S2, S3 | Number | Support levels (CE trigger) |
| Execution | Lot Size | Number | Default 75 (NIFTY lot size) |
| Execution | Paper Trade Mode | Toggle | Simulate without real orders |
| Execution | Auto Trade | Toggle | Master on/off switch |
| Zerodha | API Key | Text (encrypted) | Kite Connect API key |
| Zerodha | API Secret | Text (encrypted) | Kite Connect API secret |
| Zerodha | Access Token | Text | Auto-filled after Kite login |
| AI | Provider | Select | OpenAI / Anthropic / Gemini |
| AI | API Key | Text (encrypted) | User's AI provider key |
| AI | AI Observer | Toggle | Enable/disable AI analysis |
| Notifications | Telegram Bot Token | Text (encrypted) | Optional alerts |
| Notifications | Telegram Chat ID | Text | Optional |

---

## 10. SECURITY RULES

- All API keys stored AES-256 encrypted in DB (use `cryptography` library in Python)
- Never log API keys or access tokens
- Frontend never receives raw API keys — only masked versions (e.g., `sk-...xxxx`)
- Kite `access_token` expires daily — implement auto-refresh reminder at 8:00 AM
- All backend endpoints require session authentication (JWT or session cookie)
- CORS restricted to localhost in development, specific domain in production
- `.env` file contains `ENCRYPTION_KEY` — never commit to version control

---

## 11. CODING STANDARDS

### Python (Backend)
- Type hints on all functions
- Pydantic models for all request/response schemas
- Async/await for all I/O (Kite WebSocket, DB queries, AI calls)
- Strategy engine logic must be 100% unit tested
- Use `loguru` for structured logging
- All strategy decisions logged with timestamp, NIFTY level, action taken

### TypeScript (Frontend)
- Strict mode enabled
- All API responses typed with generated/manual TypeScript interfaces
- No `any` types in strategy-critical components
- Real-time data via WebSocket hook (`useWebSocket`)
- Dashboard auto-refreshes P&L every 5 seconds as fallback

### General
- Git commit messages: `feat:`, `fix:`, `chore:`, `test:` prefixes
- No commented-out code in production
- Environment-specific config via `.env` files only

---

## 12. TESTING REQUIREMENTS

- **Strategy Engine:** Unit tests for ALL 10 general rules — must pass before any deploy
- **State Machine:** Test each transition (Level 1→2→3, target hit, SL hit, squareoff)
- **Time Rules:** Test 11:15 AM cutoff, 11:30 AM squareoff, Tuesday expiry selection
- **Paper Trade:** Integration test running a full simulated trading day
- **Order Manager:** Mock Kite API responses for order placement tests

---

## 13. WHAT CLAUDE MUST NEVER DO

1. ❌ Never hardcode R1/R2/R3/S1/S2/S3 values — always read from config
2. ❌ Never add a Stop Loss at Level 1 or Level 2
3. ❌ Never change the strike after Level 1 entry
4. ❌ Never allow entry after 11:15 AM
5. ❌ Never keep positions open past 11:30 AM
6. ❌ Never let AI block or delay order execution
7. ❌ Never store unencrypted API keys anywhere
8. ❌ Never allow more than 3 lots total per side
9. ❌ Never mix CE and PE state (they are independent)
10. ❌ Never use LIMIT orders for exits — always MARKET for speed

---

## 14. DEVELOPMENT ENVIRONMENT SETUP

```bash
# Clone and setup
git clone <repo>
cd pyramid-strategy

# Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Fill in .env values

# Start services
docker-compose up -d  # starts PostgreSQL + Redis

# Run migrations
alembic upgrade head

# Start backend
uvicorn app.main:app --reload --port 8000

# Frontend
cd ../frontend
npm install
npm run dev  # starts on port 5173
```

---

## 15. ENVIRONMENT VARIABLES (.env.example)

```env
# App
APP_ENV=development
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-32-byte-encryption-key

# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/pyramidstrategy
REDIS_URL=redis://localhost:6379/0

# Zerodha (filled via Settings UI — these are fallback)
KITE_API_KEY=
KITE_API_SECRET=

# Paper Trade Mode
PAPER_TRADE=true

# AI (filled via Settings UI — these are fallback)
AI_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Notifications (optional)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Frontend
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```
