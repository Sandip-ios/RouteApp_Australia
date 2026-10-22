"""Drive the Dropline Android app inside an emulator: scan 7 photographed run-sheet pages with the app's
real on-device text recognition, record timings and results, and take screenshots.
Usage: python3 drive.py <apk> <pages-dir> <out-dir>"""
import base64, io, json, os, re, subprocess, sys, time
from PIL import Image
from playwright.sync_api import sync_playwright

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
    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        pg = None
        for _ in range(30):
            pages = [x for c in br.contexts for x in c.pages]
            pg = next((x for x in pages if "localhost" in x.url), None)
            if pg: break
            time.sleep(1)
        if not pg: raise SystemExit("App page not found")
        pg.wait_for_selector("#btnScan", timeout=60000)
        say("app loaded:", pg.inner_text(".brand"))
        native = pg.evaluate("!!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform())")
        say("running as Android app:", native)
        files = sorted(f for f in os.listdir(PAGES) if f.endswith(".jpg"))
        # 1. raw text recognition per page, same image size the app uses
        for f in files:
            im = Image.open(os.path.join(PAGES, f)).convert("RGB"); k = min(1, 2400 / max(im.size))
            im = im.resize((round(im.width*k), round(im.height*k))); buf = io.BytesIO(); im.save(buf, "JPEG", quality=92)
            uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
            r = pg.evaluate("""async (img) => { const C = window.Capacitor; const P = (C.Plugins && C.Plugins.TextScan) || C.registerPlugin('TextScan');
                const t0 = performance.now(); const r = await P.recognize({image: img}); r.roundTripMs = Math.round(performance.now() - t0); return r; }""", uri)
            say(f"{f}: ML Kit {r.get('ms')} ms on device, {r.get('roundTripMs')} ms including transfer, {len(r.get('lines', []))} lines")
            results["raw"].append({"file": f, **r})
        # 2. the real scan flow, page by page, as a courier would use it
        pg.click("#btnScan"); pg.wait_for_selector("#scanApp", state="visible", timeout=10000)
        for i, f in enumerate(files):
            data = base64.b64encode(open(os.path.join(PAGES, f), "rb").read()).decode()
            t0 = time.time()
            pg.evaluate("""async (d) => { const b = await (await fetch('data:image/jpeg;base64,' + d)).blob();
                const dt = new DataTransfer(); dt.items.add(new File([b], 'page.jpg', {type:'image/jpeg'}));
                const inp = document.getElementById('scanGallery'); inp.files = dt.files; inp.dispatchEvent(new Event('change', {bubbles:true})); }""", data)
            pg.wait_for_function("document.querySelectorAll('.srow').length > 0 || /Could not|No delivery/.test(document.getElementById('scanMsg').textContent)", timeout=60000)
            secs = round(time.time() - t0, 1)
            rows = pg.evaluate("[...document.querySelectorAll('.srow')].map(e => ({cls: e.className, head: e.querySelector('.srow-h').innerText, value: e.querySelector('.sinput').value}))")
            msg = pg.inner_text("#scanMsg")
            say(f"page {i+1}: {secs} s in app — {msg}")
            results["pages"].append({"page": i+1, "seconds": secs, "message": msg, "rows": rows})
            if i == 0:
                screencap("02-page1-review.png")
                pg.evaluate("document.querySelector('#scanSheet .sheet').scrollTop = 900"); time.sleep(1); screencap("03-page1-review-lower.png")
            if i < len(files) - 1: pg.click("#scanNext")
        pg.click("#scanFinish"); time.sleep(1)
        if not pg.is_visible("#importSheet"):
            say("finish check:", pg.inner_text("#scanMsg")); screencap("04-finish-check.png"); pg.click("#scanFinish")
        try:
            pg.wait_for_function("document.getElementById('impStatusTxt').textContent.startsWith('Done')", timeout=240000)
        except Exception as e:
            say("locations not finished in time")
        say("import:", pg.inner_text("#impStatusTxt"))
        screencap("05-import-done.png"); pg.click("#closeImport"); time.sleep(3); screencap("06-route-map.png")
        results["stops"] = pg.evaluate("window.RP.route.stops.map(s => ({label: s.label, geo: s.geo, parcels: s.parcels.map(p => p.seq)}))")
        say("stops in route:", len(results["stops"]))
except SystemExit as e:
    say("STOPPED:", e)
except Exception as e:
    say("ERROR:", repr(e)); screencap("99-error.png")
finally:
    json.dump(results, open(os.path.join(OUT, "results.json"), "w"))
    open(os.path.join(OUT, "log.txt"), "w").write("\n".join(log))
