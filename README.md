# PyramidStrategy / DestinyAI

Automated **NIFTY options** trading platform with two level-based intraday strategies, a real-time dashboard,
Zerodha Kite integration, historical backtesting and Telegram / WhatsApp reporting.

> **Trading involves risk of loss.** Run in **Paper** mode first. Nothing here is investment advice.

## Strategies

| | **Destiny** | **Pyramid** |
|---|---|---|
| Idea | Two levels you choose: buy a **Put** when NIFTY reaches Resistance, a **Call** when it reaches Support | Three resistance and three support levels; positions scale in and average at each level |
| Trades per day | **One** | Up to three levels per side |
| Risk | Fixed stop-loss from the fill price; target flat or with an optional **ratchet** that lets winners run | Target off the average entry price; stop-loss activates at level 3 |
| Default square-off | 15:20 IST | 11:30 IST |
| Optional | Run Resistance-only or Support-only, no-entry time, ratchet step | No-entry time |

All risk and reward is measured in **option premium points**. Strikes are slightly out of the money (Put = ATM + 50, Call = ATM − 50) on the nearest weekly expiry, which rolls to the next week on expiry day. Exits are market orders.

Full walkthrough with worked examples: [`docs/Destiny_Strategy_Guide.pdf`](docs/Destiny_Strategy_Guide.pdf).

## Features

- **Live dashboard**: levels, positions, P&L, trade log, health of the Kite feed, instant updates over WebSocket.
- **Zerodha Kite**: automated login and token handling, live ticks, order placement (paper or live).
- **Backtesting**: replay historical days against a configuration, compare up to two alternates, price options from recorded Kite data or a Black-Scholes estimate.
- **Notifications**: Telegram and WhatsApp alerts for engine start/stop, entries, exits and a daily end-of-day PDF report.
- **AI observer** (optional): OpenAI, Anthropic or Gemini commentary and pre-market briefs.
- **Multi-user**: per-user strategy configuration and engines, admin panel, subscriptions.

## Architecture

```
React (Vite) ──REST + WebSocket──▶ FastAPI ──▶ PostgreSQL (SQLite for local/tests)
                                      │   ├──▶ Redis (fakeredis for local/tests)
                                      │   └──▶ APScheduler (daily jobs)
                                      └──▶ Zerodha Kite Connect (REST + KiteTicker)
```

- **Backend**: FastAPI, SQLAlchemy, APScheduler, Loguru, KiteConnect, FPDF2.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand.
- **Deployment**: Docker Compose (`db`, `redis`, `backend`, `frontend`) behind a reverse proxy.

Source layout: `backend/app/core` (strategy engines, state machine, time rules), `backend/app/api` (routes),
`backend/app/services` (Kite, notifications, backtesting), `frontend/src/components`, `docs/`.

## Getting started

### Run with Docker

1. Create a `.env` file next to `docker-compose.yml` with **strong, unique values** (never reuse examples or defaults):

   ```bash
   POSTGRES_PASSWORD=<random>
   SECRET_KEY=<random, 48+ chars>
   ENCRYPTION_KEY=<random, 32 chars>
   ```

   Generate them with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   Keep this file out of version control, and see [SECURITY.md](SECURITY.md).

2. Start everything:

   ```bash
   docker compose up -d --build
   ```

   The compose file does not publish any ports. Put a reverse proxy in front of the `frontend` service, or add a
   `docker-compose.override.yml` that publishes it, and never publish the database or Redis to the internet.

### Local development

Prerequisites: Python 3.11+ and Node.js 20+.

```bash
# Backend (uses a local SQLite file by default)
cd backend
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # Windows: copy .env.example .env
uvicorn app.main:app --reload --port 8000             # API docs at http://localhost:8000/docs

# Frontend (in a second terminal)
cd frontend
npm ci
npm run dev                                           # http://localhost:5173
```

On Windows, `start.bat` launches both. Variable names for `.env` are listed in [`backend/.env.example`](backend/.env.example).
Kite, Telegram, WhatsApp and AI keys are optional for local work; `PAPER_TRADE=true` simulates every order.

## Testing

```bash
cd backend
DATABASE_URL="sqlite:///:memory:" USE_FAKE_REDIS=true MOCK_TIME=10:00 pytest tests/ -v

cd ../frontend
npm run build      # TypeScript check + production build
npm run lint
```

## CI/CD

GitHub Actions runs flake8, the backend tests, the frontend build and Docker image builds on every pull request.

| Event | Result |
|---|---|
| PR into `dev` or `main` | CI only |
| Push to `dev` | CI, then deploy to staging |
| Push to `main` | Deploy to production |
| Push to `destiny` | CI, then deploy the Destiny server |
| Tag `v*` | Build the Windows executable and publish a release |

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch and promotion flow.

## Documentation

See the [documentation index](docs/README.md). Notable changes are in [CHANGELOG.md](CHANGELOG.md).

## License

Proprietary. All rights reserved. See [LICENSE](LICENSE).
