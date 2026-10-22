"""Build per-postcode address lookup files from G-NAF (Australia's official address file, CC BY 4.0).
Usage: python3 build_geo.py <folder with extracted *_psv.psv files> <out-dir> <STATE ...>
Output: <out>/<state>/<postcode>.json  {"s": {"STREET NAME TYPE|LOCALITY": {"12": [lat, lon], "12A": [...]}}, "c": {"STREET|LOCALITY": [lat, lon]}}"""
import glob, json, os, sys, time
import duckdb

SRC, OUT, STATES = sys.argv[1], sys.argv[2], [s.upper() for s in sys.argv[3:]] or ["SA"]
def find(state, table):
    hits = [p for p in glob.glob(os.path.join(SRC, "**", f"{state}_{table}_psv.psv"), recursive=True)]
    if not hits: raise SystemExit(f"missing {state}_{table}")
    return hits[0]

con = duckdb.connect()
for st in STATES:
    t0 = time.time()
    rd = lambda t: f"read_csv('{find(st, t)}', delim='|', header=true, all_varchar=true, quote='')"
    rows = con.execute(f"""
      SELECT a.POSTCODE AS pc,
             trim(concat_ws(' ', s.STREET_NAME, s.STREET_TYPE_CODE, s.STREET_SUFFIX_CODE)) AS street,
             l.LOCALITY_NAME AS loc,
             concat(coalesce(a.NUMBER_FIRST_PREFIX,''), a.NUMBER_FIRST, coalesce(a.NUMBER_FIRST_SUFFIX,'')) AS num,
             a.NUMBER_LAST AS num_last,
             round(CAST(g.LATITUDE AS DOUBLE), 6) AS lat, round(CAST(g.LONGITUDE AS DOUBLE), 6) AS lon,
             a.FLAT_NUMBER IS NULL AS whole
      FROM {rd('ADDRESS_DETAIL')} a
      JOIN {rd('ADDRESS_DEFAULT_GEOCODE')} g ON g.ADDRESS_DETAIL_PID = a.ADDRESS_DETAIL_PID
      JOIN {rd('STREET_LOCALITY')} s ON s.STREET_LOCALITY_PID = a.STREET_LOCALITY_PID
      JOIN {rd('LOCALITY')} l ON l.LOCALITY_PID = a.LOCALITY_PID
      WHERE a.DATE_RETIRED IS NULL AND g.DATE_RETIRED IS NULL AND a.NUMBER_FIRST IS NOT NULL AND a.POSTCODE IS NOT NULL
      ORDER BY whole DESC
    """).fetchall()
    files = {}
    for pc, street, loc, num, num_last, lat, lon, whole in rows:
        f = files.setdefault(pc, {"s": {}, "c": {}})
        key = f"{street}|{loc}"
        nums = f["s"].setdefault(key, {})
        nums.setdefault(num, [lat, lon])                       # whole-building point wins over a unit's point
        if num_last and num_last.isdigit() and num.isdigit() and 0 < int(num_last) - int(num) <= 20:
            for n in range(int(num) + 2, int(num_last) + 1, 2): nums.setdefault(str(n), [lat, lon])   # 202-208 covers 204, 206, 208
    for pc, f in files.items():
        for key, nums in f["s"].items():
            pts = list(nums.values()); f["c"][key] = [round(sum(p[0] for p in pts)/len(pts), 6), round(sum(p[1] for p in pts)/len(pts), 6)]
        d = os.path.join(OUT, st.lower()); os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{pc}.json"), "w") as fh: json.dump(f, fh, separators=(",", ":"))
    size = sum(os.path.getsize(p) for p in glob.glob(os.path.join(OUT, st.lower(), "*.json")))
    print(f"{st}: {len(rows)} addresses, {len(files)} postcodes, {size/1e6:.1f} MB, {time.time()-t0:.0f} s", flush=True)
with open(os.path.join(OUT, "README.txt"), "w") as fh:
    fh.write("Address points from G-NAF (Geocoded National Address File), © Geoscape Australia, licensed under CC BY 4.0. Built for the Dropline route planner.\n")

# postcode index: centre point of each postcode, used to search nearby suburbs first
for st in STATES:
    d = os.path.join(OUT, st.lower()); idx = {}
    for p in glob.glob(os.path.join(d, "[0-9]*.json")):
        f = json.load(open(p)); pts = list(f["c"].values())
        if pts: idx[os.path.basename(p)[:-5]] = [round(sum(x[0] for x in pts)/len(pts), 4), round(sum(x[1] for x in pts)/len(pts), 4)]
    json.dump(idx, open(os.path.join(d, "index.json"), "w"), separators=(",", ":"))
