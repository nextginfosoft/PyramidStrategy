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
print("🚀 Live Dashboard UI Simulation Walkthrough")
print("==========================================================")

# 1. Reset strategy to start fresh
print("\n🔄 Resetting strategy to clear previous trades...")
try:
    res = requests.post(f"{BASE_URL}/strategy/reset-daily", headers=headers)
    print("Reset response:", res.json())
except Exception as e:
    print(f"Failed to reset: {e}. Is the backend uvicorn running on port 8000?")
    sys.exit(1)
time.sleep(1)

# 2. Save settings
print("\n⚙️ Saving strategy settings (S1=23100, Target=20, SL=10)...")
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
print("\n▶️ Starting Strategy Engine...")
res = requests.post(f"{BASE_URL}/strategy/start", headers=headers)
print("Start response:", res.json())
print("\n👉 OPEN YOUR BROWSER TO http://localhost:5173/ NOW TO WATCH THE LIVE ACTIONS!")
time.sleep(4)

def simulate_nifty(price):
    print(f"\n📈 Simulating NIFTY price: {price}...")
    res = requests.post(f"{BASE_URL}/strategy/simulate-tick?nifty_price={price}", headers=headers)
    data = res.json()
    status_ce = data.get("ce", {})
    status_pe = data.get("pe", {})
    print(f"  * NIFTY: {data.get('nifty_ltp')} | CE state: {status_ce.get('state')} | PE state: {status_pe.get('state')}")
    if status_ce.get('state') != 'IDLE':
        print(f"  * CE LTP: ₹{status_ce.get('current_ltp')} | Avg: ₹{status_ce.get('entry_avg_price')} | Min/Max: [₹{status_ce.get('active_low')} / ₹{status_ce.get('active_high')}]")
    if status_pe.get('state') != 'IDLE':
        print(f"  * PE LTP: ₹{status_pe.get('current_ltp')} | Avg: ₹{status_pe.get('entry_avg_price')} | Min/Max: [₹{status_pe.get('active_low')} / ₹{status_pe.get('active_high')}]")

# Tick 1: Idle state (Nifty above S1)
simulate_nifty(23120)
time.sleep(4)

# Tick 2: Trigger L1 entry (drops below S1: 23100)
# (Visualizer should appear on dashboard card instantly)
simulate_nifty(23095)
time.sleep(5)

# Tick 3: Price moves UP (CE premium rises, updates Active High!)
simulate_nifty(23115)
time.sleep(5)

# Tick 4: Price moves DOWN (CE premium falls, updates Active Low!)
simulate_nifty(23085)
time.sleep(5)

# Tick 5: Price hits target (premium up by > 20 points, exits position!)
simulate_nifty(23145)
time.sleep(3)

print("\n🎉 Walkthrough Simulation Complete!")
print("Review your dashboard: check the CE Card transition to IDLE, the Trade Log table (new Active Range column), and click 'Export CSV' to audit the saved logs.")
