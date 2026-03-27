import httpx, os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("TRONSCAN_API_KEY", "")
headers = {"TRON-PRO-API-KEY": key}
base = "https://apilist.tronscanapi.com/api"

for limit in [10, 20, 50, 100, 200]:
    r = httpx.get(base + "/contracts", params={"limit": limit, "start": 0}, headers=headers, timeout=10)
    data = r.json() if r.status_code == 200 else {}
    print(f"limit={limit} -> status={r.status_code} count={len(data.get('data', []))}")
