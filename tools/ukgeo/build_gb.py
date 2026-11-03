"""Build compact UK address files from free open data, in the same layout as the Australian ones (geo/au).

Sources (both free):
  - OS Code-Point Open (Open Government Licence): the point of every Great Britain postcode.
  - OpenStreetMap (ODbL): house numbers and street names (also Northern Ireland postcodes, which Code-Point does not cover).

Usage: python3 build_gb.py <codepoint.zip> <filtered.osm.pbf> [more.osm.pbf ...] <out-dir>
Output (in <out>/gb/):
  <DISTRICT>.json      e.g. SW1A.json: {"v":2, "cc":"GB", "st":"SW", "town":"London",
                         "s": {"HIGH STREET|LONDON": "c|n;n,dy,dx;..."},  (same street encoding as geo/au)
                         "p": "clat,clon|1AA,dy,dx;1AB,dy,dx"}         (every full postcode in the district)
  streets-<area>.json  type-ahead street list per postcode area (sw, e, m, ...): {"v":2, "l":[[town, district]], "s":[[street, li, lat, lon, n]]}
  index.json           {"SW1A": [lat, lon, "SW", kb]} centre of every postcode district
"""
import csv, io, json, math, os, re, sys, time, zipfile
from collections import Counter, defaultdict
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gnaf"))
from gnaf_pack import enc_street

AREA_TOWN = {"AB":"Aberdeen","AL":"St Albans","B":"Birmingham","BA":"Bath","BB":"Blackburn","BD":"Bradford","BH":"Bournemouth","BL":"Bolton","BN":"Brighton",
 "BR":"Bromley","BS":"Bristol","BT":"Belfast","CA":"Carlisle","CB":"Cambridge","CF":"Cardiff","CH":"Chester","CM":"Chelmsford","CO":"Colchester","CR":"Croydon",
 "CT":"Canterbury","CV":"Coventry","CW":"Crewe","DA":"Dartford","DD":"Dundee","DE":"Derby","DG":"Dumfries","DH":"Durham","DL":"Darlington","DN":"Doncaster",
 "DT":"Dorchester","DY":"Dudley","E":"London","EC":"London","EH":"Edinburgh","EN":"Enfield","EX":"Exeter","FK":"Falkirk","FY":"Blackpool","G":"Glasgow",
 "GL":"Gloucester","GU":"Guildford","HA":"Harrow","HD":"Huddersfield","HG":"Harrogate","HP":"Hemel Hempstead","HR":"Hereford","HS":"Isle of Lewis","HU":"Hull",
 "HX":"Halifax","IG":"Ilford","IP":"Ipswich","IV":"Inverness","KA":"Kilmarnock","KT":"Kingston upon Thames","KW":"Kirkwall","KY":"Kirkcaldy","L":"Liverpool",
 "LA":"Lancaster","LD":"Llandrindod Wells","LE":"Leicester","LL":"Llandudno","LN":"Lincoln","LS":"Leeds","LU":"Luton","M":"Manchester","ME":"Rochester",
 "MK":"Milton Keynes","ML":"Motherwell","N":"London","NE":"Newcastle upon Tyne","NG":"Nottingham","NN":"Northampton","NP":"Newport","NR":"Norwich","NW":"London",
 "OL":"Oldham","OX":"Oxford","PA":"Paisley","PE":"Peterborough","PH":"Perth","PL":"Plymouth","PO":"Portsmouth","PR":"Preston","RG":"Reading","RH":"Redhill",
 "RM":"Romford","S":"Sheffield","SA":"Swansea","SE":"London","SG":"Stevenage","SK":"Stockport","SL":"Slough","SM":"Sutton","SN":"Swindon","SO":"Southampton",
 "SP":"Salisbury","SR":"Sunderland","SS":"Southend-on-Sea","ST":"Stoke-on-Trent","SW":"London","SY":"Shrewsbury","TA":"Taunton","TD":"Galashiels","TF":"Telford",
 "TN":"Tonbridge","TQ":"Torquay","TR":"Truro","TS":"Middlesbrough","TW":"Twickenham","UB":"Southall","W":"London","WA":"Warrington","WC":"London","WD":"Watford",
 "WF":"Wakefield","WN":"Wigan","WR":"Worcester","WS":"Walsall","WV":"Wolverhampton","YO":"York","ZE":"Lerwick"}
