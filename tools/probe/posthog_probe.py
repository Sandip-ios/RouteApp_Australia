"""Which PostHog region (US or EU) holds this project? The project key is public by design (it goes in the app)."""
import json, urllib.request
KEY = "phc_noPj7zBuBu5LXhEGJm4pKMcouu8Hca76RyaevLt3PkA5"
for host in ["https://us.i.posthog.com", "https://eu.i.posthog.com"]:
    for path in ["/flags/?v=2", "/decide/?v=3"]:
        try:
            req = urllib.request.Request(host + path, data=json.dumps({"api_key": KEY, "distinct_id": "dropline-probe"}).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as r: print(host, path, r.status, r.read()[:200])
        except urllib.error.HTTPError as e: print(host, path, e.code, e.read()[:200])
        except Exception as e: print(host, path, "ERR", e)
