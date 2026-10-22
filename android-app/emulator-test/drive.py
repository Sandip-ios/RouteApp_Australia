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
        if any(t.get("type") == "page" and "localhost" in t.get("url","") for t in targets): break
        time.sleep(1)
    t = next((t for t in targets if t.get("type") == "page" and "localhost" in t.get("url","")), None)
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
            if ev("!!(" + cond + ")"): return True
            time.sleep(0.25)
        raise RuntimeError("timed out waiting for " + cond[:80])
    click = lambda sel: ev("document.querySelector(%s).click()" % json.dumps(sel))
    visible = lambda sel: ev("(() => { const e = document.querySelector(%s); return !!e && !e.closest('[hidden]') && e.offsetParent !== null; })()" % json.dumps(sel))
    text = lambda sel: ev("document.querySelector(%s).innerText" % json.dumps(sel))
    wait_for("document.getElementById('btnScan')")
    say("app loaded:", text(".brand").replace("\n", " "))
    say("running as Android app:", ev("!!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())"))
    files = sorted(f for f in os.listdir(PAGES) if f.endswith(".jpg"))
    # 1. raw text recognition per page, same image size the app uses
    for size, f in [(sz, f) for sz in (2400, 1600) for f in files]:
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
        wait_for("document.querySelectorAll('.srow').length > 0 || /Could not|No delivery|needs the/.test(document.getElementById('scanMsg').textContent)", 90)
        secs = round(time.time() - t0, 1)
        rows = ev("[...document.querySelectorAll('.srow')].map(e => ({cls: e.className, head: e.querySelector('.srow-h').innerText, value: e.querySelector('.sinput').value}))")
        msg = text("#scanMsg")
        say(f"page {i+1}: {secs} s in app — {msg}")
        results["pages"].append({"page": i+1, "seconds": secs, "message": msg, "rows": rows})
        if i == 0:
            screencap("02-page1-review.png")
            ev("document.querySelector('#scanSheet .sheet').scrollTop = 1100"); time.sleep(1); screencap("03-page1-review-lower.png")
        if i < len(files) - 1:
            click("#scanNext"); wait_for("document.querySelectorAll('.srow').length === 0", 10)
    click("#scanFinish"); time.sleep(1)
    if not visible("#importSheet"):
        say("finish check:", text("#scanMsg")); screencap("04-finish-check.png"); click("#scanFinish")
    try: wait_for("document.getElementById('impStatusTxt').textContent.startsWith('Done')", 300)
    except Exception: say("locations not finished in time")
    say("import:", text("#impStatusTxt"))
    screencap("05-import-done.png"); click("#closeImport"); time.sleep(3); screencap("06-route-map.png")
    results["stops"] = ev("window.RP.route.stops.map(s => ({label: s.label, geo: s.geo, parcels: s.parcels.map(p => p.seq)}))")
    say("stops in route:", len(results["stops"]))
except SystemExit as e:
    say("STOPPED:", e)
except Exception as e:
    say("ERROR:", repr(e)); screencap("99-error.png")
finally:
    json.dump(results, open(os.path.join(OUT, "results.json"), "w"))
    open(os.path.join(OUT, "log.txt"), "w").write("\n".join(log))
