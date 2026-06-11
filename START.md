# PyramidStrategy — Quick Start Guide (Windows)

## Prerequisites
- Python 3.11+ (`python --version`)
- Node.js 18+ (`node --version`)
- Git

---

## 1. Backend Setup (Run once)

```powershell
cd D:\PyramidStreategy\backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy and edit .env
copy .env.example .env
# Open .env and set your SECRET_KEY and ENCRYPTION_KEY
```

---

## 2. Start Backend

```powershell
cd D:\PyramidStreategy\backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Backend runs at: http://localhost:8000
API docs at: http://localhost:8000/docs

---

## 3. Frontend Setup (Run once)

```powershell
cd D:\PyramidStreategy\frontend
npm install
```

---

## 4. Start Frontend

```powershell
cd D:\PyramidStreategy\frontend
npm run dev
```

Frontend runs at: http://localhost:5173

---

## 5. Run Tests

```powershell
cd D:\PyramidStreategy\backend
venv\Scripts\activate
pytest tests/ -v
```

Expected: All tests pass ✓

---

## 6. First Use

1. Open http://localhost:5173
2. Click ⚙ Settings
3. Set R1/R2/R3 (resistance) and S1/S2/S3 (support) levels
4. Save Levels
5. Click ▶ START (paper trade mode ON by default)
6. Use "Simulate Tick" panel to push NIFTY prices and test the strategy

---

## 7. Git Push

```powershell
cd D:\PyramidStreategy
git add .
git commit -m "feat: Phase 1 complete — paper trade engine"
git push origin main
```

---

## Important Notes

- `PAPER_TRADE=true` in `.env` — DO NOT change until Phase 4 validation
- The DB file (`pyramidstrategy.db`) is created automatically in `backend/`
- No Redis server needed — `USE_FAKE_REDIS=true` uses in-memory fakeredis
- Strategy auto-squares off at 11:30 AM IST (APScheduler job)
- No entries allowed after 11:15 AM IST (enforced in code)
