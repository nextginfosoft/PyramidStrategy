# PyramidStrategy — Improvement Roadmap

> All improvements must respect the core strategy rules defined in CLAUDE.md.  
> Enhancements ADD capability — they never modify the pyramid logic.

---

## NEAR-TERM (Post Phase 4 — Month 2-3)

### R1: Multi-Instrument Support
**Priority:** High  
**Why:** Strategy logic is instrument-agnostic. Extending to BANKNIFTY doubles opportunity.

- Add BANKNIFTY support (lot size = 35, different ATM calculation)
- Per-instrument configuration: separate R/S levels for NIFTY and BANKNIFTY
- Separate P&L tracking per instrument
- UI: instrument selector tab on dashboard

### R2: Historical Backtesting Module
**Priority:** High  
**Why:** Before trusting any configuration change, backtest it on historical data.

- Download historical NIFTY minute-by-minute data via Kite Historical API
- Replay entire day's data through strategy engine
- Compute P&L for any given R/S level configuration
- Backtest UI: date range picker + level inputs → P&L report
- Strategy statistics: win rate, average profit, average loss, max drawdown
- Compare configurations side-by-side

### R3: Enhanced AI Analysis
**Priority:** Medium  
**Why:** Current AI is reactive (post-event). Proactive AI adds real value.

- Pre-market AI brief: VIX analysis, expected range, level quality assessment
- AI suggests optimal R/S level configuration based on historical data + current VIX
- AI post-session review: what worked, what didn't, patterns observed
- AI-powered "level quality score" — how well are the levels spaced for current volatility
- Note: AI remains ADVISORY — never auto-executes or overrides strategy rules

### R4: P&L Analytics Dashboard
**Priority:** Medium  
**Why:** Track strategy performance over time to build confidence and identify issues.

- Weekly/monthly P&L charts
- Trade statistics: win rate by level (R1 vs R2 vs R3), best times of day
- Drawdown chart
- Calendar heatmap (green/red days)
- Export to CSV/Excel

### R5: Smart Level Suggestion
**Priority:** Medium  
**Why:** Choosing optimal R/S levels is the hardest part of the strategy.

- Analyze prior 5-day price action to suggest levels
- Use LuxAlgo-style support/resistance detection algorithm
- Show suggested levels alongside manual input in Settings
- User retains full control — suggestions are advisory only

### R21: Global Strategy Configuration / Level Synchronization
**Priority:** High  
**Why:** Allow an administrator or master account to set Nifty Support/Resistance levels once and have them automatically propagate to all active user engines with their respective Zerodha accounts.

- Implement a global configuration database table (`global_strategy_config`) to decouple pricing levels from user identities.
- Create an administrative interface/API to update levels globally.
- Automatically hot-reload levels in all running `StrategyEngine` instances in the `EngineManager` when updated.
- Retain user-specific settings (like lot size and paper trade mode) separately.

---

## MID-TERM (Month 4-6)

### R6: Options Greeks Display
**Priority:** Medium  
**Why:** IV crush and theta decay are key risks for this strategy (intraday options).

- Show Delta, Gamma, Theta, Vega for open positions
- IV percentile indicator (high IV = unfavorable for buying options)
- Theta decay rate display — especially critical after 10:30 AM
- Greeks sourced from Kite option chain data

### R7: Paper Trade vs Live Comparison
**Priority:** Low-Medium  
**Why:** Validate that paper trade results match live results (slippage analysis).

- Run both modes simultaneously (paper trade shadow alongside live)
- Compare fill prices: paper vs actual
- Slippage report: average slippage per trade, worst case
- Use insights to improve order timing

### R8: Mobile-Responsive PWA
**Priority:** Medium  
**Why:** Santosh needs to monitor trades from mobile during market hours.

- Progressive Web App (PWA) configuration
- Mobile-optimized dashboard layout
- Push notifications via browser for trade events
- Quick action buttons: Pause strategy, Force squareoff
- Offline mode: show last known state when connection drops

### R9: Multi-User / Team Support
**Priority:** Low  
**Why:** Future — share the system with trusted colleagues or mentees.

- User roles: Admin (full access), Viewer (read-only), Operator (can start/stop, no settings)
- Per-user audit log: who changed what
- Shared dashboard with role-gated controls

### R10: Webhook / Alert API
**Priority:** Low-Medium  
**Why:** Enable integration with external tools.

- `POST /webhooks/trade-event` → fire on any trade event
- Configurable payload format
- Support Discord, Slack, custom URLs
- Webhook security: HMAC signature verification

