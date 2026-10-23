"""Build compact address files for the whole of Australia from G-NAF (Australia's official address file, CC BY 4.0).
Usage: python3 build_geo.py <folder with extracted *_psv.psv files> <out-dir> <STATE ...>
Output (in <out>/au/):
  <postcode>.json        compact address points per postcode (see gnaf_pack.py)
  streets-<state>.json   type-ahead street list: {"v":2, "l":[[suburb, postcode]], "s":[[street, suburbIndex, lat, lon, count]]}
  index.json             {"postcode": [lat, lon, "STATE"]} centre of every postcode
Run one state at a time (to keep memory low); index.json is rebuilt from all postcode files at the end of each run."""
import glob, json, os, sys, time
import duckdb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gnaf_pack import write_pc

SRC, OUT, STATES = sys.argv[1], sys.argv[2], [s.upper() for s in sys.argv[3:]] or ["SA"]
AU = os.path.join(OUT, "au"); os.makedirs(AU, exist_ok=True)
def find(state, table):
    hits = glob.glob(os.path.join(SRC, "**", f"{state}_{table}_psv.psv"), recursive=True)
    if not hits: raise SystemExit(f"missing {state}_{table}")
    return hits[0]

con = duckdb.connect(); con.execute("SET memory_limit='10GB'")
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
      ORDER BY pc, whole DESC
    """).fetchall()
    files, locs = {}, {}
    for pc, street, loc, num, num_last, lat, lon, whole in rows:
        f = files.setdefault(pc, {}); locs.setdefault(pc, set()).add(loc)
        nums = f.setdefault(f"{street}|{loc}", {})
        nums.setdefault(num, [lat, lon])                       # whole-building point wins over a unit's point
        if num_last and num_last.isdigit() and num.isdigit() and 0 < int(num_last) - int(num) <= 20:
            for n in range(int(num) + 2, int(num_last) + 1, 2): nums.setdefault(str(n), [lat, lon])   # 202-208 covers 204, 206, 208
    n_rows = len(rows); del rows
    srows = []
    for pc, streets in files.items():
        centres = write_pc(os.path.join(AU, f"{pc}.json"), st, streets, {l: st for l in locs[pc]})
        for k, c in centres.items():
            street, loc = k.split("|"); srows.append([street, loc, pc, round(c[0], 4), round(c[1], 4), len(streets[k])])
    srows.sort(key=lambda r: (r[0], r[1]))
    ls = sorted({(r[1], r[2]) for r in srows}); li = {l: i for i, l in enumerate(ls)}
    sp = os.path.join(AU, f"streets-{st.lower()}.json")
    json.dump({"v": 2, "l": [list(l) for l in ls], "s": [[r[0], li[(r[1], r[2])], r[3], r[4], r[5]] for r in srows]}, open(sp, "w"), separators=(",", ":"))
    size = sum(os.path.getsize(os.path.join(AU, f"{pc}.json")) for pc in files)
    print(f"{st}: {n_rows} addresses, {len(files)} postcodes, {size/1e6:.1f} MB, streets {len(srows)} ({os.path.getsize(sp)/1e6:.1f} MB), {time.time()-t0:.0f} s", flush=True)
    del files

# postcode index: centre and state of every postcode (used to find nearby suburbs and the driver's state)
from gnaf_pack import dec_street
idx = {}
for p in glob.glob(os.path.join(AU, "[0-9]*.json")):
    f = json.load(open(p)); cs = [dec_street(e)[0] for e in f["s"].values()]
    if cs: idx[os.path.basename(p)[:-5]] = [round(sum(c[0] for c in cs)/len(cs), 4), round(sum(c[1] for c in cs)/len(cs), 4), f["st"], round(os.path.getsize(p) / 1024)]
json.dump(idx, open(os.path.join(AU, "index.json"), "w"), separators=(",", ":"))
with open(os.path.join(OUT, "README.txt"), "w") as fh:
    fh.write("Address points from G-NAF (Geocoded National Address File), © Geoscape Australia, licensed under CC BY 4.0. Built for the Dropline route planner.\n")
print("index:", len(idx), "postcodes")
