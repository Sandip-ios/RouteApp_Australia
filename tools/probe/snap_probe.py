"""How often does the routing server attach a house to a road that is not its own street? (real addresses, real server)"""
import json, time, urllib.request, re, sys
rows = json.load(open("tools/probe/sample_3023.json"))
TYPES = r" (STREET|ROAD|AVENUE|DRIVE|COURT|CRESCENT|PLACE|CLOSE|GROVE|LANE|PARADE|TERRACE|WAY|CIRCUIT|BOULEVARD|HIGHWAY|SQUARE|WALK|ESPLANADE|RISE|VIEW|PARKWAY|LOOP|TRAIL|MEWS|GARDENS|HEIGHTS|RIDGE|VISTA|END)$"
FULL = {"ST":"STREET","RD":"ROAD","AVE":"AVENUE","AV":"AVENUE","DR":"DRIVE","CT":"COURT","CRES":"CRESCENT","CR":"CRESCENT","PL":"PLACE","CL":"CLOSE","GR":"GROVE","LN":"LANE","PDE":"PARADE","TCE":"TERRACE","CCT":"CIRCUIT","BVD":"BOULEVARD","HWY":"HIGHWAY"}
def norm(s):
    w = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper()).split()
    if len(w) > 1 and w[-1] in FULL: w[-1] = FULL[w[-1]]
    return " ".join(w)
same = lambda a, b: norm(a) == norm(b) or re.sub(TYPES, "", norm(a)) == re.sub(TYPES, "", norm(b))
def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DropLine-probe"}), timeout=20) as r: return json.load(r)
        except Exception as e: time.sleep(2)
    return None
bad, fixed, total = [], 0, 0
for r in rows:
    j = get(f"https://router.project-osrm.org/nearest/v1/driving/{r['lon']},{r['lat']}?number=12"); time.sleep(1.05)
    if not j or not j.get("waypoints"): continue
    total += 1
    first = j["waypoints"][0]
    if not same(first.get("name"), r["st"]):
        own = next((w for w in j["waypoints"] if same(w.get("name"), r["st"]) and w.get("distance", 0) < 300), None)
        bad.append((r["a"], first.get("name"), round(first.get("distance", 0)), own and round(own["distance"])))
        if own: fixed += 1
print(f"addresses checked: {total}")
print(f"attached to a different road: {len(bad)} ({100*len(bad)//max(total,1)}%)")
print(f"of those, own street found nearby (fix works): {fixed}")
for b in bad: print("  ", b[0], "-> attached to", repr(b[1]), b[2], "m; own street at", b[3], "m")
