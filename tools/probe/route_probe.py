"""Check the driver's real route on the real routing server: which order is fastest, and why."""
import json, urllib.request, itertools, time
P = json.load(open("tools/probe/user_route.json"))
def get(url):
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DropLine-probe"}), timeout=25) as r: return json.load(r)
        except Exception as e: print("retry", e); time.sleep(2)
coords = ";".join(f"{p['lon']},{p['lat']}" for p in P)
j = get(f"https://router.project-osrm.org/table/v1/driving/{coords}?annotations=duration,distance")
D, Di = j["durations"], j["distances"]
names = [p["a"].split(",")[0] for p in P]
print("Attached roads:")
for p, w in zip(P, j["destinations"]): print(f"  {p['a'].split(',')[0]:28s} -> {w.get('name')!r} ({round(w.get('distance', 0))} m)")
print("\nDrive times (seconds) between key stops:")
idx = {n: i for i, n in enumerate(names)}
for a in ["22 Flowerdale Road", "14 Greenstead Way", "27 Lister Street", "58 Bent Street", "44 Levenia Street"]:
    print(f"  from {a:20s}: " + ", ".join(f"{b.split(' ',1)[1][:10]} {round(D[idx[a]][idx[b]])}s" for b in names if b != a))
cost = lambda o: sum(D[x][y] for x, y in zip(o, o[1:]))
A = [0, 1, 2, 3, 4, 5, 6, 7]                 # app order: ... Flowerdale, Lister, Levenia, Bent, Greenstead
B = [0, 1, 2, 3, 7, 4, 5, 6]                 # Greenstead between Flowerdale and Lister
print(f"\nApp order (Greenstead last):        {round(cost(A))} s, {round(sum(Di[x][y] for x,y in zip(A,A[1:])))} m")
print(f"Greenstead after Flowerdale:         {round(cost(B))} s, {round(sum(Di[x][y] for x,y in zip(B,B[1:])))} m")
best = min(([0] + list(p) for p in itertools.permutations(range(1, len(P)))), key=cost)
print(f"Best possible (every order tried):   {round(cost(best))} s  -> " + " > ".join(names[i] for i in best))
for (x, y) in [(3, 7), (7, 4), (6, 7), (3, 4)]:
    r = get(f"https://router.project-osrm.org/route/v1/driving/{P[x]['lon']},{P[x]['lat']};{P[y]['lon']},{P[y]['lat']}?steps=true&overview=false")
    st = r["routes"][0]["legs"][0]["steps"]
    print(f"\n{names[x]} -> {names[y]}: {round(r['routes'][0]['duration'])} s, {round(r['routes'][0]['distance'])} m via " + " / ".join(f"{s.get('name') or '-'}({round(s['distance'])}m)" for s in st))
