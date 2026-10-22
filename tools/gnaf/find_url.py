"""Print the download link of the newest G-NAF release (GDA2020, pipe-separated files) from data.gov.au."""
import json, sys, urllib.request
API = "https://data.gov.au/data/api/3/action/package_show?id=geocoded-national-address-file-g-naf"
FALLBACK = "https://data.gov.au/data/dataset/19432f89-dc3a-4ef3-b943-5326ef1dbecc/resource/5be5278c-fe66-459e-845a-bea553f46b4b/download/g-naf_feb26_allstates_gda2020_psv_1022.zip"
try:
    req = urllib.request.Request(API, headers={"User-Agent": "Mozilla/5.0 (Dropline route planner build)"})
    pkg = json.load(urllib.request.urlopen(req, timeout=60))["result"]
    zips = [r for r in pkg["resources"] if r.get("url", "").lower().endswith(".zip") and "gda2020" in r["url"].lower()]
    zips.sort(key=lambda r: r.get("last_modified") or r.get("created") or "", reverse=True)
    for r in zips[:5]: print("candidate:", r.get("name"), r.get("last_modified"), r["url"], file=sys.stderr)
    print(zips[0]["url"] if zips else FALLBACK)
except Exception as e:
    print("lookup failed:", repr(e), file=sys.stderr)
    print(FALLBACK)
