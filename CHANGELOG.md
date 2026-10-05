# Changelog

All notable changes are recorded here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Releases before this file was started are described on the [GitHub Releases](https://github.com/nextginfosoft/PyramidStrategy/releases) page.

## [Unreleased]

Promoted to `dev`, `main` and `destiny` on 2026-10-05 after a live market session on staging.

### Added
- **Ratchet Step** for Destiny: an opt-in repeating-ratchet TARGET exit. Reaching the target locks a floor, every further step raises it, and the trade closes when price drops below the floor. Blank keeps today's flat target exit. Also replayed in backtests. (#43)
- **Real option-price backtesting**: Destiny backtests trade the contract the engine would actually buy and price it from recorded Kite 1-minute candles, falling back to a Black-Scholes estimate (Model IV %). A "Fetch real option prices" button back-fills recent days, and a 15:45 job records the day's contracts. (#44)
- **Per-side level toggle** for Destiny: run with only Resistance or only Support. The dashboard shows a disabled side as "Disabled". (#46, #47)
- Backtest trades log shows the **Instrument** (option contract) and the locked **floor** next to the exit reason. (#48, #49)
- Destiny Strategy guide (PDF) with worked examples. (#50)
- User-configurable **No Entry Time** setting. (#38)
- Logged-in **Zerodha ID** on the dashboard Kite card. (#40)
- NIFTY spot **active high/low** tracked alongside the option premium range. (#34)

### Changed
- Backtest exits fill at the exact line crossed (SL, target or locked floor) instead of the observed price. (#44)
- The Destiny engine on `dev` was brought to parity with the `destiny` branch (post-exit tracking, daily reset, active-range tracking). (#36)

### Fixed
- The scheduler's square-off backstop now works for Destiny. It called `_force_squareoff()`, which only the Pyramid engine had, so at square-off time it logged an error and did nothing; a Destiny position could stay open if NIFTY ticks had stopped arriving. Both the tick path and the scheduler now go through one guarded entry point, so an overlap cannot square off or notify twice.
- The dashboard now updates instantly on a Destiny trade: the engine broadcasts `trade_event`, the type the frontend listens for. (#45)
- Admin "sync levels" no longer drops its writes when engines are re-created inside the same transaction. (#43)
- `sqlalchemy` is capped below 2.1, which defaulted plain `postgresql://` URLs to a driver the app does not ship and crash-looped the backend. (#41)
