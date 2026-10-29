"""Does allowing a turn-around at stops (continue_straight=false) make the drawn route shorter, and closer to the
door-to-door times the optimiser uses? Public street points only."""
import json, time, urllib.request
OSRM = "https://router.project-osrm.org"
P = json.load(open("tools/probe/speed_points.json"))[:60]
ll = lambda p: "%.6f,%.6f" % (p[1], p[0])
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "DropLine-probe"}), timeout=40) as r: return json.loads(r.read())
# a sensible order: nearest neighbour on the table
T = get(OSRM + "/table/v1/driving/" + ";".join(ll(p) for p in P) + "?annotations=duration,distance")
D = T["durations"]; order = [0]; left = set(range(1, len(P)))
while left: k = min(left, key=lambda j: D[order[-1]][j]); order.append(k); left.remove(k)
tsum = sum(D[a][b] for a, b in zip(order, order[1:])); dsum = sum(T["distances"][a][b] for a, b in zip(order, order[1:]))
coords = ";".join(ll(P[i]) for i in order); time.sleep(1)
r1 = get(OSRM + "/route/v1/driving/" + coords + "?overview=false")["routes"][0]; time.sleep(1)
r2 = get(OSRM + "/route/v1/driving/" + coords + "?overview=false&continue_straight=false")["routes"][0]
print("60 stops in one order")
print("door-to-door times added up (what the optimiser uses): %.0f min, %.1f km" % (tsum / 60, dsum / 1000))
print("drawn route, keep going straight (before):          %.0f min, %.1f km" % (r1["duration"] / 60, r1["distance"] / 1000))
print("drawn route, may turn around at stops (now):        %.0f min, %.1f km" % (r2["duration"] / 60, r2["distance"] / 1000))
legs1, legs2 = r1["legs"], r2["legs"]
worse = sorted(((l1["distance"] - l2["distance"], i) for i, (l1, l2) in enumerate(zip(legs1, legs2))), reverse=True)[:5]
print("biggest detours removed (m):", [round(w) for w, _ in worse])
