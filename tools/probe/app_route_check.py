"""Run the LIVE app (real map + real routing server) on a real Deer Park / Cairnlea / St Albans run and record what the optimiser does."""
from playwright.sync_api import sync_playwright
import json, os
P = json.load(open("tools/probe/user_route2.json"))
start = [p for p in P if "Birchwood" in p["a"]][0]; stops = [p for p in P if p is not start]
os.makedirs("shots", exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(); c = b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=2)
    c.add_init_script("window.__noGuide = true;")
    pg = c.new_page(); log = []; pg.on("console", lambda m: log.append(m.text))
    pg.goto("https://sandip-ios.github.io/RouteApp_Australia/?dev=dropline-dev"); pg.wait_for_timeout(2500)
    pg.click("#homeCreate"); pg.click("#createGo"); pg.wait_for_timeout(800)
    pg.evaluate("""([st, S]) => { const R = window.RP.route; localStorage.setItem('dropline.startMe', '0');
        R.start = {label: st.a, lat: st.lat, lon: st.lon};
        R.stops = S.map((p, i) => ({id: 'q' + i, label: p.a, query: p.a, lat: p.lat, lon: p.lon, geo: 'exact', status: 'pending', parcels: []}));
        window.RP.render(); }""", [start, stops])
    pg.evaluate("document.getElementById('btnOpt').click()")
    pg.wait_for_function("document.getElementById('optBadge').textContent === 'Optimised'", timeout=180000); pg.wait_for_timeout(9000)
    print("APP ORDER: " + " > ".join(s.split(",")[0] for s in pg.evaluate("window.RP.route.stops.map(s => s.label)")))
    print("APP MESSAGE:", pg.inner_text("#optMsg"))
    print("ROUTING POINTS MOVED:", pg.evaluate("window.RP.route.stops.filter(s => s.rp).map(s => s.label.split(',')[0])"))
    pg.evaluate("document.getElementById('app-main').scrollTop = 0; document.getElementById('toast').hidden = true"); pg.wait_for_timeout(500)
    pg.screenshot(path="shots/app-map.png")
    # the same plan judged three ways, using the same road table the app uses
    res = pg.evaluate("""(async () => { const R = window.RP.route, pts = [R.start].concat(R.stops);
        const coords = pts.map(p => p.lon.toFixed(6) + ',' + p.lat.toFixed(6)).join(';');
        const j = await (await fetch('https://router.project-osrm.org/table/v1/driving/' + coords + '?annotations=duration,distance')).json();
        const D = j.durations, Di = j.distances, names = pts.map(p => p.label.split(',')[0]);
        const out = {};
        for (const [k, w] of [['time only', 0], ['time + 40 s/km', 0.04], ['time + 90 s/km', 0.09], ['distance only', 1000]]){
          const C = D.map((r, i) => r.map((v, jj) => (w >= 1000 ? 0 : v) + (w >= 1000 ? 1 : w) * Di[i][jj]));
          const s = window.RP.solve(C, null); let t = 0, d = 0, prev = 0; for (const x of s.order){ t += D[prev][x]; d += Di[prev][x]; prev = x; }
          out[k] = Math.round(t) + ' s, ' + Math.round(d) + ' m: ' + s.order.map(x => names[x]).join(' > '); }
        return out; })()""")
    for k, v in res.items(): print(f"BEST BY {k}: {v}")
    b.close()