PC_RE = re.compile(r"^([A-Z]{1,2}[0-9][A-Z0-9]?)([0-9][A-Z]{2})$")
def split_pc(p):
    m = PC_RE.match(re.sub(r"\s+", "", str(p or "")).upper()); return (m.group(1), m.group(2)) if m else None
area_of = lambda d: re.match(r"[A-Z]+", d).group(0)
up = lambda s: re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9' ]", " ", str(s or "").upper().replace("’", "'"))).replace("'", "").strip()

def load_codepoint(path):
    """{(district, inward): (lat, lon)} for Great Britain, converted from British National Grid."""
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    out, raw = {}, []
    with zipfile.ZipFile(path) as z:
        for n in z.namelist():
            if not re.search(r"Data/CSV/[a-z]+\.csv$", n, re.I): continue
            for row in csv.reader(io.TextIOWrapper(z.open(n), encoding="utf-8", errors="replace")):
                if len(row) < 4 or not row[2].strip().isdigit(): continue
                sp = split_pc(row[0])
                if not sp or row[2].strip() == "0": continue          # no grid reference
                raw.append((sp, float(row[2]), float(row[3])))
    if raw:
        lon, lat = tr.transform(np.array([r[1] for r in raw]), np.array([r[2] for r in raw]))
        for (sp, _, _), a, b in zip(raw, lat, lon): out[sp] = (round(float(a), 6), round(float(b), 6))
    return out

def parse_numbers(h):
    """'12' -> ['12'], '12a' -> ['12A'], '12-16' -> ['12','14','16'], '3;5' -> ['3','5']; flats / names -> []"""
    out = []
    for part in re.split(r"[;,]", str(h or "")):
        p = part.strip().upper().replace(" ", "")
        m = re.match(r"^(\d{1,4})-(\d{1,4})$", p)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if 0 < b - a <= 20: out += [str(n) for n in range(a, b + 1, 2 if (b - a) % 2 == 0 else 1)]
            else: out.append(str(a))
        elif re.match(r"^\d{1,4}[A-Z]?$", p): out.append(p)
    return out

