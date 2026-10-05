# Contributing

Thanks for helping improve PyramidStrategy / DestinyAI. This guide covers how changes flow from an idea to production.

## Branches and promotion

| Branch | Purpose | What a push does |
|---|---|---|
| `dev` | Integration and staging. **All work starts here.** | CI runs, then deploys the staging server |
| `main` | Production | CI gate, then deploys production |
| `destiny` | The dedicated Destiny deployment | Tests, then deploys that server |

`main` and `destiny` have diverged from `dev` over time, so a change that must reach all three is **cherry-picked** onto each (a clean `dev` PR first, then a port PR per branch).

Typical flow:

1. Branch from `dev`: `git checkout -b dev-<short-topic> origin/dev`
2. Make the change, add tests, push, and open a PR into `dev`.
3. CI must be green. Merge. The staging server redeploys automatically.
4. **If the change touches live-trading logic** (engines, order placement, exits, config loading), let it run through a real market session on staging before porting.
5. Port to `main` and `destiny` with one PR each, and make sure CI passes on each.

Never push directly to `main` or `destiny`.

## Local setup

See the [README](README.md#local-development). In short: `pip install -r backend/requirements.txt`, `npm ci` in `frontend/`, copy `backend/.env.example` to `backend/.env`.

## Before you open a PR

```bash
cd backend && pytest tests/ -v        # backend tests
cd frontend && npm run build          # TypeScript check + production build
cd frontend && npm run lint           # ESLint
```

CI runs the same checks plus flake8 and Docker image builds. Use the same environment CI uses for the backend tests if you hit differences:
`DATABASE_URL=sqlite:///:memory: USE_FAKE_REDIS=true MOCK_TIME=10:00`.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) in the present tense:

```
feat(destiny): add opt-in repeating-ratchet TARGET exit
fix(backtest): show the traded option contract as an Instrument column
docs: add Destiny Strategy guide
chore(ci): ...
```

Keep the subject short, and use the body to explain *why*.

## Engineering rules that have bitten us

- **`strategy_config` is append-only.** Every save inserts a new row. When you add a field, thread it through **every** writer and loader (`config.py`, `admin.py` sync-levels, `strategy.py`, `ai.py`, `main.py` startup, both engine config loaders, the backtest) or it is silently dropped on the next save.
- **New settings are opt-in.** Add a nullable column with no default, where `NULL` means "today's behaviour, unchanged", so deploying never changes how existing users trade. Columns are added by the self-healing migration in `backend/app/db/database.py` (no Alembic).
- **Do not open a nested DB session inside an open transaction** (for example calling `engine_manager.get_engine()` mid-transaction). Under SQLite's single shared test connection it rolls the outer transaction back.
- **Pin and cap dependencies.** An unpinned `sqlalchemy>=2.0` pulled in 2.1 and crash-looped a deploy. Prefer upper bounds on anything that can change defaults.
- **Never commit secrets** and never rely on a default secret in `docker-compose.yml`. See [SECURITY.md](SECURITY.md).
- **Time is IST.** Report and store project times in IST, not UTC.
