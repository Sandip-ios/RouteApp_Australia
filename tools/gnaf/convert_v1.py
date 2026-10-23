"""Convert the older SA files (geo/sa, format v1) into the compact national layout (geo/au, format v2).
Used for local testing before the national build runs. Usage: python3 convert_v1.py geo"""
import glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gnaf_pack import write_pc, dec_street
geo = sys.argv[1]; AU = os.path.join(geo, "au"); os.makedirs(AU, exist_ok=True)
srows = []
for p in sorted(glob.glob(os.path.join(geo, "sa", "[0-9]*.json"))):
    pc = os.path.basename(p)[:-5]; f = json.load(open(p))
    locs = {k.split("|")[1] for k in f["s"]}
    out = os.path.join(AU, pc + ".json")
    if os.path.exists(out): os.remove(out)
    cs = write_pc(out, "SA", f["s"], {l: "SA" for l in locs})
    for k, c in cs.items():
        st, loc = k.split("|"); srows.append([st, loc, pc, round(c[0], 4), round(c[1], 4), len(f["s"][k])])
srows.sort(key=lambda r: (r[0], r[1])); ls = sorted({(r[1], r[2]) for r in srows}); li = {l: i for i, l in enumerate(ls)}
json.dump({"v": 2, "l": [list(l) for l in ls], "s": [[r[0], li[(r[1], r[2])], r[3], r[4], r[5]] for r in srows]}, open(os.path.join(AU, "streets-sa.json"), "w"), separators=(",", ":"))
idx = {}
for p in glob.glob(os.path.join(AU, "[0-9]*.json")):
    f = json.load(open(p)); cs = [dec_street(e)[0] for e in f["s"].values()]
    idx[os.path.basename(p)[:-5]] = [round(sum(c[0] for c in cs)/len(cs), 4), round(sum(c[1] for c in cs)/len(cs), 4), f["st"], round(os.path.getsize(p) / 1024)]
json.dump(idx, open(os.path.join(AU, "index.json"), "w"), separators=(",", ":"))
size = sum(os.path.getsize(p) for p in glob.glob(os.path.join(AU, "[0-9]*.json")))
print(len(idx), "postcodes,", round(size / 1e6, 1), "MB")