### R16: Interactive Telegram Bot Commands
**Priority:** Medium  
**Why:** Enable two-way remote strategy management without needing the dashboard open.

- Set up a secure bot webhook listener (e.g. `POST /telegram/webhook`).
- Expose basic controls via custom inline keyboard buttons (Start engine, Stop engine, Status).
- Query current positions, active levels, and live P&L in real-time.

### R17: Granular Notification Filters
**Priority:** Low-Medium  
**Why:** Avoid alert noise on high-frequency channels (like WhatsApp) while keeping full logging on Telegram.

- Add per-channel configuration checkboxes in settings.
- Selectively enable/disable alerts for: Entries, Exits, Safety Cutoffs, and Daily PDF Reports independently per integration.

### R18: Auto-reconnect & Self-healing Websockets
**Priority:** High  
**Why:** Prevent live feed interruption and missing critical level ticks during trading hours.

- Implement a background ping/pong monitor for the Zerodha WebSocket feed.
- Automatic re-authentication flow using stored API key and TOTP seed on connection drops.
- Queue pending orders or retry state reconciliation to avoid sync mismatches.

---

## LONG-TERM (Month 6-12)

### R11: Strategy Variant Engine
**Priority:** Medium (future startup feature)  
**Why:** The core logic can be generalized to support variant strategies.

- Allow configuring different target/SL per level (currently fixed at 20/10)
- Allow configuring lot progression (currently 1:1:1 — could be 1:2:3)
- Named strategy presets (save/load different configurations)
- A/B test different configurations using backtesting
- Important: variants must still respect ALL general rules in CLAUDE.md

### R12: Pre-Market Intelligence Brief
**Priority:** High (strategic differentiator)  
**Why:** Automate the hardest manual task — delivering reasoned, OI-backed S/R levels before market open so the user approves rather than guesses.

- Runs automatically at 8:45 AM IST via APScheduler before every trading session
- Fetches live OI snapshot from Kite option chain — extracts max pain, PCR, top CE walls (resistance) and PE walls (support)
- Pulls previous session OHLCV from Kite historical API — uses prior high/low/close as pivot anchors
- Incorporates Gift Nifty indicated open for gap-up/gap-down bias and India VIX for volatility-adjusted band widening
- LLM (Claude/Gemini) synthesizes all inputs and suggests R1/R2/R3 and S1/S2/S3 with a plain-English reason and HIGH/MEDIUM/LOW confidence score per level
- Brief delivered via Telegram alert and Dashboard update by 9:00 AM IST
- User reviews suggested levels → clicks Approve → strategy arms automatically with AI-suggested levels
- Every level is verifiable on NSE option chain or Sensibull — fully explainable, no black box

### R13: SaaS Productization
**Priority:** High (startup vision)  
**Why:** Turn PyramidStrategy into a product for other NIFTY traders.

- Multi-tenant architecture (each user has isolated strategy state)
- Subscription tiers: Free (paper trade only), Pro (live trading), Enterprise (multi-instrument)
- Onboarding flow: connect Zerodha → configure levels → start paper trading
- Billing: Razorpay integration
- Landing page with strategy explainer
- Compliance: clearly state "not SEBI registered, not investment advice"

### R14: Strategy Performance Attribution
**Priority:** Medium  
**Why:** Understand which market conditions the strategy performs best in.

- Tag each trading day with market regime (trending, sideways, volatile)
- Correlate P&L with VIX, NIFTY range of day, day of week
- Report: "Strategy works best on days when NIFTY range > 150 pts"
- Use findings to add optional "market filter" rule in settings

### R15: Automated Daily Reporting
**Priority:** Medium  
**Why:** Track long-term performance without manual work.

- EOD report auto-generated at 3:30 PM
- Content: day's trades, P&L, strategy decisions, AI observations
- Format: PDF report or Telegram message
- Weekly summary: Monday briefing with prior week stats

### R19: Expiry Day Strike Roll-Over (Next-Week Expiry Toggle)
**Priority:** High  
**Why:** Prevent theta decay risk and high intraday option volatility on expiry Tuesdays.

- Add a settings toggle to roll over expiry contracts after a custom time (e.g. 10:30 AM).
- If enabled, the engine selects the next week's option strike contracts instead of the current day's expiring contracts on Tuesdays.

### R20: Multi-Account Trade Copier
**Priority:** Medium-High  
**Why:** Replicate trading strategy signals across multiple client accounts concurrently.

