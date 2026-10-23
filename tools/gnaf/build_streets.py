"""Build the type-ahead street index from the per-postcode address files.
Usage: python3 build_streets.py <geo-dir> <state>   e.g. geo sa
Output: <geo-dir>/<state>/streets.json
  {"v":2, "l":[[locality, postcode], ...], "s":[[street, localityIndex, lat, lon, count], ...]}   one row per street in each suburb"""
import glob, json, os, sys
geo, st = sys.argv[1], sys.argv[2].lower()
rows = []
for p in sorted(glob.glob(os.path.join(geo, st, "[0-9]*.json"))):
    pc = os.path.basename(p)[:-5]; f = json.load(open(p))
    for key, nums in f["s"].items():
        street, loc = key.split("|"); c = f["c"][key]
        rows.append([street, loc, pc, round(c[0], 4), round(c[1], 4), len(nums)])
rows.sort(key=lambda r: (r[0], r[1]))
locs = sorted({(r[1], r[2]) for r in rows}); li = {l: i for i, l in enumerate(locs)}
out = os.path.join(geo, st, "streets.json")
json.dump({"v": 2, "l": [list(l) for l in locs], "s": [[r[0], li[(r[1], r[2])], r[3], r[4], r[5]] for r in rows]}, open(out, "w"), separators=(",", ":"))
print(f"{st}: {len(rows)} streets, {os.path.getsize(out)/1e6:.2f} MB")
