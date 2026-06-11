# Copilot Instructions for PyramidStrategy

## Project shape
- `backend/` is the implemented runtime surface in this checkout.
- The backend is FastAPI-based and centers on `app/main.py`, which wires startup/shutdown, APScheduler jobs, CORS, REST routes, and the WebSocket endpoint.
- Core trading behavior lives in `app/core/`: `strategy_engine.py` orchestrates the flow, `state_machine.py` holds CE/PE state, `time_rules.py` enforces cutoff/expiry logic, `option_selector.py` resolves strikes and symbols, and `order_manager.py` persists paper/live orders.
- Data models are SQLAlchemy in `app/models/models.py`; request/response contracts are Pydantic models in `app/schemas/schemas.py`.
- `CLAUDE.md` is the source of truth for strategy rules; keep code aligned with it.

## Setup and run
- Backend setup:
  ```powershell
  cd D:\PyramidStreategy\backend
  python -m venv venv
  venv\Scripts\activate
  pip install -r requirements.txt
  copy .env.example .env
  ```
- Start the backend:
  ```powershell
  cd D:\PyramidStreategy\backend
  venv\Scripts\activate
  uvicorn app.main:app --reload --port 8000
  ```
- Frontend dev server:
  ```powershell
  cd D:\PyramidStreategy\frontend
  npm install
  npm run dev
  ```

## Tests
- Run the full backend test suite:
  ```powershell
  cd D:\PyramidStreategy\backend
  venv\Scripts\activate
  pytest tests/ -v
  ```
- Run a single test file:
  ```powershell
  pytest tests\test_time_rules.py -v
  ```
- Run a single test:
  ```powershell
  pytest tests\test_state_machine.py -k "test_sl_active_at_l3" -v
  ```

## Key conventions
- Treat CE and PE as independent state machines; never couple their state or lifecycle.
- Never hardcode R1/R2/R3/S1/S2/S3 in strategy code; load levels from config.
- Use `Decimal` for prices, averages, and P&L math.
- Respect the hard rules from `CLAUDE.md`: strike locks at level 1, max 3 lots per side, no entries after 11:15 IST, square off by 11:30 IST, Tuesday uses next weekly expiry, and exits are MARKET-only.
- Paper trade is the default local mode (`PAPER_TRADE=true`), and Redis is faked locally (`USE_FAKE_REDIS=true`).
- `backend/pyramidstrategy.db` is a local dev artifact and is ignored.
- Strategy and service code logs with `loguru`; prefer the existing logging style and keep AI calls non-blocking.
- Validation is already encoded in Pydantic models and tests; reuse those patterns instead of adding ad hoc checks.
