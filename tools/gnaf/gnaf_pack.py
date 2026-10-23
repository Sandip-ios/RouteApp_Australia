"""Compact per-postcode address files (format v2), about 3x smaller than v1.

geo/au/<postcode>.json
  {"v":2, "st":"NSW", "ls":{"HUME":"ACT"},            # state; "ls" only for suburbs in a different state
   "s":{"JOHN STREET|BURNSIDE": "c|n;n,dy,dx;n;..."}}  # c = centre "lat,lon" in 1/100000 degree
Each address: house number, then its point as an offset from the street centre (1/100000 degree, about 1 m).
A number with no offset sits at the same point as the one before it (e.g. 202-208 or several numbers on one lot).
"""
import json, os

def enc_street(nums):
    """nums: {"12": [lat, lon], ...} (insertion order kept) -> (centre [lat, lon], encoded string)"""
    pts = list(nums.values())
    clat = round(sum(p[0] for p in pts) / len(pts) * 1e5); clon = round(sum(p[1] for p in pts) / len(pts) * 1e5)
    parts, prev = [], None
    for n, (lat, lon) in nums.items():
        q = (round(lat * 1e5) - clat, round(lon * 1e5) - clon)
        parts.append(n if q == prev else f"{n},{q[0]},{q[1]}"); prev = q
    return [clat / 1e5, clon / 1e5], f"{clat},{clon}|" + ";".join(parts)

def write_pc(path, state, streets, loc_state):
    """streets: {"STREET|LOC": {num: [lat, lon]}}; loc_state: {LOC: state}. Merges with an existing file (postcodes across a state border)."""
    out = {"v": 2, "st": state, "ls": {}, "s": {}}
    if os.path.exists(path):
        old = json.load(open(path)); out["s"].update(old["s"]); out["ls"].update(old.get("ls", {}))
        if old["st"] != state:   # keep the first state as default; mark this state's suburbs
            for k in streets: out["ls"][k.split("|")[1]] = state
            state = old["st"]; out["st"] = state
    for loc, s in loc_state.items():
        if s != out["st"]: out["ls"][loc] = s
    centres = {}
    for k, nums in streets.items():
        c, e = enc_street(nums); out["s"][k] = e; centres[k] = c
    if not out["ls"]: del out["ls"]
    with open(path, "w") as fh: json.dump(out, fh, separators=(",", ":"))
    return centres

def dec_street(e):
    head, _, body = e.partition("|"); clat, clon = map(int, head.split(","))
    nums, prev = {}, (0, 0)
    for t in body.split(";") if body else []:
        f = t.split(",")
        if len(f) == 3: prev = (int(f[1]), int(f[2]))
        nums[f[0]] = [(clat + prev[0]) / 1e5, (clon + prev[1]) / 1e5]
    return [clat / 1e5, clon / 1e5], nums
