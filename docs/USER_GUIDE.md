# PyramidStrategy — User Guide
## All Phases: Paper Trading · Live Data · AI Observer · Live Orders

---

## Table of Contents

1. [What is PyramidStrategy?](#1-what-is-pyramidstrategy)
2. [Prerequisites](#2-prerequisites)
3. [First-Time Installation](#3-first-time-installation)
4. [Phase 1 — Paper Trading Guide](#4-phase-1--paper-trading-guide)
   - 4.1 Start the Backend
   - 4.2 Start the Frontend
   - 4.3 Configure Strategy Levels
   - 4.4 Run a Paper Trade Session
   - 4.5 Simulate NIFTY Price Movement
   - 4.6 Read the Dashboard
   - 4.7 Run Tests
5. [Phase 2 — Live Kite Data Guide](#5-phase-2--live-kite-data-guide)
   - 5.1 Get Zerodha Kite Connect API Key
   - 5.2 Save API Credentials in Settings
   - 5.3 Connect to Kite (OAuth Login)
   - 5.4 Start the Live NIFTY Feed
   - 5.5 Load NFO Instruments
   - 5.6 Verify Live Data is Flowing
   - 5.7 Daily Reconnect Routine
6. [Phase 3 — Login, AI Observer & Telegram](#6-phase-3--login-ai-observer--telegram)
   - 6.1 Logging In (JWT Authentication)
   - 6.2 Configure the AI Observer
   - 6.3 Using the AI Observer Panel
   - 6.4 Configure Telegram Notifications
   - 6.5 Test Telegram Connection
   - 6.6 Complete Settings UI Reference
7. [Phase 4 — Live Order Execution](#7-phase-4--live-order-execution)
   - 7.1 Enable Live Trading Mode
   - 7.2 Pre-Flight Safety Checks
   - 7.3 What Happens on Each Trade
   - 7.4 Order Retry and Failure Handling
   - 7.5 Going Live — Step-by-Step Checklist
   - 7.6 Daily Live Trading Routine
8. [Strategy Rules Reference](#8-strategy-rules-reference)
9. [Dashboard Walkthrough](#9-dashboard-walkthrough)
10. [Common Errors & Fixes](#10-common-errors--fixes)
11. [Safety Checklist Before Live Trading](#11-safety-checklist-before-live-trading)
12. [How to Run Using Docker](#12-how-to-run-using-docker)

---

## 1. What is PyramidStrategy?

PyramidStrategy is an automated intraday NIFTY options trading system based on the **Pyramid position-sizing strategy**.

**How it works:**
- You define 3 resistance levels (R1, R2, R3) and 3 support levels (S1, S2, S3) before the market opens
- When NIFTY touches a resistance level → system buys NIFTY PE options (bearish bet)
- When NIFTY touches a support level → system buys NIFTY CE options (bullish bet)
- Each subsequent level adds 1 more lot (1 lot at L1, 2 lots at L2, 3 lots at L3)
- Target: **20 points profit** on total position → exit everything immediately
- Stop Loss: **10 points loss** at Level 3 only → exit everything
- All positions are squared off at **11:30 AM IST** regardless

| Phase | What it does |
|-------|-------------|
| **Phase 1** | Paper trading — fake orders, mock NIFTY prices |
| **Phase 2** | Real NIFTY prices from Zerodha KiteTicker — still fake orders |
| **Phase 3** | JWT login, AI Observer (GPT/Claude/Gemini), Telegram alerts |
| **Phase 4** | Real Kite orders — live money trading |

---

## 2. Prerequisites

Make sure these are installed on your Windows machine:

| Software | Version | Check Command |
|----------|---------|---------------|
| Python | 3.11 or higher | `python --version` |
| Node.js | 18 or higher | `node --version` |
| Git | Any | `git --version` |

No Docker, no Redis server, no PostgreSQL needed for any phase.

---

## 3. First-Time Installation

Open **PowerShell** and run these commands once:

### Backend Setup

```powershell
cd D:\PyramidStreategy\backend

# Create virtual environment
python -m venv venv

# Activate it
venv\Scripts\activate

# Install all Python dependencies
pip install -r requirements.txt

# Create your .env file from the template
copy .env.example .env
```

Now open `D:\PyramidStreategy\backend\.env` in Notepad and set:

```env
DATABASE_URL=sqlite:///./pyramidstrategy.db
USE_FAKE_REDIS=true
PAPER_TRADE=true
ENCRYPTION_KEY=change-this-to-exactly-32-bytes!!
SECRET_KEY=any-random-secret-string-here
```

> **Important:** `ENCRYPTION_KEY` must be exactly 32 characters. Example:
> `MyPyramidStrategy2024SecretKey32`

### Frontend Setup

```powershell
cd D:\PyramidStreategy\frontend
npm install
```

---

## 4. Phase 1 — Paper Trading Guide

Phase 1 runs entirely without Zerodha API keys. Orders are simulated, prices are mocked. Use this phase to understand the strategy and test your level configuration.

---

### 4.1 Start the Backend

Open a **new PowerShell window** and run:

```powershell
cd D:\PyramidStreategy\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

You should see:
```
INFO: PyramidStrategy Backend starting...
INFO: Paper Trade: True
INFO: Fake Redis: True
INFO: Uvicorn running on http://0.0.0.0:8000
```

Keep this window open. The backend API is now live at `http://localhost:8000`.

> Swagger docs available at: `http://localhost:8000/docs`

---

### 4.2 Start the Frontend

Open a **second PowerShell window** and run:

```powershell
cd D:\PyramidStreategy\frontend
npm run dev
```

You should see:
```
VITE ready in 300ms
➜ Local: http://localhost:5173/
```

Open your browser at **`http://localhost:5173`**

You will be shown the **Login page** first (added in Phase 3). Log in with:
- **Username:** `admin`
- **Password:** `pyramid123`

---

### 4.3 Configure Strategy Levels

Before running any trades, you must set your NIFTY levels.

1. Click the **⚙ Settings** button (top right of the dashboard)
2. In the **Strategy Levels** section, enter:

| Field | What it means | Example |
|-------|--------------|---------|
| R1 | First resistance — buy PE here | 24500 |
| R2 | Second resistance — add to PE | 24550 |
| R3 | Third resistance — final PE add (SL active) | 24600 |
| S1 | First support — buy CE here | 24300 |
| S2 | Second support — add to CE | 24250 |
| S3 | Third support — final CE add (SL active) | 24200 |

3. Set **Lot Size** = `75` (standard NIFTY lot size)
4. Ensure **Paper Trade Mode** is toggled **ON** (blue)
5. Click **Save Levels**

> **Rule:** R1 < R2 < R3 (resistance levels go up) and S1 > S2 > S3 (support levels go down)

---

### 4.4 Run a Paper Trade Session

1. From the dashboard, click the **▶ START** button
2. The engine status changes to **RUNNING**
3. You will see the Level Panel showing your R1–R3 (red) and S1–S3 (green) levels

The engine is now live. In Phase 1, it waits for simulated price ticks.

To **stop** the engine, click **⏹ STOP**.

---

### 4.5 Simulate NIFTY Price Movement

Since Phase 1 has no live data feed, you manually push NIFTY prices to test the strategy.

**The "Simulate Tick" panel** is visible on the left side of the dashboard (only shown in Paper Trade mode).

**How to test a full trade cycle:**

Assume your levels are: R1=24500, R2=24550, R3=24600

**Step 1 — Trigger L1 PE entry:**
- Type `24500` in the Simulate Tick box → click **→**
- Watch: PE side enters L1, buys 1 lot of ATM+50 PE
- Trade log shows a BUY entry

**Step 2 — Trigger L2 PE add:**
- Type `24550` → click **→**
- PE side adds 1 more lot (now 2 lots total, same strike)

**Step 3 — Trigger L3 PE add (SL now active):**
- Type `24600` → click **→**
- PE side adds final lot (3 lots total, SL at -10 pts now active)

**Step 4A — Hit Target:**
- The option price must rise 20 pts above your average entry
- In mock mode, option LTP starts at ₹100. Push enough ticks to trigger the target check.

**Step 4B — Test Stop Loss:**
- Simulate price moving against you (option falls 10 pts below avg entry)
- The engine auto-exits all 3 lots

**Step 4C — Test Squareoff:**
- Set system time past 11:30 AM or wait — the APScheduler job fires the squareoff automatically

---

### 4.6 Read the Dashboard

```
┌─────────────────────────────────────────────────────────┐
│  NIFTY: 24,523.45  ●LIVE  [▶ START] [⏹ STOP] [⚙] [↩]  │
│  ⚠ Paper Trade Mode                                     │
├──────────────────┬──────────────────┬───────────────────┤
│  LEVEL PANEL     │  P&L + TRADES    │  OPEN POSITIONS   │
│                  │                  │                   │
│  R3 ──── 24600  │  TODAY'S P&L     │  CE  NIFTY...PE   │
│  R2 ──── 24550  │  +₹1,500         │  2L  +₹800        │
│  R1 ──── 24500  │                  │                   │
│  ──── NIFTY ─── │  [P&L Chart]     │  KITE STATUS      │
│  S1 ──── 24300  │                  │  ● Auth: ✓        │
│  S2 ──── 24250  │  [Trade Log]     │  ● Feed: ✓        │
│  S3 ──── 24200  │                  │                   │
│                  │                  │  🤖 AI OBSERVER   │
└──────────────────┴──────────────────┴───────────────────┘
```

| Element | Meaning |
|---------|---------|
| **Green level badge** | That level has been triggered (entry placed) |
| **Grey level badge** | Level blocked (target already hit today from this level) |
| **CE state: L2_ENTERED** | CE side is in Level 2 with 2 lots open |
| **PE state: BLOCKED** | PE target was hit — no more PE entries today |
| **+₹1,500** | Today's realized P&L (paper) |
| **↩ (logout icon)** | Logout button — ends your session |

---

### 4.7 Run Tests

To verify everything is working correctly:

```powershell
cd D:\PyramidStreategy\backend
venv\Scripts\activate
pytest tests/ -v
```

Expected output:
```
153 passed in 1.15s
```

All 153 tests cover: strategy rules, time rules, state machine transitions, option selector, Kite service, AI service, Telegram notifications, JWT auth, order manager, and safety checks.

---

## 5. Phase 2 — Live Kite Data Guide

Phase 2 connects to Zerodha's KiteTicker WebSocket to receive real-time NIFTY spot prices and option LTPs. Orders are still simulated (paper trade). This lets you test the strategy with real market prices before going live.

> **Prerequisite:** You need a Zerodha account with Kite Connect API subscription (approx ₹2,000/month).

---

### 5.1 Get Zerodha Kite Connect API Key

1. Log in to [https://developers.kite.trade](https://developers.kite.trade)
2. Click **Create New App**
3. Fill in:
   - **App Name:** PyramidStrategy
   - **Redirect URL:** `http://localhost:8000/auth/kite/callback`
   - **App Type:** Connect
4. After creation, note your:
   - **API Key** (e.g., `abcdef1234567890`)
   - **API Secret** (e.g., `xyzxyzxyz1234567890abcdef`)

---

### 5.2 Save API Credentials in Settings

1. Open the dashboard → click **⚙ Settings**
2. Scroll to the **Zerodha API** section
3. Enter your **API Key** and **API Secret**
4. Click **Save Zerodha Keys**

The keys are stored AES-256-GCM encrypted in the local database. They are never stored in plain text and never sent to any external server.

---

### 5.3 Connect to Kite (OAuth Login)

Every day before trading, you must complete the Kite OAuth flow to get a fresh access token. Kite tokens expire daily at approximately 6:00 AM.

**Steps:**

1. On the dashboard, find the **Zerodha Kite** panel (right side)
2. Click **Login to Kite**
3. A new browser tab opens with the Zerodha login page
4. Enter your Zerodha **client ID** and **password**
5. Complete the **2FA** (TOTP or PIN)
6. Zerodha redirects to: `http://localhost:8000/auth/kite/callback?request_token=...`
7. The backend automatically exchanges the request token for an access token
8. You see: `{"status": "authenticated", "message": "Kite login successful"}`
9. Return to the dashboard — the Kite panel shows **Authenticated ✓**

> [!NOTE]
> **First-Time Authorization (Consent Screen Redirect Error):**
> If you are connecting a new Client ID or API Key for the first time, Zerodha requires manual consent and will render a "Consent" page ("Authorize app to connect?"). This results in a status code `200` instead of a `302` redirect, causing the daily auto-login check to throw an error.
>
> **To bypass this:**
> 1. Copy the login URL: `https://kite.zerodha.com/connect/login?api_key=YOUR_API_KEY&v=3`
> 2. Paste it in a browser window where you are logged in to the target Zerodha account.
> 3. Click the **Authorize** button manually. Once Zerodha records your authorization, future automated daily logins will bypass this consent page.

> **If the redirect page shows an error:** Make sure the backend is running on port 8000 and the Redirect URL in your Kite app settings exactly matches `http://localhost:8000/auth/kite/callback`

---

### 5.4 Start the Live NIFTY Feed

After successful authentication:

1. In the **Zerodha Kite** panel, click **▶ Start Live Feed**
2. The panel updates to show:
   - **WebSocket feed: ●** (green dot = connected)
   - **NIFTY price** in the dashboard header updates in real-time

The KiteTicker WebSocket is now streaming:
- **NSE:NIFTY 50** spot price → drives strategy level detection
- **Option LTPs** → subscribed automatically when you enter a position (for target/SL monitoring)

> **Important:** Do this between **9:00 AM and 9:15 AM** IST, before market movement starts.

---

### 5.5 Load NFO Instruments

The instrument cache maps option symbols (e.g., `NIFTY27JUN2423150PE`) to Kite's internal instrument tokens. This is required for option LTP streaming.

This loads **automatically at 9:00 AM** each day (APScheduler job). If you start the app after 9:00 AM, load it manually:

1. In the Kite panel, click **Load Instruments**
2. Wait 5–10 seconds (downloads ~10,000 NFO instruments)
3. Panel shows **NFO instruments: ●** (green)

---

### 5.6 Verify Live Data is Flowing

Check all systems are green before clicking START:

| Check | Where to see it | Expected |
|-------|----------------|---------|
| Backend running | PowerShell window | No errors |
| NIFTY price live | Dashboard header | Real-time price moving |
| Kite authenticated | Kite panel | Auth token ✓ |
| Ticker connected | Kite panel | WebSocket feed ✓ |
| Instruments loaded | Kite panel | NFO instruments ✓ |
| Paper trade ON | Dashboard banner | ⚠ Paper Trade Mode |
| Strategy levels set | Level Panel | R1–R3 and S1–S3 visible |

When everything is green → click **▶ START**.

---

### 5.7 Daily Reconnect Routine

Kite access tokens expire daily. Follow this routine every morning:

**8:00 AM** — App auto-validates your token and warns if expired  
**8:15 AM** — If expired: click **Login to Kite** → complete login → return to dashboard  
**9:00 AM** — Instruments auto-reload; click **▶ Start Live Feed** if not auto-started  
**9:15 AM** — Set today's R1–R3 and S1–S3 levels in Settings → **Save**  
**9:30 AM** — Market opens. Click **▶ START** when ready  
**11:30 AM** — Positions auto-squared off by the scheduler  
**11:35 AM** — Review trade log and P&L  

---

## 6. Phase 3 — Login, AI Observer & Telegram

Phase 3 adds security (JWT login), intelligence (AI trade observer), and real-time alerts (Telegram). All three are optional enhancements on top of the working strategy engine.

---

### 6.1 Logging In (JWT Authentication)

The dashboard is now protected. When you open `http://localhost:5173` you will see the **Login page**.

**Default credentials:**
- **Username:** `admin`
- **Password:** `pyramid123`

After login, a JWT token is stored in your browser. It expires after **8 hours** — you will be automatically logged out and redirected to the login page at that point.

To **log out** manually, click the **↩** (logout) button in the top-right of the dashboard header.

> **To change the password:** Open `backend/app/api/routes/session.py` and update the `ADMIN_PASSWORD` constant. Then restart the backend.

---

### 6.2 Configure the AI Observer

The AI Observer watches every trade event in real time and provides 2–3 sentence insights. It **never delays or blocks order execution** — it runs asynchronously after each event.

**Supported providers:**

| Provider | Model | Best for |
|----------|-------|---------|
| OpenAI | gpt-4o | General analysis, fast |
| Anthropic | claude-3-5-sonnet | Nuanced market context |
| Google Gemini | gemini-2.5-flash | Alternative perspective |

**Setup steps:**

1. Go to **Settings → AI Observer** section
2. Select your preferred **AI Provider** from the dropdown
3. Paste your **API Key** for that provider
4. Toggle **AI Observer** to **ON**
5. Click **Save AI Settings**
6. Click **Test Connection** — you should see "Connection OK" confirmation

**Where to get API keys:**
- OpenAI: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- Anthropic: [console.anthropic.com](https://console.anthropic.com)
- Google Gemini: [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

API keys are stored AES-256-GCM encrypted. The masked version (e.g., `sk-...xxxx`) is shown in Settings — the full key is never returned to the frontend.

---

### 6.3 Using the AI Observer Panel

The **AI Observer** panel appears on the right side of the dashboard when an AI key is configured.

**When does the AI produce a suggestion?**

| Event | AI trigger |
|-------|-----------|
| Level 1 entry (L1) | "Entry signal observed — provide context" |
| Level 2 add | "Position pyramid at L2 — assess risk" |
| Level 3 add | "Full pyramid at L3, SL now active — assess urgency" |
| Target hit | "Target achieved — post-trade analysis" |
| SL hit | "Stop loss triggered — what went wrong?" |
| Squareoff | "Day-end review" |

Each suggestion appears in the AI Observer panel with a timestamp and the event that triggered it. Suggestions are also persisted to the database — you can review them later via `GET /ai/suggestions` in Swagger.

**Important limitations:**
- The AI is **advisory only** — it cannot trigger, delay, or cancel trades
- Suggestions appear 5–15 seconds after the event (API latency)
- If the AI API key is invalid or the API is down, the strategy continues normally — AI failures are logged but never surface as errors

---

### 6.4 Configure Telegram Notifications

Telegram sends instant alerts to your phone for every trade event. Setup takes about 5 minutes.

**Step 1 — Create a Telegram Bot:**

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name: `PyramidStrategy Alerts`
4. Choose a username: `pyramidstrategy_yourname_bot`
5. BotFather gives you a **bot token**: `123456789:ABCdefGHI...`
6. Copy and save this token

**Step 2 — Get your Chat ID:**

1. Search for **@userinfobot** in Telegram and start it
2. It replies with your **Chat ID** (a number like `987654321`)
3. Alternatively, message your new bot and then visit:
   `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
   Look for `"chat":{"id":987654321}`

**Step 3 — Save in Settings:**

1. Go to **Settings → Telegram** section
2. Paste your **Bot Token**
3. Paste your **Chat ID**
4. Click **Save Telegram**

---

### 6.5 Test Telegram Connection

After saving:

1. Click **Send Test Message**
2. Check your Telegram — you should receive:
   ```
   ✅ PyramidStrategy — Telegram connected successfully!
   ```

If no message arrives within 10 seconds:
- Verify the Bot Token has no extra spaces
- Verify the Chat ID is numeric (no `@` prefix)
- Make sure you have started a conversation with your bot (send it any message first)

**Alert types you will receive:**

| Event | Message format |
|-------|---------------|
| BUY order | 🟢 BUY `NIFTY27JUN2423150PE` \| CE L1 \| 1 Lot @ ₹95.50 |
| Target hit | 🎯 TARGET HIT — CE \| 2 Lots \| +₹3,000 |
| SL hit | 🛑 SL HIT — PE L3 \| 3 Lots \| -₹2,250 |
| Squareoff | ⏰ SQUAREOFF — 11:30 AM \| Total: +₹750 |
| Engine start | ▶️ PyramidStrategy STARTED — 📝 PAPER mode |
| Engine stop | ⏹ PyramidStrategy STOPPED |
| Order failure | ❌ ORDER FAILED — CE L1 BUY |

---

### 6.6 Complete Settings UI Reference

The Settings page (⚙ button) is organized into these sections:

| Section | Fields | Notes |
|---------|--------|-------|
| **Trading Mode** | Paper / Live toggle | Confirm dialog required to switch to Live |
| **Strategy Levels** | R1, R2, R3, S1, S2, S3 | Required before starting engine |
| **Execution** | Lot Size, Target Points, SL Points | Lot size default 75 |
| **Zerodha API** | API Key, API Secret | Encrypted at rest |
| **AI Observer** | Provider, API Key, toggle | Test Connection button |
| **Telegram** | Bot Token, Chat ID | Send Test Message button |

All save operations show a status bar at the bottom of the Settings panel (green = saved, red = error, auto-dismisses after 3 seconds).

---

## 7. Phase 4 — Live Order Execution

Phase 4 enables **real money trading**. The strategy engine places actual MARKET orders on NSE via Kite Connect. Proceed only after thorough paper trading and review.

> ⚠️ **WARNING:** Phase 4 uses real money. Always paper trade for at least 2 weeks before enabling live mode.

---

### 7.1 Enable Live Trading Mode

1. Ensure Kite is authenticated (Section 5.3)
2. Ensure NFO instruments are loaded (Section 5.5)
3. Go to **Settings → Trading Mode**
4. Toggle from **Paper** to **Live**
5. A confirmation dialog appears: *"Switch to LIVE mode? Real orders will be placed."*
6. Click **Confirm**
7. Click **Save Settings**

Alternatively, edit `.env` directly:
```env
PAPER_TRADE=false
```
Then restart the backend.

---

### 7.2 Pre-Flight Safety Checks

When you click **▶ START** in live mode, the system runs automatic safety checks before the engine starts. If any check fails, the engine does NOT start and you see a list of errors.

**Checks performed:**

| Check | Pass condition | On failure |
|-------|---------------|-----------|
| Strategy config | R1–R3 and S1–S3 are set | Error — configure in Settings |
| Time check | Before 11:15 AM IST | Error — too late to start today |
| Kite auth | Valid access token | Error — re-login required |
| Token validity | Token not expired | Error — re-login required |
| Instruments loaded | NFO cache populated | Error — click Load Instruments |
| Account margin | ≥ ₹50,000 available | Error — add funds |
| Existing positions | No open NIFTY options | Warning only — engine still starts |
| KiteTicker connected | WebSocket live | Warning only — feed activates on start |

You can also run checks without starting via **Settings → Run Safety Check** or the API endpoint `GET /strategy/safety-check`.

---

### 7.3 What Happens on Each Trade

**On BUY (entry):**
1. Strategy engine detects NIFTY crosses a level
2. `OrderManager.place_buy_order()` is called
3. A MARKET order is placed: `variety=regular, exchange=NFO, product=MIS` (intraday)
4. System polls Kite every second for up to 15 seconds waiting for fill confirmation
5. When filled, the average fill price is logged to the `trades` table
6. An audit log entry is created
7. Telegram sends a 🟢 BUY alert (if configured)
8. AI Observer analyzes the entry (if configured)

**On EXIT (target/SL/squareoff):**
1. Strategy engine detects target or SL condition
2. A MARKET SELL order is placed immediately
3. System waits up to 15 seconds for fill
4. P&L is calculated: `(exit_price - avg_entry) × qty`
5. Trade record is updated with final status and P&L
6. Telegram sends 🎯/🛑/⏰ alert

**Tuesday expiry rule:**
- On Tuesdays, options are bought on the **next week's Thursday expiry**
- This is automatic — no configuration needed
- The system detects Tuesday and adjusts the instrument symbol accordingly

---

### 7.4 Order Retry and Failure Handling

The order manager has built-in resilience for live trading:

**BUY orders:**
- 3 retry attempts with exponential backoff (0.5s, 1.0s, 1.5s)
- If REJECTED (e.g., insufficient margin): no retry — raises error immediately
- If TIMEOUT (15s poll): retries up to 3 times

**EXIT (SELL) orders:**
- 2 retry attempts maximum (not 3) to prevent double-selling
- If TIMEOUT on EXIT: checks Kite order book for a recent fill before raising error
- If confirmed fill found in order book: uses that fill (no double-sell)
- If order FAILS after all retries: sends ❌ ORDER FAILED Telegram alert

**On order failure:**
- Error is logged to the audit log
- Telegram alert sent immediately
- The strategy engine pauses that side (CE or PE)
- The other side continues operating independently
- **You must manually check and close any open positions in Kite**

---

### 7.5 Going Live — Step-by-Step Checklist

Complete every item before your first live trading day:

**One-time setup:**
- [ ] All 153 tests pass: `pytest tests/ -v`
- [ ] Ran ≥ 10 full paper trade sessions with simulated ticks
- [ ] Ran ≥ 10 paper trade sessions with live Kite prices (Phase 2)
- [ ] Verified 11:30 AM squareoff fires correctly
- [ ] Verified target exit at exactly 20 pts
- [ ] Verified SL exit at exactly 10 pts (L3 only)
- [ ] Verified CE and PE behave independently (one side's exit doesn't affect the other)
- [ ] Telegram alerts tested and working
- [ ] AI Observer tested (optional but recommended)
- [ ] Zerodha account has **min ₹50,000** available margin
- [ ] Kite Connect app has `orders` scope enabled (in Kite developer settings)

**Each trading morning:**
- [ ] Log in to dashboard (admin/pyramid123)
- [ ] Complete Kite OAuth login (fresh token)
- [ ] Click **▶ Start Live Feed** and verify NIFTY price is live
- [ ] Click **Load Instruments** if instruments show as stale
- [ ] Confirm **Paper Trade mode = OFF** (no "⚠ Paper Trade" banner)
- [ ] Set today's R1–R3 and S1–S3 levels in Settings
- [ ] Click **▶ Run Safety Check** — all errors must be zero
- [ ] Click **▶ START** — engine running by 9:15 AM at the latest

---

### 7.6 Daily Live Trading Routine

```
7:30 AM  — Review previous day's P&L and trade log
8:00 AM  — Backend validates Kite token; auto-warns if expired
8:15 AM  — Re-login to Kite if token expired
9:00 AM  — NFO instruments auto-reload
9:05 AM  — Set today's R/S levels (based on your analysis)
9:10 AM  — Click ▶ Start Live Feed
9:12 AM  — Click ▶ Run Safety Check → all green
9:15 AM  — Market opens — click ▶ START
9:15 AM  — Monitor dashboard for first level triggers
11:15 AM — No new entries after this time (auto-enforced)
11:30 AM — All positions auto-squared off (auto-enforced)
11:35 AM — Review trade log, P&L, and AI Observer summary
11:40 AM — Click ⏹ STOP to idle the engine
```

---

## 8. Strategy Rules Reference

These are hard-coded and cannot be changed from Settings:

| Rule | Description |
|------|-------------|
| **Strike Lock** | Strike selected at L1 entry is used for L2 and L3 — never changes |
| **Nearest Thursday expiry** | On all days except Tuesday, options use the nearest upcoming Thursday expiry |
| **Tuesday Rule** | On Tuesdays, use NEXT week's Thursday expiry (avoids theta decay on 2-day contract) |
| **Max 3 lots** | Maximum 3 lots total per side (CE or PE) — never exceeded |
| **Target = 20 pts** | Exit ALL lots when option gains 20 pts above average entry |
| **SL = 10 pts at L3 only** | Stop loss only activates at Level 3 — no SL at L1 or L2 |
| **Exit = MARKET order** | All exits use MARKET orders for speed (no LIMIT orders ever) |
| **No entry after 11:15 AM** | Entry blocked at or after 11:15 AM IST |
| **Squareoff at 11:30 AM** | All open positions force-closed at 11:30 AM IST |
| **No re-entry same level** | After target at L1, that level is blocked for rest of day |
| **CE/PE independent** | CE and PE sides run simultaneously, never affecting each other |
| **New cycle after target** | If NIFTY reaches next level after a target, a NEW cycle starts from 1 lot |

---

## 9. Dashboard Walkthrough

### Header Bar
- **NIFTY Price** — real-time spot price (Phase 2+) or last simulated tick (Phase 1)
- **● LIVE / ● MOCK** — green = live Kite feed, orange = mock/paper mode
- **▶ START / ⏹ STOP** — master engine control
- **⚙ Settings** — configure levels and API keys
- **↩** — logout button (clears JWT session)

### Left Panel — Level Panel
Shows R1, R2, R3 (red, bearish) and S1, S2, S3 (green, bullish) levels.

Each level badge shows one of:
- **WAITING** (grey) — level not yet reached
- **ACTIVE** (yellow pulse) — position open at this level
- **DONE** (green checkmark) — target achieved, level blocked
- **BLOCKED** (grey lock) — no more entries from this level today

### Center Panel — P&L and Trades
- **Today's P&L** — cumulative realized P&L for the day
- **P&L Chart** — intraday P&L curve (updates after each exit)
- **Trade Log** — every BUY and EXIT with time, side, level, price, lots, P&L

### Right Panel — Positions, Kite, AI
- **Open Positions** — currently held CE and PE positions with unrealized P&L
- **Kite Status** — connection health (auth, ticker, instruments)
- **AI Observer** — AI-generated trade insights (when AI key is configured)

### AI Observer Panel
- Shows the most recent AI suggestion at the top (blue border = just generated)
- Older suggestions shown below in chronological order
- Each entry shows: event type, side, NIFTY level, provider, timestamp
- Panel auto-refreshes every 15 seconds

---

## 10. Common Errors & Fixes

### Backend won't start

**Error:** `ENCRYPTION_KEY must be exactly 32 bytes`  
**Fix:** Open `.env` and make your `ENCRYPTION_KEY` exactly 32 characters long.

**Error:** `ModuleNotFoundError: No module named 'fastapi'`  
**Fix:** You forgot to activate the virtual environment. Run `venv\Scripts\activate` first.

---

### Frontend won't load

**Error:** Blank page or `Failed to fetch`  
**Fix:** Make sure the backend is running on port 8000. Check `VITE_API_BASE_URL=http://localhost:8000` in `frontend/.env` (create if missing).

**Error:** Stuck on Login page after entering correct password  
**Fix:** Check browser console for CORS errors. Ensure backend is running and `VITE_API_BASE_URL` is correct.

---

### Login issues (Phase 3)

**Error:** "Invalid credentials" with admin/pyramid123  
**Fix:** Make sure the backend has restarted after the latest code update. The JWT auth was added in Phase 3.

**Error:** Logged out unexpectedly  
**Fix:** JWT tokens expire after 8 hours. Log in again. This is expected behavior.

---

### Kite login fails

**Error:** `Zerodha API key/secret not configured`  
**Fix:** Go to Settings, save your API Key and Secret, then try Login again.

**Error:** Callback page shows `Invalid request_token`  
**Fix:** Tokens are single-use. If you refreshed the callback page, go back and re-login via **Login to Kite** button.

**Error:** Redirect to callback shows "Site can't be reached"  
**Fix:** Your backend is not running or is on a different port. Ensure `uvicorn` is running on port 8000.

---

### NIFTY price not updating (Phase 2+)

**Check 1:** Is the Kite panel showing **WebSocket feed ✓**?  
**Check 2:** Did the ticker disconnect? Click **Start Live Feed** again.  
**Check 3:** Has your access token expired? Click **Validate Token** — if expired, re-login.

---

### Strategy not triggering at levels

**Check 1:** Is the engine status **RUNNING**? Click ▶ START.  
**Check 2:** Are levels saved? Open Settings and verify R1–R3, S1–S3 are set.  
**Check 3:** Is it past 11:15 AM IST? No new entries are allowed after that.  
**Check 4:** Was that level already hit today (badge shows BLOCKED)?

---

### Safety checks failing (Phase 4)

**"Cannot start after 11:15 AM IST"** — Today's trading window has closed. Start the engine before 11:15 AM tomorrow.

**"Kite not authenticated"** — Complete the OAuth login (Section 5.3).

**"NFO instruments not loaded"** — Click **Load Instruments** in the Kite panel.

**"Insufficient margin: ₹X available, ₹50,000 required"** — Add funds to your Zerodha account.

---

### AI Observer not showing suggestions

**Check 1:** Is the AI API key saved and valid? Click **Test Connection** in Settings.  
**Check 2:** Is the AI Observer toggle **ON**?  
**Check 3:** Has a trade event occurred? AI only fires after entries, exits, SL, or squareoff.  
**Check 4:** Check backend logs for errors like `AI call failed (openai): ...`

---

### Telegram alerts not arriving

**Check 1:** Click **Send Test Message** in Settings — if this fails, the token or chat ID is wrong.  
**Check 2:** Have you started a conversation with your bot in Telegram? Send it a `/start` message.  
**Check 3:** Verify the Bot Token format: `123456789:ABCdef...` (number:letters)  
**Check 4:** Check backend logs for `Telegram notification failed: ...`

---

### Order rejected in live mode (Phase 4)

**Telegram alert:** ❌ ORDER FAILED — CE L1 BUY  
**Immediate action:**
1. Open Zerodha Kite app on your phone
2. Check **Positions** — verify the position was not opened
3. If open position exists, close it manually
4. Check the error reason in the backend logs
5. Common causes: insufficient margin, market closed, wrong instrument symbol

---

### Tests failing

```powershell
cd D:\PyramidStreategy\backend
venv\Scripts\activate
pytest tests/ -v --tb=short
```

If you see import errors, re-run `pip install -r requirements.txt`.

Expected: **153 passed**

---

## 11. Safety Checklist Before Live Trading

**Phase 4 is now fully implemented.** Complete all items before enabling `PAPER_TRADE=false`.

### One-Time Verification
- [ ] All 153 tests pass: `pytest tests/ -v`
- [ ] Ran ≥ 10 paper trade sessions with simulated ticks (Phase 1)
- [ ] Ran ≥ 10 paper trade sessions with live Kite prices (Phase 2)
- [ ] Verified 11:30 AM squareoff triggers correctly
- [ ] Verified target exit works at exactly 20 pts
- [ ] Verified SL exit works at exactly 10 pts (at L3 only, not L1/L2)
- [ ] Verified CE and PE behave independently (different strikes, independent exits)
- [ ] Verified the Tuesday expiry rule (next Thursday, not same-day)
- [ ] Verified level blocking works (no re-entry after target on same level)
- [ ] Tested Telegram alerts — all message types received correctly
- [ ] Tested AI Observer — suggestions appear after trade events

### Account Preparation
- [ ] Zerodha account has minimum ₹50,000 available margin
- [ ] Kite Connect API subscription is active
- [ ] Kite app has `orders` scope enabled in developer settings
- [ ] Tested token expiry recovery — re-login and strategy resumes correctly

### Risk Awareness

> **Maximum daily risk calculation:**
> - SL at L3 = 10 pts × 3 lots × 75 qty = **₹2,250 per side**
> - Both CE and PE can hit SL on the same day = **₹4,500 maximum daily loss**
> - Plus brokerage/taxes (approx ₹200–500 per day of active trading)

> **The system cannot lose more than ₹4,500 in a single day** because:
> - Max 3 lots per side (hard limit in state machine)
> - SL of 10 pts enforced by order manager
> - 11:30 AM squareoff closes everything regardless

---

## 12. How to Run Using Docker

You can run the entire PyramidStrategy platform (React frontend, FastAPI backend, PostgreSQL database, and Redis cache) inside Docker containers. This is the recommended approach for deploying on a **VPS** (e.g., Ubuntu server) or running the complete environment locally without manual Python/Node setups.

### 12.1 Prerequisites
Make sure you have Docker and Docker Compose installed on your host system:
* **Windows/Mac:** Install [Docker Desktop](https://www.docker.com/products/docker-desktop/).
* **Ubuntu/Linux VPS:** Install Docker using the terminal:
  ```bash
  sudo apt update && sudo apt install docker.io docker-compose-v2 -y
  sudo systemctl enable --now docker
  ```

### 12.2 Clone and Setup
1. Clone the repository on your server:
   ```bash
   git clone https://github.com/nextginfosoft/PyramidStrategy.git
   cd PyramidStrategy
   ```

2. **Configure your Domain or VPS IP Address in `docker-compose.yml`** (so the frontend browser knows where to send API requests):
   * By default, `docker-compose.yml` is configured to use the domain **`pyramid.nextginfosoft.com`** with secure SSL/TLS.
   * If you need to change this to a different domain or a raw IP address:
     * **Option A (Automated command):** Run these commands (replace `your_domain.com` with your actual domain or IP):
       ```bash
       sed -i 's|VITE_API_BASE_URL=https://pyramid.nextginfosoft.com/api|VITE_API_BASE_URL=https://your_domain.com/api|g' docker-compose.yml
       sed -i 's|VITE_WS_URL=wss://pyramid.nextginfosoft.com/ws|VITE_WS_URL=wss://your_domain.com/ws|g' docker-compose.yml
       ```
     * **Option B (Manual edit):** Open `docker-compose.yml` in a text editor (e.g., `nano docker-compose.yml`) and update the `frontend` build arguments:
       ```yaml
       args:
         - VITE_API_BASE_URL=https://your_domain.com/api
         - VITE_WS_URL=wss://your_domain.com/ws
       ```

### 12.3 Spin Up the Services
Run the following command in the root folder (where `docker-compose.yml` resides) to build and run all services in the background:
```bash
sudo docker compose up -d --build
```
This builds and connects:
* **Frontend:** Serves Vite React static assets via Nginx on port `80`.
* **Backend:** Runs FastAPI inside a Docker container on port `8000`.
* **PostgreSQL:** Starts database container on port `5432` with persistent volume (`postgres_data`).
* **Redis:** Starts Redis container on port `6379`.

### 12.4 Verification & Updates
* Open your browser and go to your VPS IP: `http://your_vps_ip` (port 80).
* To update the system when you push changes to GitHub:
  ```bash
  git pull
  sudo docker compose up -d --build
  ```

---

*PyramidStrategy v1.0 — All Phases Complete*  
*Built by Santosh Kumar | nextginfosoft*  
*Phase 1 (Paper) · Phase 2 (Live Data) · Phase 3 (AI + Alerts) · Phase 4 (Live Orders)*
