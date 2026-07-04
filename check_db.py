import sqlite3
import os

db_path = os.path.join(os.environ.get("APPDATA", ""), "PyramidStrategy", "pyramidstrategy.db")

print(f"Connecting to database at: {db_path}")
if not os.path.exists(db_path):
    print("Database file does not exist yet at this location!")
    exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Fetch users
    users = cursor.execute("SELECT id, username, is_approved, is_admin FROM users").fetchall()
    print("\nREGISTERED USERS:")
    if not users:
        print("  (No users registered yet)")
    for u in users:
        print(f"  * ID: {u[0]} | Username: {u[1]} | Approved: {u[2]} | Admin: {u[3]}")
        
    conn.close()
except Exception as e:
    print(f"Error reading database: {e}")
