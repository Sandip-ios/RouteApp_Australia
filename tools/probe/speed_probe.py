"""Times the routing requests an optimise of 160 points makes: today's pattern vs faster patterns. Points are public
street locations from the official address list (no customer addresses)."""
import json, time, urllib.request, concurrent.futures as cf
OSRM = "https://router.project-osrm.org"
P = json.load(open("tools/probe/speed_points.json"))
def get(url, timeout=40):
    t = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "DropLine-probe"}), timeout=timeout) as r:
            j = json.loads(r.read()); return j, time.time() - t, r.status
    except urllib.error.HTTPError as e: return None, time.time() - t, e.code
    except Exception as e: return None, time.time() - t, str(e)[:40]
ll = lambda i: "%.6f,%.6f" % (P[i][1], P[i][0])
def table(idx, src=None, dst=None):
    u = OSRM + "/table/v1/driving/" + ";".join(ll(i) for i in idx) + "?annotations=duration,distance"
    if src is not None: u += "&sources=" + ";".join(map(str, src)) + "&destinations=" + ";".join(map(str, dst))
    return get(u)
n = len(P); C = 50; chunks = [list(range(i, min(n, i + C))) for i in range(0, n, C)]
def old():
    t = time.time(); times = []; fails = 0
    for I in chunks:
        for J in chunks:
            idx = I if I is J else I + J; src = list(range(len(I))); dst = src if I is J else list(range(len(I), len(I) + len(J)))
            j, dt, st = table(idx, src, dst); times.append(round(dt, 2)); fails += (j is None or j.get("code") != "Ok"); time.sleep(0.3)
    return time.time() - t, len(times), fails, times
def pairs():
    out = []
    for a in range(len(chunks)):
        for b in range(a + 1, len(chunks)): out.append(chunks[a] + chunks[b])
    if len(chunks) == 1: out.append(chunks[0])
    return out
def new(par):
    t = time.time(); reqs = pairs()
    with cf.ThreadPoolExecutor(par) as ex: res = list(ex.map(lambda idx: table(idx), reqs))
    return time.time() - t, len(reqs), sum(1 for j, _, _ in res if j is None or j.get("code") != "Ok"), [round(dt, 2) for _, dt, _ in res], [st for _, _, st in res if st != 200]
def nearest(par, k=40):
    t = time.time()
    with cf.ThreadPoolExecutor(par) as ex: res = list(ex.map(lambda i: get(OSRM + "/nearest/v1/driving/" + ll(i) + "?number=12"), range(k)))
    return time.time() - t, sum(1 for j, _, _ in res if j is None), [st for _, _, st in res if st != 200][:5]
def route():
    t = time.time(); f = 0
    for i in range(0, n - 1, 60):
        j, dt, st = get(OSRM + "/route/v1/driving/" + ";".join(ll(k) for k in range(i, min(n, i + 61))) + "?overview=full&geometries=geojson&steps=false"); f += j is None
    return time.time() - t, f
def check_same():
    # the 100-point union request gives the same numbers as the separate block requests
    I, J = chunks[0], chunks[1]
    a, _, _ = table(I + J); b, _, _ = table(I + J, list(range(50)), list(range(50, 100)))
    if not a or not b: return "n/a"
    d = max(abs(a["durations"][x][50 + y] - b["durations"][x][y]) for x in range(50) for y in range(50))
    return "max difference %.3f s" % d
print("points", n, "chunks", [len(c) for c in chunks])
print("same numbers:", check_same()); time.sleep(2)
for name, fn in [("OLD 16 block requests, one at a time", old), ("NEW 6 joined requests, one at a time", lambda: new(1)), ("NEW 6 joined requests, 2 at a time", lambda: new(2)),
                 ("NEW 6 joined requests, 3 at a time", lambda: new(3)), ("street check: 40 nearest, one at a time", lambda: nearest(1)), ("street check: 40 nearest, 4 at a time", lambda: nearest(4)),
                 ("route line, 3 requests", route)]:
    r = fn(); print("%-45s %6.1f s  %s" % (name, r[0], r[1:])); time.sleep(3)