def read_osm(paths):
    import osmium
    addrs, roads = [], []      # addrs: (lat, lon, street, nums, postcode, city); roads: (street, [(lat, lon), ...])
    class H(osmium.SimpleHandler):
        def take(self, t, lat, lon):
            st, hn = t.get("addr:street"), t.get("addr:housenumber")
            if st and hn:
                nums = parse_numbers(hn)
                if nums: addrs.append((lat, lon, up(st), nums, t.get("addr:postcode"), t.get("addr:city") or t.get("addr:town")))
        def node(self, n):
            if "addr:housenumber" in n.tags: self.take(n.tags, n.location.lat, n.location.lon)
        def way(self, w):
            t = w.tags
            try: pts = [(nd.lat, nd.lon) for nd in w.nodes if nd.location.valid()]
            except Exception: return
            if not pts: return
            if "addr:housenumber" in t:
                self.take(t, sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
            hw = t.get("highway")
            if hw and t.get("name") and hw not in ("motorway", "motorway_link", "trunk_link", "footway", "cycleway", "path", "steps", "bridleway", "track", "proposed", "construction", "platform", "corridor"):
                roads.append((up(t.get("name")), pts[:: max(1, len(pts) // 8)]))
    for p in paths:
        t0 = time.time(); H().apply_file(p, locations=True, idx="flex_mem")
        print(f"read {p}: {len(addrs)} addresses, {len(roads)} roads so far, {time.time()-t0:.0f} s", flush=True)
    return addrs, roads

def main():
    cp_zip, pbfs, OUT = sys.argv[1], sys.argv[2:-1], sys.argv[-1]
    GB = os.path.join(OUT, "gb"); os.makedirs(GB, exist_ok=True)
    t0 = time.time(); units = load_codepoint(cp_zip); print(f"Code-Point: {len(units)} postcodes, {time.time()-t0:.0f} s", flush=True)
    addrs, roads = read_osm(pbfs)

    # Northern Ireland (and any postcode missing from Code-Point): centre of the OSM addresses that carry that postcode
    extra = defaultdict(list)
    for lat, lon, _, _, pc, _ in addrs:
        sp = split_pc(pc)
        if sp and sp not in units: extra[sp].append((lat, lon))
    for sp, pts in extra.items():
        if len(pts) >= 1: units[sp] = (round(sum(p[0] for p in pts) / len(pts), 6), round(sum(p[1] for p in pts) / len(pts), 6))
    print(f"postcodes incl. OSM-only (mainly Northern Ireland): {len(units)}", flush=True)

    keys = list(units.keys()); P = np.array([units[k] for k in keys])
    K = math.cos(math.radians(54)); tree = cKDTree(np.c_[P[:, 0], P[:, 1] * K])
    def nearest(lat, lon): d, i = tree.query([lat, lon * K]); return keys[i], d * 111000

    files = defaultdict(lambda: defaultdict(dict))    # district -> street -> {num: [lat, lon]}
    road_pts = defaultdict(lambda: defaultdict(list))  # district -> street -> [(lat, lon)]
    towns = defaultdict(Counter)
    kept = far = 0
    for lat, lon, st, nums, pc, city in addrs:
        sp = split_pc(pc)
        if not sp:
            sp, d = nearest(lat, lon)
            if d > 3000: far += 1; continue          # not near any postcode (outside the UK)
        dist = sp[0]
        if city: towns[dist][up(city)] += 1
        for n in nums: files[dist][st].setdefault(n, [round(lat, 6), round(lon, 6)])
        kept += 1
    print(f"addresses kept {kept}, skipped (far from any postcode) {far}", flush=True)
    for st, pts in roads:
        for lat, lon in pts:
            sp, d = nearest(lat, lon)
            if d < 1500: road_pts[sp[0]][st].append((lat, lon))

    by_dist = defaultdict(dict)
    for (dist, inw), p in units.items(): by_dist[dist][inw] = p
    index, area_streets = {}, defaultdict(list)
    for dist, upts in sorted(by_dist.items()):
        area = area_of(dist)
        tc = towns[dist].most_common(1)
        town = tc[0][0].title() if tc and tc[0][1] >= 5 else AREA_TOWN.get(area, area)
        TOWN = up(town)
        lat0 = round(sum(p[0] for p in upts.values()) / len(upts) * 1e5); lon0 = round(sum(p[1] for p in upts.values()) / len(upts) * 1e5)
        pstr = f"{lat0},{lon0}|" + ";".join(f"{inw},{round(p[0]*1e5)-lat0},{round(p[1]*1e5)-lon0}" for inw, p in sorted(upts.items()))
        s = {}
        streets = set(files[dist]) | set(road_pts[dist])
        for st in sorted(streets):
            nums = files[dist].get(st, {})
            if nums:
                c, e = enc_street(nums)
            else:
                pts = road_pts[dist][st]; c = [sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)]
                e = f"{round(c[0]*1e5)},{round(c[1]*1e5)}|"
            s[f"{st}|{TOWN}"] = e
            area_streets[area].append([st, town, dist, round(c[0], 4), round(c[1], 4), len(nums)])
        path = os.path.join(GB, f"{dist}.json")
        json.dump({"v": 2, "cc": "GB", "st": area, "town": town, "s": s, "p": pstr}, open(path, "w"), separators=(",", ":"))
        index[dist] = [round(lat0 / 1e5, 4), round(lon0 / 1e5, 4), area, round(os.path.getsize(path) / 1024)]
    for area, rows in area_streets.items():
        rows.sort(key=lambda r: (r[0], r[2]))
        ls = sorted({(r[1], r[2]) for r in rows}); li = {l: i for i, l in enumerate(ls)}
        json.dump({"v": 2, "l": [list(l) for l in ls], "s": [[r[0], li[(r[1], r[2])], r[3], r[4], r[5]] for r in rows]},
                  open(os.path.join(GB, f"streets-{area.lower()}.json"), "w"), separators=(",", ":"))
    json.dump(index, open(os.path.join(GB, "index.json"), "w"), separators=(",", ":"))
    n_num = sum(len(v) for f in files.values() for v in f.values())
    size = sum(os.path.getsize(os.path.join(GB, f)) for f in os.listdir(GB))
    print(f"done: {len(index)} districts, {len(area_streets)} areas, {n_num} house numbers, {size/1e6:.1f} MB, {time.time()-t0:.0f} s", flush=True)

if __name__ == "__main__":
    main()
