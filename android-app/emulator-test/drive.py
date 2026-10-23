"""Drive the Dropline Android app inside an emulator: scan 7 photographed run-sheet pages with the app's
real on-device text recognition, record timings and results, and take screenshots.
Usage: python3 drive.py <apk> <pages-dir> <out-dir>"""
import base64, io, json, os, re, subprocess, sys, time
from PIL import Image
import urllib.request, websocket

APK, PAGES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)
def adb(*args, check=True):
    r = subprocess.run(["adb", *args], capture_output=True, text=True, timeout=300)
    if check and r.returncode: say("adb", args, "failed:", r.stderr.strip())
    return r.stdout
def screencap(name):
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout)

results = {"pages": [], "raw": []}
try:
    say("installing", APK); say(adb("install", "-r", APK).strip())
    for perm in ["ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "CAMERA", "POST_NOTIFICATIONS"]: adb("shell", "pm", "grant", "au.dropline.routeplanner", "android.permission." + perm, check=False)
    adb("emu", "geo", "fix", "138.6406", "-34.9395", check=False)      # put the emulator in Burnside, Adelaide (near the test stops)
    adb("shell", "am", "start", "-n", "au.dropline.routeplanner/.MainActivity")
    sock = ""
    for _ in range(60):
        time.sleep(2)
        m = re.search(r"@?(webview_devtools_remote_\d+)", adb("shell", "cat", "/proc/net/unix", check=False))
        if m: sock = m.group(1); break
    if not sock: raise SystemExit("WebView debugging socket not found")
    adb("forward", "tcp:9222", "localabstract:" + sock)
    time.sleep(8); screencap("01-app-start.png")
    targets = []
    for _ in range(30):
        try: targets = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=10))
        except Exception: targets = []
        if any(t.get("type") == "page" and re.search(r"localhost|github\.io|offline\.html", t.get("url","")) for t in targets): break
        time.sleep(1)
    t = next((t for t in targets if t.get("type") == "page" and re.search(r"localhost|github\.io|offline\.html", t.get("url",""))), None)
    if not t: raise SystemExit("App page not found: " + json.dumps(targets)[:300])
    ws = websocket.create_connection(t["webSocketDebuggerUrl"], timeout=300, suppress_origin=True, max_size=None) if False else websocket.create_connection(t["webSocketDebuggerUrl"], timeout=300, suppress_origin=True)
    msg_id = [0]
    def ev(expr):
        msg_id[0] += 1; mid = msg_id[0]
        ws.send(json.dumps({"id": mid, "method": "Runtime.evaluate", "params": {"expression": expr, "awaitPromise": True, "returnByValue": True}}))
        while True:
            m = json.loads(ws.recv())
            if m.get("id") == mid: break
        r = m.get("result", {})
        if r.get("exceptionDetails"): raise RuntimeError("page error: " + json.dumps(r["exceptionDetails"])[:400])
        return r.get("result", {}).get("value")
    def wait_for(cond, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if ev("!!(" + cond + ")"): return True
            except RuntimeError: pass
            time.sleep(0.25)
        raise RuntimeError("timed out waiting for " + cond[:80])
    click = lambda sel: ev("document.querySelector(%s).click()" % json.dumps(sel))
    visible = lambda sel: ev("(() => { const e = document.querySelector(%s); return !!e && !e.closest('[hidden]') && e.offsetParent !== null; })()" % json.dumps(sel))
    text = lambda sel: ev("document.querySelector(%s).innerText" % json.dumps(sel))
    if ev("location.href").startswith("file:") or ev("/offline/.test(location.href) || document.title.includes('no internet')"):
        say("app opened without internet:", ev("location.href"), "| page:", ev("document.title")); screencap("01a-offline-page.png")
        for _ in range(12):
            try:
                if ev("!!window.RP"): break
                ev("document.getElementById('again') && document.getElementById('again').click(); true")
            except Exception: pass
            time.sleep(10)
    wait_for("document.getElementById('homeCreate') && window.RP", 120)
    ev("document.getElementById('guide') && !document.getElementById('guide').hidden && document.getElementById('gSkip').click(); true")
    say("page:", ev("location.href"))
    screencap("01b-routes-home.png")
    ev("document.getElementById('homeCreate').click(); document.getElementById('createName').value = 'Emulator test run'; document.getElementById('createGo').click(); true")
    wait_for("document.getElementById('home').hidden", 10); say("route created:", text("#routeTitle").replace("\n", " "))
    say("app loaded:", text(".brand").replace("\n", " "))
    say("running as Android app:", ev("!!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())"))
    files = sorted(f for f in os.listdir(PAGES) if f.endswith(".jpg"))
    # 1. raw text recognition per page, same image size the app uses
    for size, f in [(sz, f) for sz in (1800,) for f in files]:
        im = Image.open(os.path.join(PAGES, f)).convert("RGB"); k = min(1, size / max(im.size))
        im = im.resize((round(im.width*k), round(im.height*k))); buf = io.BytesIO(); im.save(buf, "JPEG", quality=92)
        uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        r = ev("""(async () => { const C = window.Capacitor; const P = (C.Plugins && C.Plugins.TextScan) || C.registerPlugin('TextScan');
            const t0 = performance.now(); const r = await P.recognize({image: %s}); r.roundTripMs = Math.round(performance.now() - t0); return r; })()""" % json.dumps(uri))
        say(f"{f} at {size}px: ML Kit {r.get('ms')} ms on device, {r.get('roundTripMs')} ms including transfer, {len(r.get('lines', []))} lines")
        results["raw"].append({"file": f, "size": size, **r})
    # 2. the real scan flow, page by page, as a courier would use it
    ev("window.__errs = []; window.addEventListener('error', e => window.__errs.push(String(e.message))); true")
    ev("document.getElementById('btnScan').dispatchEvent(new MouseEvent('click', {bubbles:true})); true")
    try: wait_for("!document.getElementById('scanSheet').hidden && !document.getElementById('scanApp').hidden", 15)
    except Exception:
        say("scan screen did not open:", json.dumps(ev("""({sheetHidden: document.getElementById('scanSheet').hidden, appHidden: document.getElementById('scanApp').hidden,
            noAppHidden: document.getElementById('scanNoApp').hidden, errs: window.__errs, cap: !!window.Capacitor, plugins: Object.keys((window.Capacitor||{}).Plugins||{}),
            url: location.href})""")))
        raise
    for i, f in enumerate(files):
        data = base64.b64encode(open(os.path.join(PAGES, f), "rb").read()).decode()
        t0 = time.time()
        ev("""(async () => { const b = await (await fetch('data:image/jpeg;base64,' + %s)).blob();
            const dt = new DataTransfer(); dt.items.add(new File([b], 'page.jpg', {type:'image/jpeg'}));
            const inp = document.getElementById('scanGallery'); inp.files = dt.files; inp.dispatchEvent(new Event('change', {bubbles:true})); return true; })()""" % json.dumps(data))
        wait_for("!document.getElementById('scanResult').hidden || /could not|No addresses|needs the/.test(document.getElementById('scanMsg').textContent)", 90)
        if ev("!document.getElementById('scanShowAll').hidden && !document.getElementById('scanAllList').innerHTML"): click("#scanShowAll")
        secs = round(time.time() - t0, 1)
        rows = ev("[...document.querySelectorAll('.srow')].map(e => ({cls: e.className, head: e.querySelector('.srow-h').innerText, value: e.querySelector('.sinput').value}))")
        msg = text("#scanMsg")
        say(f"page {i+1}: {secs} s in app — {msg}")
        results["pages"].append({"page": i+1, "seconds": secs, "message": msg, "rows": rows})
        if i == 0:
            screencap("02-page1-review.png")
            ev("document.querySelector('#scanSheet .sheet').scrollTop = 1100"); time.sleep(1); screencap("03-page1-review-lower.png")
        if i < len(files) - 1:
            click("#scanNext"); time.sleep(0.5)
            if not ev("document.getElementById('scanResult').hidden"): click("#scanNext")
            wait_for("document.getElementById('scanResult').hidden", 10)
    click("#scanFinish"); time.sleep(0.6)
    if not ev("document.getElementById('scanSheet').hidden"): click("#scanFinish"); time.sleep(0.6)
    if not ev("document.getElementById('scanSheet').hidden"):
        say("finish check:", text("#scanMsg")); screencap("04-finish-check.png")
        if ev("!!document.getElementById('scanFinishIdle')"): click("#scanFinishIdle")
    try: wait_for("window.RP.route.stops.length > 100 && window.RP.route.stops.every(s => s.geo !== 'pending' && s.geo !== 'searching')", 300)
    except Exception: say("locations not finished in time")
    st = ev("window.RP.route.stops.map(s => s.geo)"); say("stops in route:", len(st), "| exact:", st.count("exact"), "| check pin:", st.count("street"), "| missing:", st.count("missing"))
    results["stops"] = ev("window.RP.route.stops.map(s => ({label: s.label, geo: s.geo, parcels: s.parcels.map(p => p.seq)}))")
    screencap("05-route-ready.png")
    say("next step:", text("#nextStep").replace("\n", " ")[:160] if visible("#nextStep") else "(none)")
    say("start:", ev("JSON.stringify(window.RP.route.start)"))
    # optimise (live OSRM over the internet)
    t0 = time.time(); click("#nsOpt" if visible("#nsOpt") else "#btnOpt")
    try: wait_for("/Optimised|Estimate/.test(document.getElementById('optBadge').textContent)", 240); say(f"optimised in {round(time.time()-t0,1)} s:", text("#mTime"), text("#mDist"), "|", text("#optMsg")[:120])
    except Exception: say("optimise did not finish:", text("#optMsg"))
    screencap("06-optimised.png")
    # pickup + parcel count on stop 2
    sid = ev("window.RP.route.stops[1].id")
    ev("document.querySelector('[data-tap=\"%s\"]').click(); true" % sid); time.sleep(0.5)
    ev("document.querySelector('[data-kind=\"pickup\"][data-sid=\"%s\"]').click(); true" % sid); time.sleep(0.3)
    ev("document.querySelector('[data-qty=\"1\"][data-sid=\"%s\"]').click(); true" % sid); time.sleep(0.3)
    say("pickup + parcels:", ev("JSON.stringify({kind: window.RP.route.stops[1].kind, qty: window.RP.route.stops[1].qty})"))
    # delivered -> next slides in
    ev("document.getElementById('app-main').scrollTop = 0; true")
    before = text("#nextNum"); ev("document.querySelector('#nextCard [data-next=\"delivered\"]').click(); true"); time.sleep(0.12)
    mid = ev("[document.getElementById('nextBody').className, document.getElementById('nextStamp').textContent, !document.getElementById('nextStamp').hidden]"); screencap("07-delivered-sliding.png")
    time.sleep(1); say("delivered:", before, "->", text("#nextNum"), "| mid-animation:", mid, "| then:", text("#upNext").replace("\n", " ")[:120])
    screencap("08-next-stop.png")
    # voice plugin
    say("TextToSpeech plugin:", ev("!!(window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.TextToSpeech)"))
    say("TTS speak test:", ev("""(async () => { try { const T = window.Capacitor.Plugins.TextToSpeech; const t0 = performance.now();
        await Promise.race([T.speak({text: 'Turn left onto Glynburn Road', lang: 'en-AU', rate: 1.0}), new Promise((_, r) => setTimeout(() => r(new Error('no reply in 15 s')), 15000))]);
        return 'spoke OK in ' + Math.round(performance.now() - t0) + ' ms'; } catch (e) { return 'error: ' + e.message; } })()"""))
    try: say("TTS languages:", str(ev("(async () => { try { const r = await window.Capacitor.Plugins.TextToSpeech.getSupportedLanguages(); return (r.languages || []).filter(l => /en/i.test(l)).slice(0, 8); } catch (e) { return 'error ' + e.message; } })()")))
    except Exception as e: say("TTS languages: error", e)
    # phone helper: permissions, notification, badge
    say("device helper:", ev("""(async () => { try { const D = window.Capacitor.Plugins.DroplineDevice; const p = await D.permissions();
        const n = await D.requestNotifications().catch(e => ({err: e.message})); let sent = 'not sent';
        try { await D.notify({id: 9, title: 'Dropline test', body: 'Ready for no signal'}); sent = 'sent'; } catch (e) { sent = 'error ' + e.message; }
        await D.clearBadge(); return JSON.stringify({permissions: p, request: n, notify: sent, badge: 'cleared'}); } catch (e) { return 'error: ' + e.message; } })()"""))
    try: say("notification shade:", [l.strip() for l in adb("shell", "dumpsys", "notification", "--noredact", check=False).splitlines() if "Dropline test" in l or "android.title=" in l][:4])
    except Exception as e: say("notification shade: error", e)
    # real navigation from the emulator's GPS position
    ev("window.__spoken = []; document.getElementById('nextGo').click(); true")
    try: wait_for("(window.__spoken || []).length > 0 || /km from|Turn on location/i.test(document.getElementById('navInstr').textContent)", 60)
    except Exception: pass
    time.sleep(3); say("navigation:", text("#navInstr"), "|", text("#navDist"), "|", text("#navEta"), "| spoken:", ev("JSON.stringify(window.__spoken)")[:200], "| simulate ticked:", ev("document.getElementById('navSim').checked"))
    screencap("09-navigation.png")
    click("#navBack"); time.sleep(1)
    # routes list
    click("#btnRoutes"); time.sleep(1); say("routes list:", text("#routeList").replace("\n", " ")[:160]); screencap("10-routes.png")
    say("script errors:", ev("JSON.stringify(window.__errs || [])"))
except SystemExit as e:
    say("STOPPED:", e)
except Exception as e:
    say("ERROR:", repr(e)); screencap("99-error.png")
finally:
    json.dump(results, open(os.path.join(OUT, "results.json"), "w"))
    open(os.path.join(OUT, "log.txt"), "w").write("\n".join(log))
