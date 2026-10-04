# BANKNIFTY (paper) — runbook

BANKNIFTY runs alongside NIFTY with its own engine, levels, trades and P&L.
**It is paper-only**: the backend forces paper mode for any instrument flagged
`paper_only` in `backend/app/core/instruments.py`, whatever the saved config says.

## What differs from NIFTY

| | NIFTY | BANKNIFTY |
|---|---|---|
| Strike step / option offset | 50 / ATM ± 50 | 100 / ATM ± 100 |
| Lot size (registry default) | 65 | 30 |
| Expiry | weekly (Tuesday; Tuesday-roll rule) | monthly only: last Tuesday, previous trading day if holiday; rolls to next month on/after expiry day |
| Live trading | yes | **no** |
| AI brief / review, Telegram bot, weekly report | yes | not yet (NIFTY-only; weekly report sums both) |

Strategy rules (levels, 20-pt target, 10-pt L3 stop loss, 11:15 entry cut-off, 11:30 square-off,
strike lock, no re-entry) are identical and shared code.

## Step 0 — verify the registry against Zerodha (do this first, and after any NSE circular)

Lot size and expiry rules are exchange-controlled. The registry values were taken from public
sources, not from your broker, so check them against the live instrument dump:

```powershell
cd backend
$env:KITE_API_KEY = "<your key>"
$env:KITE_ACCESS_TOKEN = "<today's access token>"
python scripts/verify_instruments.py
```

`[ OK ]` for both instruments means lot size, strike step, spot token and the expiry the rule
picks all match the dump. Any `FAIL` line says what to change in `instruments.py`.

## Paper session checklist

**Before the open (≈ 9:00–9:15 IST)**
1. Connect Kite (Settings → Kite Connect). Instrument cache for BANKNIFTY options loads when a
   BANKNIFTY engine exists (9:00 AM job, or on first use).
2. Switch to **BANKNIFTY** in the sidebar. Set R1–R3 / S1–S3 around the live BANK NIFTY spot
   (the defaults are placeholders around 52,000) and save. The Live button is disabled.
3. Press **START**. Expect: BANK NIFTY spot card shows a live price (not "simulated"); the
   response/toast has no "SIMULATED prices" warning. If you see it, the Kite ticker is not running.

**During the session**
4. On an entry, check the trade log: symbol `BANKNIFTY<YY><MON><strike><CE|PE>` (e.g.
   `BANKNIFTY26OCT55000CE`), strike a multiple of 100, quantity = lots × 30, expiry = the monthly
   expiry, flagged as paper trades.
5. Confirm NIFTY is unaffected: switch tabs; NIFTY P&L, trades and engine state must not change
   when BANKNIFTY trades. The green dot next to a tab means that instrument's engine is running.
6. Option prices: BANKNIFTY paper fills use live option ticks when the symbol is subscribed,
   otherwise the local estimator. If the log shows estimator prices while the ticker is up,
   the instrument cache did not load — reload instruments from the Kite card (or restart the engine).

**After the session**
7. Square-off happens on the BANKNIFTY config's own `squareoff_time`; the EOD report arrives
   15 min later and covers BANKNIFTY only (separate `daily_pnl` row).
8. P&L Analytics and Export (CSV) follow the selected instrument.

## Known gaps (not bugs — not built)
- Live trading for BANKNIFTY (intentionally blocked).
- AI pre-market brief / post-session review for BANKNIFTY; Telegram bot commands (user 1, NIFTY).
- Weekly summary mixes instruments; report/landing/guide copy still says "NIFTY" in places.
- The synthetic backtest uses a simple premium model — treat results as a smoke test, not a forecast.

## Rolling back
- Pre-migration database copies were taken in `backups/` (git-ignored) before Phase 2.
- Schema change is additive (`underlying` column, default `NIFTY`); old code ignores it, except
  `daily_pnl`'s unique key now includes `underlying`.
- Code: each phase is its own commit on the `banknifty` branch (`git log --oneline`).
