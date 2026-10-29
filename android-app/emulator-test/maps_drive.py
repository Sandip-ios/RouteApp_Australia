"""Emulator check: does 'Open in Google Maps' work every time (navigation menu and next-stop button), also after
coming back to DropLine? Taps are real touch events. Usage: python3 maps_drive.py <apk> <out-dir>"""
import json, os, re, subprocess, sys, time, urllib.request, websocket
APK, OUT = sys.argv[1], sys.argv[2]; os.makedirs(OUT, exist_ok=True); log = []
def say(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); log.append(s)
def adb(*args):
    return subprocess.run(["adb", *args], capture_output=True, text=True, timeout=120).stdout
def shot(name):
    open(os.path.join(OUT, name), "wb").write(subprocess.run(["adb", "exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout)
def front():
    out = adb("shell", "dumpsys", "activity", "activities")
    m = re.search(r"(?:topResumedActivity|mResumedActivity|ResumedActivity)[^\n]*?\{[^}]*? ([\w.]+)/", out); return m.group(1) if m else "?"
def connect():
    for _ in range(40):
        m = re.search(r"@?(webview_devtools_remote_\d+)", adb("shell", "cat", "/proc/net/unix"))
        if m:
            adb("forward", "tcp:9222", "localabstract:" + m.group(1))
            try:
                ts = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=10))
                t = next((t for t in ts if t.get("type") == "page" and "github.io" in t.get("url", "")), None)
                if t: return websocket.create_connection(t["webSocketDebuggerUrl"], timeout=120, suppress_origin=True, max_size=None)
            except Exception: pass
        time.sleep(2)
    raise SystemExit("no app page")
ws = None; mid = [0]
def call(method, params):
    mid[0] += 1; ws.send(json.dumps({"id": mid[0], "method": method, "params": params}))
    while True:
        m = json.loads(ws.recv())
        if m.get("id") == mid[0]: return m.get("result", {})
def ev(expr):
    r = call("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
    if r.get("exceptionDetails"): raise RuntimeError(json.dumps(r["exceptionDetails"])[:300])
    return r.get("result", {}).get("value")
def wait(cond, t=60):
    t0 = time.time()
    while time.time() - t0 < t:
        try:
            if ev("!!(" + cond + ")"): return True
        except Exception: pass
        time.sleep(0.3)
    raise RuntimeError("timeout: " + cond)
def tap(sel):
    r = ev("(() => { const e = document.querySelector(%s); if (!e) return null; e.scrollIntoView({block:'center'}); const b = e.getBoundingClientRect(); return [b.left + b.width/2, b.top + b.height/2]; })()" % json.dumps(sel))
    if not r: raise RuntimeError("no element " + sel)
    time.sleep(0.4)
    r = ev("(() => { const b = document.querySelector(%s).getBoundingClientRect(); return [b.left + b.width/2, b.top + b.height/2]; })()" % json.dumps(sel))
    pt = [{"x": r[0], "y": r[1]}]
    call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt}); call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
results = []
try:
    say(adb("install", "-r", APK).strip())
    for p in ["ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION", "POST_NOTIFICATIONS"]: adb("shell", "pm", "grant", "au.dropline.routeplanner", "android.permission." + p)
    adb("emu", "geo", "fix", "151.0040", "-33.8156")
    adb("shell", "am", "start", "-n", "au.dropline.routeplanner/.MainActivity"); time.sleep(10)
    ws = connect(); wait("window.RP && document.getElementById('homeCreate')", 120)
    say("app version:", ev("document.querySelector('.appver') && document.querySelector('.appver').textContent"))
    ev("localStorage.setItem('dropline.navapp.v1', 'google'); document.getElementById('guide') && !document.getElementById('guide').hidden && document.getElementById('gSkip').click(); true")
    ev("document.getElementById('homeCreate').click(); document.getElementById('createGo').click(); true"); time.sleep(1)
    ev("window.RP.loadSample(); window.__fastOpt = true; true"); time.sleep(4)
    ev("document.getElementById('btnOpt').click(); true"); wait("document.getElementById('optBadge').textContent === 'Optimised'", 120); time.sleep(2)
    ev("document.getElementById('optOv') && (document.getElementById('optOv').hidden = true); document.getElementById('app-main').scrollTop = 0; true")
    say("optimised; next card visible:", ev("!document.getElementById('nextCard').hidden"))
    def back_to_app(label):
        adb("shell", "am", "start", "-n", "au.dropline.routeplanner/.MainActivity"); time.sleep(4)
        fa = front(); say("  back in DropLine?", fa)
        global ws
        try: ev("1")
        except Exception: ws = connect()
    # A. the green Google Maps button on the next-stop card, 3 times
    for k in range(3):
        before = front(); tap("#nextNav"); time.sleep(5); after = front(); shot(f"card-{k+1}.png")
        ok = after not in ("au.dropline.routeplanner", "?"); results.append(("next-stop card, try %d" % (k+1), ok, after)); say("card try", k+1, ":", before, "->", after)
        back_to_app("card")
    # B. navigation menu -> Open in Google Maps, 3 times
    ev("document.getElementById('navSim').checked = true; window.__simSpeed = 1; true")
    tap("#nextGo"); wait("!document.getElementById('navScreen').hidden", 30); time.sleep(3)
    for k in range(3):
        if ev("document.getElementById('navMenu').hidden"): tap("#navMore"); time.sleep(1)
        shot(f"menu-{k+1}.png")
        before = front(); tap("#navExt"); time.sleep(5); after = front(); shot(f"menu-after-{k+1}.png")
        ok = after not in ("au.dropline.routeplanner", "?"); results.append(("navigation menu, try %d" % (k+1), ok, after)); say("menu try", k+1, ":", before, "->", after)
        back_to_app("menu")
        say("  navigation still open:", ev("!document.getElementById('navScreen').hidden"), "| menu open:", ev("!document.getElementById('navMenu') || !document.getElementById('navMenu').hidden"))
    # C. the new round maps button on the stop card, 3 times
    for k in range(3):
        before = front(); tap("#navExtCard"); time.sleep(5); after = front(); shot(f"cardbtn-{k+1}.png")
        ok = after not in ("au.dropline.routeplanner", "?"); results.append(("stop card maps button, try %d" % (k+1), ok, after)); say("card button try", k+1, ":", before, "->", after)
        back_to_app("cardbtn")
except Exception as e:
    say("ERROR", repr(e)[:400]); shot("error.png")
say("\nRESULTS"); [say(("PASS " if ok else "FAIL ") + n + " -> " + str(a)) for n, ok, a in results]
open(os.path.join(OUT, "log.txt"), "w").write("\n".join(log))
