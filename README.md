# PyramidStrategy

Automated NIFTY options trading system for the intraday pyramid strategy.

## What’s here
- **Backend:** FastAPI + SQLAlchemy + APScheduler
- **Frontend:** React 18 + TypeScript + Vite
- **Data:** SQLite for local dev, Redis or fakeredis for cache/state

The strategy engine keeps CE and PE legs independent, locks the strike on the first entry, and enforces the time rules from `CLAUDE.md`.

## Setup

### Backend
```powershell
cd D:\PyramidStreategy\backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### Frontend
```powershell
cd D:\PyramidStreategy\frontend
npm install
```

## Run

### Backend
```powershell
cd D:\PyramidStreategy\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Backend: `http://localhost:8000`  
API docs: `http://localhost:8000/docs`

### Frontend
```powershell
cd D:\PyramidStreategy\frontend
npm run dev
```

Frontend: `http://localhost:5173`

## Test

### Backend tests
```powershell
cd D:\PyramidStreategy\backend
venv\Scripts\activate
pytest tests/ -v
```

### Single test file
```powershell
pytest tests\test_time_rules.py -v
```

### Single test
```powershell
pytest tests\test_state_machine.py -k "test_sl_active_at_l3" -v
```

## Key rules
- R1/R2/R3 and S1/S2/S3 come from config, not hardcoded values.
- No entries after **11:15 AM IST**.
- Force square-off by **11:30 AM IST**.
- Tuesday uses the next weekly expiry.
- Exit orders are MARKET orders.

## More docs
- `CLAUDE.md`
- `ARCHITECTURE.md`
- `START.md`