- Expose multi-account credential inputs in the Settings page.
- Distribute strategy buy and exit orders to all active accounts with customizable lot size multipliers.

### R21: Live Slippage & Latency Auditing
**Priority:** Low-Medium  
**Why:** Audit and log Zerodha execution efficiency and actual pricing slippage.

- Track differences between level crossing time, request dispatch, and final trade execution fill timestamp.
- Present a latency statistics card and raw tick slippage log on the frontend.

---

## TECHNICAL DEBT & INFRASTRUCTURE

### T1: Containerized Deployment (Docker)
- Dockerfile for backend + frontend
- `docker-compose.prod.yml` for production deployment
- One-command deploy: `docker-compose up -d`

### T2: CI/CD Pipeline
- GitHub Actions workflow
- Auto-run strategy engine unit tests on every push
- Block merge if strategy tests fail
- Auto-deploy to VPS on main branch push

### T3: Database Query Optimization
- Add indexes on `trades(trade_date, side, status)`
- Partition `trades` table by month for performance
- Connection pooling via PgBouncer for high-frequency reads

### T4: Strategy Engine Performance Testing
- Load test: simulate 1000 ticks/second through strategy engine
- Measure: latency from tick received → order placed
- Target: < 200ms end-to-end (currently target: 500ms)

### T5: Comprehensive Error Recovery
- Retry logic for Kite API errors (transient network issues)
- Dead letter queue for failed order notifications
- Manual override UI: force-exit positions from dashboard

### T6: Automated Desktop Release Pipeline (GitHub Actions)
- Configured GitHub Actions workflow triggered on version tag pushes (`v*`).
- Compiles the React frontend production assets automatically.
- Runs PyInstaller inside a Windows runner to compile `PyramidStrategy.exe`.
- Compresses the output into a `.zip` file and attaches it as a download to the GitHub Release.

### T7: Desktop License & Activation Key System
- Add offline (cryptographic signatures) or online (SaaS API) license key verification.
- Local hardware fingerprinting using WMI/BIOS serial number hash checks.
- Build a FastAPI licensing check middleware that blocks strategy execution if the license is inactive or expired.
- Isolate the licensing system so it only runs when packaged as an executable (`sys.frozen` is True), leaving VPS/Cloud deployments completely unaffected.
- Add an activation key prompt/unlock page in the React UI.

---

## IMPROVEMENT PRIORITY MATRIX

| Item | Impact | Effort | Priority |
|------|--------|--------|----------|
| R1: BANKNIFTY support | High | Low | ⭐⭐⭐ |
| R2: Backtesting | High | Medium | ⭐⭐⭐ |
| R5: Smart Level Suggestion | High | Medium | ⭐⭐⭐ |
| R4: P&L Analytics | Medium | Low | ⭐⭐⭐ |
| R3: Enhanced AI | Medium | Medium | ⭐⭐ |
| R8: Mobile PWA | Medium | Medium | ⭐⭐ |
| R12: AI Level Detection | Very High | High | ⭐⭐ (post MVP) |
| R13: SaaS | Very High | Very High | ⭐ (startup phase) |
| R6: Greeks display | Low | Low | ⭐⭐ |
| R16: Interactive Bot | Medium | Medium | ⭐⭐ |
| R17: Notification Filters | Low | Low | ⭐⭐ |
| R18: Auto-reconnect | High | Medium | ⭐⭐⭐ |
| R19: Expiry Roll-over | High | Medium | ⭐⭐⭐ |
| R20: Multi-Account Copier | High | High | ⭐⭐ |
| R21: Slippage Auditing | Medium | Low | ⭐⭐ |
| T1: Docker deploy | High | Low | ⭐⭐⭐ |
| T2: CI/CD | Medium | Low | ⭐⭐ |
| T6: Desktop Release Pipeline | High | Low | Completed ⭐⭐⭐ |
| T7: Desktop Licensing System | High | Medium | Future ⭐⭐ |

---

## WHAT WILL NEVER CHANGE (Core Constraints)

These items are frozen — no roadmap item should ever modify them:

1. ✅ PyramidStrategy pyramid logic (3 levels, 1:1:1 lots)
2. ✅ 20-point target rule
3. ✅ 10-point SL only at Level 3
4. ✅ 11:30 AM squareoff deadline
5. ✅ Tuesday expiry rule
6. ✅ Strike locking after Level 1
7. ✅ No re-entry after target at same level

Any future features must work WITH these rules, never around them.
