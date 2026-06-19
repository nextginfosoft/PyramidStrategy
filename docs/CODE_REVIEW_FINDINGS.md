# PyramidStrategy — Code Review & Improvement Suggestions

Read-only review. No source files were modified. Findings are grouped by severity/area; each includes file/line refs so you can act on them yourself.

---

## 1. Critical — Functional gaps (docs say it works, code doesn't)

**1.1 Telegram trade alerts are never sent.**
`notification.py` has fully-implemented `notify_trade_entry`, `notify_target_hit`, `notify_sl_hit`, `notify_squareoff`, `notify_error`. None of them are called from `strategy_engine.py` or `order_manager.py` — grep across the codebase confirms zero call sites outside `notification.py` itself. The Telegram section in `USER_GUIDE.md` (which I wrote last session based on the service existing) overstates what currently fires in practice. Only the `/notifications/test` manual button actually sends a message.
→ Fix direction: call the relevant `notify_*` via `get_user_notification_service(self.user_id)` at the same points `_notify_ai` is called in `strategy_engine.py`, and in `order_manager._alert_order_failure`.

**1.2 `order_manager.py::_alert_order_failure` (lines 320–329) is a no-op.**
It imports `NotificationService` but never instantiates or calls it — just logs and returns. Order failures (rejected orders, exit timeouts) currently raise `OrderError` and log to file, but the user gets no out-of-band alert, which is the one moment they most need to be notified.

**1.3 AI Observer is single-tenant in the one place that matters.**
`strategy_engine.py::_notify_ai` does `from app.services.ai_service import ai_service` — the module-level singleton hardcoded to `user_id=1` — instead of `get_user_ai_service(self.user_id)`. Every other route (`api/routes/ai.py`, `api/routes/config.py`) correctly uses the per-user factory. In a multi-user deployment, every user's live trade events get analyzed under User 1's AI provider config/API key, and `get_today_suggestions` for user 2+ would show nothing despite the engine running fine. If you're currently single-user this is dormant, but it'll bite the moment a second account trades.

---

## 2. Security

