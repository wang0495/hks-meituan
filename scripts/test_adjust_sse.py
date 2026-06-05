"""Quick SSE adjust smoke test."""
import requests
import json
import sys

BASE = "http://127.0.0.1:8000"

print("=== Step 1: Plan a route ===")
resp = requests.post(
    f"{BASE}/api/plan",
    json={"user_input": "珠海一日游"},
    timeout=120,
    stream=True,
)

route_id = None
for line in resp.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data: "):
        continue
    data = json.loads(line[6:])
    if "route_id" in data:
        route_id = data["route_id"]
        steps = data.get("full_route", {}).get("route", [])
        print(f"  route_id = {route_id}")
        print(f"  steps = {len(steps)}")
        break
    elif "error" in data:
        print(f"  ERROR: {data['error']}")
        sys.exit(1)

if not route_id:
    print("  NO route_id obtained!")
    sys.exit(1)

print()
print("=== Step 2: Adjust route (SSE) ===")
resp2 = requests.get(
    f"{BASE}/api/route/{route_id}/adjust",
    params={"instruction": "太赶了，想轻松点"},
    timeout=120,
    stream=True,
)

print(f"  HTTP {resp2.status_code}")
print(f"  Content-Type: {resp2.headers.get('content-type')}")
print()

for line in resp2.iter_lines(decode_unicode=True):
    if not line:
        continue
    if line.startswith("event: "):
        evt = line[7:].strip()
        print(f"  [event] {evt}")
    elif line.startswith("data: "):
        data = json.loads(line[6:])
        if "reply" in data:
            print(f"  [reply] {data['reply'][:100]}")
        if "route" in data and isinstance(data["route"], dict):
            new_steps = data["route"].get("route", [])
            print(f"  [route] {len(new_steps)} steps")
        if "error" in data:
            print(f"  [error] {data['error']}")
        if "message" in data:
            print(f"  [phase] {data['message']}")

print()
print("=== ALL DONE ===")
