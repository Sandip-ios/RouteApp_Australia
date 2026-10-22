"""Make look-alike courier run-sheet pages for testing photo scanning.
Real Adelaide street and suburb names, made-up house numbers and codes: no customer data.
Writes page-N.jpg (phone-photo style) and answers.csv (what each row should read)."""
import csv, math, os, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = sys.argv[1] if len(sys.argv) > 1 else "pages"
os.makedirs(OUT, exist_ok=True)
SEED = int(sys.argv[2]) if len(sys.argv) > 2 else 20261022
random.seed(SEED)
FONT = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"

STREETS = [  # (street, suburb, postcode) — public street names
 ("Banksia Street","Parkside","5063"),("Lomandra Avenue","Glenside","5065"),("Greenhill Road","Eastwood","5063"),("Hauteville Terrace","Eastwood","5063"),
 ("Markey Street","Eastwood","5063"),("Glen Osmond Road","Fullarton","5063"),("Main Avenue","Frewville","5063"),("Flemington Street","Frewville","5063"),
 ("L'Estrange Street","Glenside","5065"),("North Street","Frewville","5063"),("Florence Street","Fullarton","5063"),("Aragon Street","Fullarton","5063"),
 ("Moore Street","Fullarton","5063"),("Seaview Street","Fullarton","5063"),("Wattle Street","Fullarton","5063"),("Elinor Terrace","Glen Osmond","5064"),
 ("Portrush Road","Glen Osmond","5064"),("Ashley Avenue","Glen Osmond","5064"),("Fowlers Road","Glen Osmond","5064"),("Taminga Avenue","Glenunga","5064"),
 ("Glenunga Avenue","Glenunga","5064"),("Allinga Avenue","Glenunga","5064"),("Leroy Street","Glenunga","5064"),("Kingsley Avenue","Glenunga","5064"),
 ("Broughton Street","Glenside","5065"),("Almond Avenue","Glenside","5065"),("Sturt Avenue","Toorak Gardens","5065"),("Bolingbroke Grove","Toorak Gardens","5065"),
 ("Brandreth Street","Tusmore","5065"),("Bakewell Street","Tusmore","5065"),("Northumberland Street","Tusmore","5065"),("Kennaway Street","Tusmore","5065"),
 ("Hanson Avenue","Heathpool","5068"),("Clapton Road","Marryatville","5068"),("Hackett Terrace","Marryatville","5068"),("Dudley Road","Marryatville","5068"),
 ("Tusmore Avenue","Leabrook","5068"),("Statenborough Street","Leabrook","5068"),("Rochester Street","Leabrook","5068"),("Davenport Terrace","Hazelwood Park","5066"),
 ("Knightsbridge Road","Hazelwood Park","5066"),("Howard Terrace","Hazelwood Park","5066"),("John Street","Burnside","5066"),("Glynburn Road","Burnside","5066"),
 ("Moorcroft Court","Burnside","5066"),("Chisholm Avenue","Burnside","5066"),("Vauxhall Street","Erindale","5066"),("Godfrey Terrace","Erindale","5066"),
 ("South Terrace","Kensington Gardens","5068"),("Kensington Road","Kensington Gardens","5068"),("Hyland Terrace","Rosslyn Park","5072"),("Lanark Street","Rosslyn Park","5072"),
 ("Primrose Terrace","Rosslyn Park","5072"),("Wyfield Street","Wattle Park","5066"),("Yeltana Avenue","Wattle Park","5066"),("Carunta Street","Wattle Park","5066"),
 ("Wahroonga Avenue","Wattle Park","5066"),("Simpson Road","Wattle Park","5066"),("Penfold Road","Stonyfell","5066"),("Edinburgh Avenue","Stonyfell","5066"),
 ("Heatherbank Terrace","Stonyfell","5066"),("Eucalypt Court","Stonyfell","5066"),("Grevillea Crescent","Stonyfell","5066"),("Morland Avenue","Stonyfell","5066"),
 ("Mingara Avenue","Stonyfell","5066"),("Hallett Road","Stonyfell","5066"),("Bradfield Street","Burnside","5066"),("Lockwood Road","Burnside","5066"),
 ("Kings Avenue","Burnside","5066"),("Hill Street","Burnside","5066"),("Waterfall Gully Road","Waterfall Gully","5066"),("Finniss Terrace","Burnside","5066"),
 ("Garden Avenue","Burnside","5066"),("Russell Avenue","Hazelwood Park","5066"),("Linden Avenue","Hazelwood Park","5066"),("Dryden Avenue","Hazelwood Park","5066"),
 ("Katoomba Road","Beaumont","5066"),("Dashwood Road","Beaumont","5066"),("Bennett Avenue","Beaumont","5066"),("Devereux Road","Linden Park","5065"),
 ("Rayne Avenue","Linden Park","5065"),("Sturdee Street","Linden Park","5065"),("Hood Street","Linden Park","5065"),("Torrens Street","Linden Park","5065"),
 ("Durham Avenue","St Georges","5064"),("Craighill Road","St Georges","5064"),("Sunnyside Road","St Georges","5064"),("Snow Street","Glen Osmond","5064"),
 ("Paynter Street","Glen Osmond","5064"),("Gleneagles Road","Mount Osmond","5064"),
]
ABBR = {"Street":"St","Avenue":"Ave","Road":"Rd","Terrace":"Tce","Crescent":"Cres","Court":"Ct","Grove":"Grove"}

