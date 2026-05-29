import requests

BASE = "https://ela.kpi.ua/server/api"
UUID = "e475e84c-48ff-4236-9633-694b923e4a82"

# Тест 1: чи взагалі колекція відповідає
r1 = requests.get(f"{BASE}/core/collections/{UUID}")
print("Collection:", r1.status_code, r1.text[:300])

# Тест 2: discover endpoint
r2 = requests.get(f"{BASE}/discover/search/objects",
    params={"scope": UUID, "dsoType": "item", "page": 0, "size": 5})
print("Discover:", r2.status_code, r2.text[:500])

# Тест 3: що взагалі є на /server/api
r3 = requests.get(f"{BASE}")
print("Root links:", list(r3.json().get("_links", {}).keys()))
