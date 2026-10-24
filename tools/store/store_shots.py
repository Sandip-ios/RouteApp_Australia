"""App Store screenshots, iPhone 6.9-inch (1320 x 2868)."""
from playwright.sync_api import sync_playwright
import os
SITE = "https://sandip-ios.github.io/RouteApp_Australia/"
OUT = "shots"; os.makedirs(OUT, exist_ok=True); errs = []
HIDE = "document.getElementById('toast').hidden = true;"
with sync_playwright() as p:
    b = p.chromium.launch()
    c = b.new_context(viewport={"width":440,"height":956}, is_mobile=True, has_touch=True, device_scale_factor=3, geolocation={"latitude":-33.8150,"longitude":151.0030}, permissions=["geolocation"]); c.add_init_script("window.__noGuide = true;")
    pg = c.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(SITE); pg.wait_for_timeout(1500)
    for name, n_del in [("Thursday run · Parramatta", 25), ("Friday run · Westmead", 14), ("Monday run · Parramatta", None)]:
        pg.click("#homeCreate"); pg.fill("#createName", name); pg.click("#createGo"); pg.wait_for_timeout(300)
        if n_del is not None:
            pg.evaluate("window.RP.loadSample()"); pg.wait_for_timeout(9000)
            pg.evaluate(f"window.RP.route.stops.slice(0, {n_del}).forEach((s, i) => {{ s.status = i === 3 ? 'failed' : 'delivered'; s.doneAt = Date.now(); }}); window.RP.render()")
            pg.click("#btnRouteMenu"); pg.click("#menuClose")
        pg.click("#btnRoutes"); pg.wait_for_timeout(200)
        if pg.is_hidden("#home"): pg.click("#btnRoutes")
        pg.wait_for_timeout(300)
    pg.wait_for_timeout(1800); pg.evaluate(HIDE); pg.screenshot(path=f"{OUT}/1-routes.png")
    # newest route (top): load stops and optimise
    pg.click("#routeList .rcard:nth-child(1) .ro"); pg.wait_for_timeout(600)
    pg.evaluate("window.RP.loadSample()"); pg.wait_for_timeout(9000)
    pg.evaluate("window.RP.route.stops[0].notes = 'Front door · Big box'; window.RP.route.stops[0].qty = 2; window.RP.render()")
    pg.click("#btnOpt"); pg.wait_for_function("document.getElementById('optBadge').textContent === 'Optimised'", timeout=120000); pg.wait_for_timeout(6000)
    pg.evaluate("document.getElementById('app-main').scrollTop = 0;" + HIDE); pg.wait_for_timeout(300); pg.screenshot(path=f"{OUT}/2-optimised-map.png")
    pg.click('#routeTabs [data-view="stops"]'); pg.wait_for_timeout(1500); pg.evaluate("document.getElementById('app-main').scrollTop = 260;" + HIDE); pg.wait_for_timeout(300); pg.screenshot(path=f"{OUT}/3-stops.png")
    pg.click('#routeTabs [data-view="map"]'); pg.wait_for_timeout(600)
    pg.evaluate("document.getElementById('navSim').checked = true; window.__simSpeed = 2")
    pg.click("#nextGo"); pg.wait_for_timeout(9000); pg.evaluate(HIDE); pg.screenshot(path=f"{OUT}/4-navigation.png")
    pg.click("#navBack"); pg.wait_for_timeout(400)
    pg.evaluate("window.RP.route.stops.forEach((s, i) => { s.status = i === 6 ? 'failed' : 'delivered'; if (i === 6) s.reason = 'No one home'; s.doneAt = Date.now() - (25 - i) * 9 * 60000; }); window.RP.route.stops[0].status = 'pending'")
    pg.evaluate("window.RP.setStatus(window.RP.route.stops[0].id, 'delivered')"); pg.wait_for_timeout(1300); pg.evaluate(HIDE); pg.screenshot(path=f"{OUT}/5-run-complete.png")
    pg.click("#repClose"); pg.click("#btnRoutes"); pg.wait_for_timeout(300)
    if pg.is_hidden("#home"): pg.click("#btnRoutes")
    pg.click("#btnSettings"); pg.wait_for_timeout(900); pg.screenshot(path=f"{OUT}/6-settings.png")
    print("errors:", errs)
    b.close()