**2.1 Hardcoded production secrets committed in `docker-compose.yml`.**
`SECRET_KEY=prod-secret-key-change-this-in-env`, `ENCRYPTION_KEY=prod-encryption-key-32-chars!!`, and Postgres password `password` are checked into the compose file in plaintext. Anyone with repo access (or anyone who finds this repo if it's ever made public/forked) has the JWT signing key and the AES key protecting every user's broker API keys. Same insecure-default pattern exists in `config.py` (`SECRET_KEY = "dev-secret-key-change-in-production"`, `ENCRYPTION_KEY = "dev-encryption-key-32-bytes!!!!"`) with no startup check that rejects these defaults in `APP_ENV=production`.

**2.2 Unauthenticated Kite OAuth callback.**
`auth.py::kite_callback` (no `require_auth` dependency) defaults `user_id` to "first user in DB or 1" if not explicitly passed. Anyone who can hit the callback URL (it's also aliased at 4 different paths in `main.py`) with a valid-looking `request_token` could potentially attach a Kite session to the wrong account, or at minimum the endpoint has no proof the caller is the logged-in user initiating that OAuth flow.

**2.3 No rate limiting on `/session/login` or `/session/register`.**
Both are open to brute-force/credential-stuffing with no lockout, throttle, or CAPTCHA.

**2.4 JWT stored in `localStorage`, sent as a WS query param.**
`localStorage` is readable by any injected script (XSS risk — there's no CSP visible in `main.py`'s middleware stack). Putting the JWT in the WebSocket URL (`/ws?token=...`) also means it can land in server access logs, proxy logs, and browser history. An httpOnly cookie (with CSRF protection) or at minimum sending the token as a WS subprotocol/first-message rather than a query param would reduce exposure.

**2.5 `encryption.py::_get_key()` derives the AES key by truncating/padding the raw `ENCRYPTION_KEY` string** rather than running it through a KDF (PBKDF2/HKDF). Functionally fine if the key truly is 32 random bytes, but combined with 2.1's hardcoded default, it's a weak link.

**2.6 `/strategy/simulate-tick` has no environment gate.** Any authenticated user can POST an arbitrary NIFTY price directly into their own *live* (non-paper) engine, which will act on it for real order placement. This is presumably meant as a testing/demo endpoint — worth restricting to `paper_trade` mode or `is_development`.

**2.7 `pyramidstrategy.db` sits untracked at repo root** (confirmed via `git status` — currently untracked, not committed). It's covered by `.gitignore`'s `backend/pyramidstrategy.db` rule but *not* by a bare `*.db` rule, so if anyone ever runs the app from repo root instead of `backend/`, the DB (containing encrypted API keys, password hashes, trade history) could get committed by accident. Tighten the `.gitignore` pattern to `*.db` or `**/*.db`.

**2.8 `/session/logout` is client-side only** — no server-side token blacklist/revocation. A stolen JWT remains valid for its full 8-hour life even after "logout."

---

## 3. Architecture / Multi-user correctness

**3.1 No persistence of in-memory state machine state across restarts.** `engine_manager.py`'s `_engines: dict[int, StrategyEngine]` is purely in-process. A backend restart (deploy, crash, OOM) mid-trading-day loses `StateMachine.state`, `locked_strike`, `entry_avg_price`, `blocked_levels`, `realized_pnl` for every running user — even though the underlying `Trade`/`AuditLog` rows are durably in the DB. Recovery would require re-deriving state from today's `Trade` rows on startup; currently there's no such reconciliation step.

**3.2 `OrderManager.__init__` defaults `user_id: int = 1`.** Consistent with the `ai_service` singleton bug in 1.3 — another spot where the "default to user 1" pattern could silently misattribute orders if a call site forgets to pass `user_id` explicitly.

**3.3 `trades.py::/export` exit-matching is O(n²)** (scans all exits per entry trade) — fine at today's volume, but will degrade as `trade_date`-scoped history grows; an index-assisted join or single grouped query would scale better.

---

## 4. Testing

**4.1 168 tests collected total** (verified via `pytest --collect-only`), distributed: `test_phase3.py` 42, `test_kite_service.py` 31, `test_state_machine.py` 27, `test_time_rules.py` 21, `test_phase4.py` 19, `test_option_selector.py` 15, `test_trades.py` 10, **`test_strategy_engine.py` only 3.**
`strategy_engine.py` is the actual orchestration core (425 lines: tick routing, level crossing, cooldown, entry/exit execution, force-squareoff) and has the thinnest test coverage of any module relative to its complexity and blast radius. Worth adding coverage for: SL/target hit paths, the `asyncio.gather(... return_exceptions=True)` behavior when one side's processing throws, and `_force_squareoff` under partial-failure (one side's exit order fails).

**4.2 No tests for `api/routes/*.py` auth boundaries** beyond what `test_phase3.py`/`test_phase4.py` cover incidentally — e.g., nothing explicitly verifies the unauthenticated `kite_callback` behavior (2.2) or that `/strategy/simulate-tick` is reachable in live mode (2.6). These are exactly the kind of gap that regresses silently.

**4.3 No CI workflow.** `.github/` contains only `copilot-instructions.md` — no GitHub Actions workflow runs the test suite, linter, or build on push/PR. The 168 tests only run when someone remembers to run them locally.

**4.4 `frontend/package.json` defines `"lint": "eslint . --ext ts,tsx"` but `eslint` is not listed in `devDependencies`.** Running `npm run lint` on a fresh clone will fail until `eslint` (plus the TS/React plugin set) is installed and added to `package.json`.

---

## 5. Frontend

**5.1 `strategyStore.ts::handleWSMessage`** has a `trade_event` branch that's an empty comment (`// Refresh trades list via react-query instead`) — the WS message arrives but does nothing; if a query invalidation was intended, it isn't wired up, so the trade log likely lags until the next poll/manual refresh.

**5.2 `useWebSocket.ts` reconnect has no backoff or cap** — fixed 3-second retry forever. Fine for a personal trading app, but if the backend is down for an extended period this is a steady drip of failed connection attempts; an exponential backoff (capped at, say, 30s) is kinder to both client and server.

**5.3 No visible error boundary or global Axios interceptor for 401s.** A few places catch `err?.response?.data?.detail` ad hoc (e.g., `Login.tsx`), but there's no central interceptor to catch an expired JWT (401) and force re-login app-wide — each component would need its own handling, which is easy to miss on a new screen.

---

## 6. Operational / deployment

**6.1 Root-level stray `package.json`** contains just `{"dependencies": {"playwright": "^1.60.0"}}` — separate from `frontend/package.json`'s own `playwright` devDependency. Unclear if this is leftover scaffolding or intentional (e.g., for repo-root e2e scripts); worth confirming it's needed, otherwise remove to avoid two `node_modules` trees.

**6.2 `docker-compose.yml`'s Postgres has no resource limits / health checks**, and `backend`/`frontend` depend_on `db`/`redis` without `condition: service_healthy`, so on a cold `docker-compose up` the backend may attempt to connect before Postgres finishes initializing.

**6.3 No backup strategy visible for the Postgres volume** (`postgres_data`) — trade history and audit logs are the system's financial record; worth at minimum documenting a pg_dump cron or volume snapshot policy.

---

## Suggested priority order

1. Wire up Telegram alerts for trade events + order failures (1.1, 1.2) — currently the biggest gap between what's documented and what actually happens.
2. Fix the AI Observer / OrderManager `user_id` defaults (1.3, 3.2) before onboarding a second user.
3. Remove hardcoded secrets from `docker-compose.yml`, add a startup guard that refuses to boot with default `SECRET_KEY`/`ENCRYPTION_KEY` in production (2.1).
4. Gate `/strategy/simulate-tick` and add `require_auth` consistency to the Kite callback (2.6, 2.2).
5. Add a CI workflow running `pytest` + `eslint` (after fixing the missing eslint devDependency) on every PR (4.3, 4.4).
6. Expand `test_strategy_engine.py` coverage (4.1) and design a state-recovery path for restarts (3.1).

---

## 7. UI / UX (frontend)

**7.1 No responsive layout — desktop-only.** `Dashboard.tsx` is a hardcoded `grid-cols-12` (3/5/4 split) with exactly one Tailwind breakpoint prefix (`sm:`/`md:`/`lg:`) anywhere in the whole `src` tree. On a tablet or phone the three columns squeeze into unreadable slivers rather than stacking. If you ever want to check P&L from your phone, this needs `grid-cols-1 md:grid-cols-12` style stacking plus a mobile-first pass on `Settings.tsx`'s tab layout and `LiveLogModal.tsx`.

**7.2 Zero accessibility attributes.** A repo-wide search for `aria-` / `role=` returns nothing. Icon-only or emoji-only buttons (⏹ STOP, ⚙ Settings, ⇥ Logout, 📥 Export CSV) have no `aria-label`, inputs like the "SIMULATE TICK" price field have no associated `<label>`, and the Settings/LiveLog modals don't trap focus or restore it on close. Low effort, high value fixes: `aria-label` on icon buttons, `role="dialog"` + `aria-modal="true"` + focus trap on the two modals, and `<label htmlFor>` on form inputs.

**7.3 Browser-native `alert()`/`confirm()` break the dark theme and block the UI thread.** `Dashboard.tsx` uses `alert()` for CSV/log export failures (lines 44, 65); `Settings.tsx` uses `window.confirm()` to gate the LIVE-mode switch (line 272) — arguably the single most consequential click in the whole app, currently protected by a stock browser dialog that's trivially click-through and provides no extra context (margin available, current time-cutoff, etc.). Both should become in-app toast/modal components consistent with the existing `StatusMsg` pattern already used elsewhere in `Settings.tsx`.

**7.4 No loading/empty/skeleton states for the main numbers.** NIFTY LTP and P&L render as a bare `—` while `status`/`pnl` are still `null` (Dashboard.tsx lines 116-117, 205) — indistinguishable from "no data because the engine is down" vs. "still loading after refresh." A skeleton pulse or distinct "loading…" label would remove that ambiguity, especially since these query intervals are 3s and a slow first load is common.

**7.5 The safety-check error banner concatenates everything into one paragraph.** `startMut.isError` block (Dashboard.tsx lines 165-183) joins all failed safety checks with `; ` into a single centered line. With 2-3 simultaneous failures (e.g., margin + instruments + time cutoff) this becomes a hard-to-scan run-on sentence right when the user most needs clarity before going live. Rendering each error as its own line/bullet would read much faster under stress.

**7.6 Critical mode-switch buried in a tabbed settings modal.** The LIVE/PAPER toggle (`handleTogglePaperTrade`, gated by the `window.confirm` in 7.3) lives inside the "strategy" tab of a modal you have to explicitly open. Given this is the one switch that turns real money trading on, surfacing its current state more prominently in the main header (not just the small "PAPER TRADE" badge that already exists) — and requiring a second, explicit confirmation step (e.g., type "LIVE" to confirm) rather than a single OK click — would reduce the chance of an accidental live-mode flip.

**7.7 Export buttons give no feedback beyond a spinner glyph.** `handleExportTrades`/`handleExportLogs` (Dashboard.tsx) show a tiny inline spinner during the request but no success confirmation once the download fires — easy to click twice or wonder if it worked, especially since the file just silently lands in the Downloads folder.

**7.8 Trade Log / Open Positions panels have a fixed pixel height implied by `space-y-3` stacking with no internal scroll.** Once `trades` grows past a screenful, `TradeLog.tsx` (56 lines — worth checking it caps rows or scrolls internally) can push the P&L chart and Trade Log off-screen together; an internal `max-h-* overflow-y-auto` on the trade list keeps the dashboard layout stable as the day's trade count grows.

**7.9 Color is the only signal for state in a few spots.** CE/PE labels, P&L sign, and the LIVE/DISCONNECTED WS badge all rely solely on green/red. For colorblind users (and for quick scanning under stress), pairing color with a consistent icon or +/- prefix (already partly done for P&L's `+`/no-sign) everywhere color is used as the sole differentiator would help — e.g., the WS status dot, the CE/PE badges in "Open Positions."

**7.10 No dark/light theme toggle, but that's a minor nice-to-have** — the dark theme is reasonable for an always-on trading dashboard; not a priority relative to 7.1–7.6.

### Suggested UI priority order
1. Replace `window.confirm`/`alert` with an in-app modal/toast — especially the LIVE-mode confirmation (7.3, 7.6).
2. Add `aria-label`s to icon-only buttons and a focus trap to the Settings/LiveLog modals (7.2) — cheap, immediate accessibility win.
3. Split the safety-check error banner into a list (7.5) — directly affects decision-making before going live.
4. Add a mobile/tablet responsive breakpoint pass to `Dashboard.tsx` and `Settings.tsx` (7.1).
5. Loading/skeleton states for LTP and P&L (7.4), scroll containment on Trade Log (7.8), export success feedback (7.7).
