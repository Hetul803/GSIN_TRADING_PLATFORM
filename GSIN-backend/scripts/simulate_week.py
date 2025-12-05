#!/usr/bin/env python3
import time, os, subprocess
API = os.environ.get("API_URL", "http://localhost:8000")
for day in range(7):
    print(f"Sim day {day+1}/7")
    subprocess.call(["python","scripts/seed_strategies.py"])
    time.sleep(0.5)
print("Done.")