def make_row(seq):
    street, sub, pc = random.choice(STREETS)
    num = random.randint(1, 240)
    suffix = random.choice(["", "", "", "", "A", "B"])
    style = random.random()
    st_txt = street
    if random.random() < 0.3: st_txt = street.replace(street.split()[-1], ABBR.get(street.split()[-1], street.split()[-1]))
    if random.random() < 0.3: st_txt = st_txt.upper()
    unit = ""
    if style < 0.12: unit = f"{random.randint(1,9)}/"
    elif style < 0.20: unit = f"Unit {random.randint(1,30)} "
    sub_txt = sub if random.random() < 0.8 else f"{sub.upper()} {sub}"
    if random.random() < 0.06: sub_txt = f"None {sub}"
    printed = f"{unit}{num}{suffix} {st_txt} {sub_txt} SA {pc} AU"
    if style > 0.94: printed = f"ACME PTY LTD LEVEL 1 {num} {st_txt.upper()} {sub} SA {pc} AU"   # long, wraps
    answer = f"{num} {street}, {sub} SA {pc}"
    dims = random.choice(["26.58 CM X 21.67 CM X 2.7 CM","35.5 CM X 26.86 CM X 6.3 CM","24.7 CM X 17.3 CM X 8.1 CM","28.4 CM X 28.0 CM X 3.7 CM","43.18 CM X 28.39 CM X 7.4 CM",""])
    code = f"D5002{random.randint(7000000,7599999)}"
    track = random.choice([f"DRNFLY0000244{random.randint(10000,99999)}", f"00393580940{random.randint(100000000,199999999)}"])
    return dict(seq=seq, printed=printed, answer=answer, dims=dims, code=code, track=track)

