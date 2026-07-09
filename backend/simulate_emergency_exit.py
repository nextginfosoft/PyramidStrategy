import sys
import os
import time
import requests
from decimal import Decimal

# Ensure python can find app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.api.routes.session import create_token
from app.config import settings

# Create a valid token for user_id = 1 (santosh)
token = create_token("1")
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

BASE_URL = "http://localhost:8000"

print("==========================================================")
print("[EMERGENCY EXIT] Feature API Simulation")
print("==========================================================")

# 1. Reset strategy to start fresh
print("\n[RESET] Resetting strategy to clear previous trades...")
try:
    res = requests.post(f"{BASE_URL}/strategy/reset-daily", headers=headers)
    print("Reset response:", res.json())
except Exception as e:
    print(f"Failed to reset: {e}. Is the backend uvicorn running on port 8000?")
    sys.exit(1)
time.sleep(1)

# 2. Save settings
print("\n[SETTINGS] Saving strategy settings (S1=23100, Target=20, SL=10)...")
settings_payload = {
    "r1": 23200.0, "r2": 23250.0, "r3": 23300.0,
    "s1": 23100.0, "s2": 23050.0, "s3": 23000.0,
    "lot_size": 150,
    "target_points": 20.0,
    "sl_points": 10.0,
    "paper_trade": True,
    "squareoff_time": "11:30"
}
res = requests.post(f"{BASE_URL}/config/strategy", json=settings_payload, headers=headers)
print("Config save response:", res.json())
time.sleep(1)

# 3. Start Strategy Engine
print("\n[START] Starting Strategy Engine...")
res = requests.post(f"{BASE_URL}/strategy/start", headers=headers)
print("Start response:", res.json())
time.sleep(1)

# 4a. Establish initial high nifty price tick above S1 (23100)
print("\n[TICK] Establishing initial NIFTY price at 23125 (above S1)...")
res = requests.post(f"{BASE_URL}/strategy/simulate-tick?nifty_price=23125", headers=headers)
data = res.json()
print(f"  * NIFTY: {data.get('nifty_ltp')} | CE state: {data.get('ce', {}).get('state')}")
time.sleep(1.5)

# 4b. Trigger L1 Entry (Nifty drops below S1: 23100)
print("\n[TICK] Simulating NIFTY price drop to 23095 to enter a CE trade...")
res = requests.post(f"{BASE_URL}/strategy/simulate-tick?nifty_price=23095", headers=headers)
data = res.json()
print("Tick simulation response status:")
print(f"  * NIFTY: {data.get('nifty_ltp')} | CE state: {data.get('ce', {}).get('state')} | PE state: {data.get('pe', {}).get('state')}")
print(f"  * CE Lots: {data.get('ce', {}).get('lots')} | Locked Instrument: {data.get('ce', {}).get('locked_instrument')}")
time.sleep(1)

# 5. Check active positions
ce_lots = data.get('ce', {}).get('lots', 0)
if ce_lots == 0:
    print("[ERROR] Failed to trigger entry. Cannot proceed with emergency exit simulation.")
    sys.exit(1)

# 6. Call the /strategy/emergency-exit endpoint
print("\n[EMERGENCY] Triggering EMERGENCY EXIT (Close All Positions and Stop)...")
res = requests.post(f"{BASE_URL}/strategy/emergency-exit", headers=headers)
exit_data = res.json()
print("Emergency Exit response:")
print(exit_data)
time.sleep(1)

# 7. Get final strategy status
print("\n[VERIFY] Verifying final strategy state...")
res = requests.get(f"{BASE_URL}/strategy/status", headers=headers)
status = res.json()
print("Final Status:")
print(f"  * Engine Is Running: {status.get('is_running')}")
print(f"  * CE State: {status.get('ce', {}).get('state')}")
print(f"  * CE Lots: {status.get('ce', {}).get('lots')}")
print(f"  * CE Blocked Levels: {status.get('ce', {}).get('blocked_levels')}")

# 8. Get trade logs for today to verify manual exit is recorded
print("\n[LOGS] Fetching today's trade log...")
res = requests.get(f"{BASE_URL}/trades/today", headers=headers)
trades = res.json()
for idx, trade in enumerate(trades):
    print(f"  * Trade {idx+1}: {trade.get('side')} | {trade.get('level')} | Action: {trade.get('action')} | Status: {trade.get('status')} | Price: {trade.get('avg_price')} | P&L: Rs. {trade.get('pnl')}")

print("\n[SUCCESS] Emergency Exit Simulation Complete!")
