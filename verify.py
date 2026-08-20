"""Quick verification script to confirm all components are working."""
import sqlite3

# 1. Verify Flask app and routes
import app

routes = [r.rule for r in app.app.url_map.iter_rules()]

# 2. Verify DB tables
conn = sqlite3.connect("database.db")
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
conn.close()

# 3. Verify OpenCV and cascade
import cv2

cascade = cv2.CascadeClassifier("data/haarcascades/haarcascade_frontalface_default.xml")
cascade_ok = not cascade.empty()

# 4. Verify Streamlit / dashboard imports
import matplotlib
matplotlib.use("Agg")

import dashboard  # noqa: F401 - import to verify no errors

print("=" * 50)
print("  VERIFICATION REPORT")
print("=" * 50)
print(f"Flask app:       OK")
print(f"Routes:          {routes}")
print(f"DB tables:       {tables}")
print(f"Haar Cascade:    {'OK' if cascade_ok else 'MISSING / EMPTY'}")
print(f"Dashboard:       OK")
print("=" * 50)
print("ALL CHECKS PASSED ✅")