def wrap(draw, text, font, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= width: cur = t
        else: lines.append(cur); cur = w
    lines.append(cur); return lines

def render_page(rows, page, total):
    W, H = 2550, 1850
    img = Image.new("L", (W, H), 255); d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 34); fb = ImageFont.truetype(BOLD, 44); fh = ImageFont.truetype(BOLD, 34); fs = ImageFont.truetype(FONT, 30)
    d.text((140, 120), "CourierCo", font=fb, fill=0)
    d.text((W//2 - 330, 100), "Courier Co Australia - EAST", font=fb, fill=0)
    d.text((W//2 - 380, 160), "From 2026-10-14 00:00:00.0 to 2026-10-15 00:29:00.0", font=fs, fill=0)
    d.rectangle((W-300, 90, W-180, 210), fill=0); d.rectangle((W-280, 110, W-200, 190), fill=255)
    d.text((140, 280), "ADEL1236", font=fh, fill=0); d.text((140, 325), "Route - ADEL1236", font=fh, fill=0)
    d.text((W-760, 335), f"Total number of packages : {total}", font=fh, fill=0)
    cols = [140, 560, 930, 1010, 1920, 2330, 2400]
    y = 380; d.rectangle((cols[0], y, cols[-1], y+44), fill=150)
    for x, t in zip(cols, ["Code","Tracking ID","Seq","Address","Dimensions","SIG"]): d.text((x+8, y+4), t, font=fh, fill=60)
    y += 44
    for r in rows:
        lines = wrap(d, r["printed"], f, cols[4]-cols[3]-16)
        h = 40 * len(lines) + 6
        mid = y + h/2
        d.text((cols[0]+6, mid-20), r["code"], font=f, fill=0)
        d.text((cols[1]+6, mid-20), r["track"], font=f, fill=0)
        d.text((cols[2]+10, mid-20), str(r["seq"]), font=f, fill=0)
        for i, ln in enumerate(lines): d.text((cols[3]+6, y+3+40*i), ln, font=f, fill=0)
        if r["dims"]: d.text((cols[4]+6, mid-18), r["dims"], font=ImageFont.truetype(FONT, 28), fill=0)
        for x in cols: d.line((x, y, x, y+h), fill=0, width=2)
        d.line((cols[0], y+h, cols[-1], y+h), fill=0, width=2)
        y += h
    d.line((cols[0], 424, cols[-1], 424), fill=0, width=2)
    return img

def phone_photo(img, seed):
    rnd = random.Random(seed)
    img = img.convert("RGB")
    # slight tilt and perspective, like a hand-held photo
    ang = rnd.uniform(-2.5, 2.5)
    img = img.rotate(ang, resample=Image.BICUBIC, expand=True, fillcolor=(205, 200, 190))
    W, H = img.size; dx, dy = W*0.03, H*0.03
    coeffs = find_coeffs([(0,0),(W,0),(W,H),(0,H)], [(rnd.uniform(0,dx), rnd.uniform(0,dy)), (W-rnd.uniform(0,dx), rnd.uniform(0,dy)), (W-rnd.uniform(0,dx), H-rnd.uniform(0,dy)), (rnd.uniform(0,dx), H-rnd.uniform(0,dy))])
    img = img.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC, fillcolor=(205, 200, 190))
    # uneven light and slight blur
    shade = Image.linear_gradient("L").resize((W, H)).rotate(rnd.choice([0, 90, 180, 270]))
    shade = shade.point(lambda v: 205 + v * 50 // 255)
    img = Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)), shade) if False else Image.blend(img, Image.merge("RGB", (shade, shade, shade)), 0.18)
    img = img.filter(ImageFilter.GaussianBlur(rnd.uniform(0.6, 1.2)))
    return img.resize((int(W*0.8), int(H*0.8)))

def find_coeffs(pa, pb):
    import numpy as np
    m = []
    for p1, p2 in zip(pa, pb):
        m.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0]*p1[0], -p2[0]*p1[1]])
        m.append([0, 0, 0, p1[0], p1[1], 1, -p2[1]*p1[0], -p2[1]*p1[1]])
    A = np.array(m, dtype=float); B = np.array(pb, dtype=float).reshape(8)
    return list(np.linalg.solve(A, B))

TOTAL = 166
rows = [make_row(i) for i in range(1, TOTAL + 1)]
with open(os.path.join(OUT, "answers.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["seq", "printed", "answer"]); [w.writerow([r["seq"], r["printed"], r["answer"]]) for r in rows]
for p in range(7):
    chunk = rows[p*25:(p+1)*25]
    page = render_page(chunk, p+1, TOTAL)
    phone_photo(page, SEED * 10 + p).save(os.path.join(OUT, f"page-{p+1}.jpg"), quality=85)
print("made", len(rows), "rows on 7 pages in", OUT)
