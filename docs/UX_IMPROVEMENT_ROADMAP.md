# Frontend UX Improvement Roadmap

Derived from a UI/UX review of the React + Tailwind frontend (Dashboard, LevelPanel,
TradeLog, KiteStatus, Login, PnLChart, AIObserver). No source code was changed —
this is a planning document only.

Goal: reduce mis-click risk on a live-money trading screen, remove ambiguity about
data freshness, and make the dashboard usable on more screen sizes — without a
redesign.

---

## Phase 1 — Critical / Quick Wins (1–3 days)

Highest risk-to-cost ratio. Do these first.

| # | Item | Why it matters | Touch points |
|---|------|-----------------|---------------|
| 1.1 | [Completed] Confirm-before-action on **STOP** and **Simulate Tick** | Single misclick can halt a live strategy or inject a fake price tick | `Dashboard.tsx` start/stop buttons, simulate tick handler |
| 1.2 | [Completed] Replace `alert()` with a toast/notification component | `alert()` blocks the UI thread and is inconsistent with the rest of the app's styling | `Dashboard.tsx` export handlers, `KiteStatus.tsx` messages |
| 1.3 | [Completed] Add "last updated Xs ago" on NIFTY price + P&L tiles | Removes ambiguity about whether displayed data is current, especially when `wsConnected` is false | `Dashboard.tsx` price/P&L cards |
| 1.4 | [Completed] Color contrast / accessibility audit (axe or Lighthouse) | Confirm CE/PE red-green pairing, focus rings, emoji alt text — establishes a baseline before further visual changes | App-wide |

---

## Phase 2 — Structural UX Fixes (1–2 weeks)

These require layout or state-management changes but no architecture rework.

| # | Item | Why it matters | Touch points |
|---|------|-----------------|---------------|
| 2.1 | [Completed] Responsive layout: stack the 3-column grid below `lg` breakpoint | Currently fixed `grid-cols-12`; unusable on tablet/phone widths | `Dashboard.tsx` |
| 2.2 | Horizontal scroll / column-priority for TradeLog table on narrow screens | 7-column table has no mobile fallback | `TradeLog.tsx` |
| 2.3 | [Completed] Unified toast/notification system (success, error, warning, info) | Currently 3 different patterns (alert, inline banner, message paragraph) | New shared component; used by `Dashboard`, `KiteStatus`, `Settings` |
| 2.4 | Loading/skeleton states for price, P&L, config, open positions | `'—'` is ambiguous between "loading," "no data," and "broken" | `Dashboard.tsx`, `LevelPanel.tsx` |
| 2.5 | [Completed] Pause/reduce 3s polling fallback when WebSocket is actually connected | Avoids redundant network calls and potential stale-vs-live conflicts | `Dashboard.tsx` queries, `useWebSocket.ts` |
| 2.6 | [Completed] Trade log filters: side (CE/PE), level, win/loss, date range | Only "today" is queryable from UI; log will get harder to scan as trade count grows | `TradeLog.tsx`, `services/api.ts` |

---

## Phase 3 — Polish & Trust Signals (ongoing / as time allows)

Lower urgency, but compounds the "feels professional" perception.

| # | Item | Why it matters |
|---|------|-----------------|
| 3.1 | Proactive Kite re-auth prompt (toast + one-click re-login) the moment a request fails due to expired token, instead of a static always-on warning | Reduces time-to-recovery from the daily 6 AM token expiry |
| 3.2 | Promote Today's P&L visually (larger type / pinned position) | It's the most-glanced-at number; currently equal-weight with other cards |
| 3.3 | Subtle pulse/highlight animation on P&L or price when a new value lands | Draws the eye to what changed instead of a silent value swap |
| 3.4 | Smooth numeric transitions (count-up/fade) instead of instant value jumps | Reduces "flicker" feel from polling-driven updates |
| 3.5 | Consistent modal behavior: Esc-to-close, click-outside-to-close, focus trap | Currently unverified across `Settings`, `BacktestModal`, `LiveLogModal`, `PDFReportsModal` |
| 3.6 | Replace fixed `setTimeout(1500)` auto-login-after-register with awaited chained call | Avoids feeling laggy on slow networks; more correct |
| 3.7 | Password strength/length hint on registration | Minor but standard UX expectation |
| 3.8 | Icon/shape redundancy alongside color for CE/PE and level states | Accessibility for colorblind users (red/green is the worst pairing for deuteranopia) |
| 3.9 | [Completed] NIFTY price tile redesign: % / point change badge (↑/↓ colored pill) + market-style timestamp, Google-Finance-style | Gives the price tile the at-a-glance "is the market up or down" signal that a bare LTP number doesn't provide. **Needs a backend addition first**: `prev_close` (or `day_open`) is not currently in `StrategyStatus` — likely sourced from Kite's `ohlc.close` quote field alongside the existing `nifty_ltp` feed. |

---

## Suggested Sequencing

```
Week 1        Phase 1 (1.1 - 1.4)
Week 2-3      Phase 2 (2.1 - 2.4)
Week 3-4      Phase 2 (2.5 - 2.6)
Ongoing       Phase 3, picked up between feature work
```

## Out of Scope (for this roadmap)

- Backend/API changes (e.g. new filter endpoints) are noted as touch points but not
  scoped here — Phase 2.6 will need a small API addition for date-range/side filtering
  if not already supported server-side.
- Visual redesign / rebranding — this roadmap only fixes usability gaps in the
  existing dark trading-terminal aesthetic.

---

*Generated from a manual code review on 2026-06-20. No source files were modified.*
