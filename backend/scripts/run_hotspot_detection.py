"""
Run DBSCAN hotspot detection via the live API and print a report.
"""
import requests
import json
import time
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings

BASE = "http://127.0.0.1:8000"

def wait_for_server(retries=10, delay=2):
    for _ in range(retries):
        try:
            r = requests.get(f"{BASE}/api/health", timeout=3)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False

def main():
    print("Waiting for server to be ready...")
    if not wait_for_server():
        print("ERROR: Server not reachable.")
        return

    print("Server is up.\n")

    # ----------------------------------------------------------------
    # Run DBSCAN detection
    # ----------------------------------------------------------------
    print("=== POST /api/hotspots/detect ===")
    payload = {"eps_km": settings.DBSCAN_EPS_KM, "min_samples": settings.DBSCAN_MIN_SAMPLES}
    r = requests.post(f"{BASE}/api/hotspots/detect", json=payload, timeout=120)
    print(f"Status: {r.status_code}")
    result = r.json()
    print(json.dumps(result, indent=2))

    print()
    # ----------------------------------------------------------------
    # Stats
    # ----------------------------------------------------------------
    print("=== GET /api/hotspots/stats ===")
    r = requests.get(f"{BASE}/api/hotspots/stats")
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))

    print()
    # ----------------------------------------------------------------
    # List hotspots (top 5)
    # ----------------------------------------------------------------
    print("=== GET /api/hotspots?limit=5 ===")
    r = requests.get(f"{BASE}/api/hotspots?limit=5")
    print(f"Status: {r.status_code}")
    d = r.json()
    print(f"Total clusters stored: {d['total']}")
    print("Sample clusters:")
    for c in d["data"][:3]:
        print(f"  cluster_id={c['cluster_id']} | observations={c['observation_count']} "
              f"| severity={c['severity']} | avg_pollution={c['average_pollution']} "
              f"| centroid=({c['centroid']['latitude']}, {c['centroid']['longitude']})")

    print()
    # ----------------------------------------------------------------
    # Single cluster by ID
    # ----------------------------------------------------------------
    if d["data"]:
        cid = d["data"][0]["cluster_id"]
        print(f"=== GET /api/hotspots/{cid} ===")
        r = requests.get(f"{BASE}/api/hotspots/{cid}")
        print(f"Status: {r.status_code}")
        print(json.dumps(r.json(), indent=2))

    print()
    # ----------------------------------------------------------------
    # Filter by severity CRITICAL
    # ----------------------------------------------------------------
    print("=== GET /api/hotspots?severity=CRITICAL ===")
    r = requests.get(f"{BASE}/api/hotspots?severity=CRITICAL&limit=100")
    d = r.json()
    print(f"Status: {r.status_code}")
    print(f"CRITICAL clusters: {d['total']}")

    print()
    # ----------------------------------------------------------------
    # 404 check
    # ----------------------------------------------------------------
    print("=== GET /api/hotspots/99999 (404 check) ===")
    r = requests.get(f"{BASE}/api/hotspots/99999")
    print(f"Status: {r.status_code}")
    print(f"Body: {r.json()}")

if __name__ == "__main__":
    main()
