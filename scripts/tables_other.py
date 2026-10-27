# Tabeller for andre idretter enn fotball, fra ligaenes og forbundenes egne tabellsider (Noah 2026-10-27).
# Kjøres hver time etter update_data.py: python3 scripts/tables_other.py index.html
# Skriver inn i const TABLES med samme radform som fotball: [navn, kamper, vunnet, uavgjort, tapt, for, mot, poeng],
# pluss "sport" og "cols" så siden kan vise riktige kolonnenavn. For volleyball er for/mot vunne og tapte sett.
# Kilder:
#  - Svensk ishockey (SHL, HockeyAllsvenskan, Hockeyettan Norra/Södra, SDHL): stats.swehockey.se (T = uavgjort etter full tid)
#  - Svensk håndball (Handbollsligan herrer og damer): handbollsligan.se/<herr|dam>/tabell/
#  - Dansk håndball (Herreligaen, Kvindeligaen, 1. division herrer og kvinder): tophaandbold.dk/stillinger/<liga>
#  - Dansk volleyball (Volleyligaen herrer og kvinder): volleyligaen.dk/<herrer|kvinder>/stilling/
#  - Norsk ishockey (EliteHockey Ligaen): regnet ut fra Norges Ishockeyforbunds egne kamper i data/hockey_no.json
#    (3 poeng for seier på ordinær tid, 2 etter forlengning/straffer, 1 for tap etter forlengning/straffer)
#  - Curling (Sparebank 1 Gudbrandsdal-serien i Lillehammer, tre divisjoner): curlingresultater.no, Curlingforbundets resultatside.
#    Seier etter ekstra omgang (VT/TT) telles som seier/tap; for/mot er poeng (stein)
import datetime, html as H, json, os, re, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixtures_other import get, matcher, SWEHOCKEY, TOPH, fix_enc

def cells(r): return [" ".join(H.unescape(re.sub(r"<[^>]+>", " ", x)).split()) for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
def num(x):
    m = re.search(r"-?\d+", x or ""); return int(m.group()) if m else 0
def pair(x):
    m = re.search(r"(\d+)\s*[-:]\s*(\d+)", x or ""); return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def swehockey(sid):
    """{seksjon: rader}. Første tabell på siden er hovedtabellen; Hockeyettan har én per avdeling."""
    s = get(f"https://stats.swehockey.se/ScheduleAndResults/Standings/{sid}")
    if not s: return {}
    out, cur = {}, None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        c = cells(r)
        if len(c) == 1 and c[0]: cur = c[0]; continue
        if len(c) >= 9 and c[0].isdigit() and cur:
            gf, ga = pair(c[6])
            out.setdefault(cur, []).append([c[1], num(c[2]), num(c[3]), num(c[4]), num(c[5]), gf, ga, num(c[8])])
    return out

def handbollsligan(path):
    s = get(f"https://handbollsligan.se/{path}/tabell/")
    if not s: return []
    rows = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        c = cells(r)
        if len(c) >= 9 and c[0].isdigit():
            gf, ga = pair(c[7]); rows.append([c[2], num(c[3]), num(c[4]), num(c[5]), num(c[6]), gf, ga, num(c[8])])
    return rows

def tophaandbold(slug):
    s = get(f"https://tophaandbold.dk/stillinger/{slug}")
    if not s: return []
    rows = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        c = cells(r)
        if len(c) >= 8 and c[0].isdigit():
            gf, ga = pair(c[6]); rows.append([c[1], num(c[2]), num(c[3]), num(c[4]), num(c[5]), gf, ga, num(c[7])])
    return rows

def volleyligaen(path):
    s = get(f"https://volleyligaen.dk/{path}/stilling/")
    if not s: return []
    rows = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        c = cells(r)
        if len(c) >= 8 and c[0].isdigit():
            sw, sl = pair(c[5]); rows.append([fix_enc(c[1]), num(c[2]), num(c[3]), 0, num(c[4]), sw, sl, num(c[7])])
    # Siden kan liste samme tabell flere ganger (hjemme/borte); første forekomst gjelder
    seen, out = set(), []
    for r in rows:
        if r[0] in seen: break
        seen.add(r[0]); out.append(r)
    return out

def hockey_no(now):
    """Tabell regnet ut fra spilte kamper. Mangler en spilt kamp forlengningsflagg, lages ingen tabell (heller ingen enn feil)."""
    try: games = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "hockey_no.json")))["games"]
    except Exception: return []
    T = {}
    for g in games:
        when, h, a, hs, as_ = g[:5]; ot = g[5] if len(g) > 5 else None
        if hs is None or as_ is None or when > now: continue
        if ot is None: print("  EliteHockey Ligaen: mangler forlengning for", when, h, a); return []
        for team, gf, ga in ((h, hs, as_), (a, as_, hs)):
            r = T.setdefault(team, [team, 0, 0, 0, 0, 0, 0, 0]); r[1] += 1; r[5] += gf; r[6] += ga
            if ot: r[3] += 1; r[7] += 2 if gf > ga else 1
            elif gf > ga: r[2] += 1; r[7] += 3
            else: r[4] += 1
    return sorted(T.values(), key=lambda r: (-r[7], -(r[5] - r[6]), -r[5], r[0]))

CURL = "https://www.curlingresultater.no/nb/tournaments/sparebank-1-gudbrandsdal-serien"
def curling_gbs(n):
    s = get(f"{CURL}/pools/{n}-divisjon-sparebank-1-gudbrandsdal-serien")
    if not s: return []
    rows = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        c = cells(r)
        if len(c) >= 9 and re.match(r"\d+\.?$", c[0]):
            pf, pa = pair(c[7].replace("–", "-")); w, l = num(c[2]) + num(c[3]), num(c[4]) + num(c[5])
            rows.append([c[1], w + l, w, 0, l, pf, pa, num(c[8])])
    return rows

COLS = {"Ishockey": "hockey", "Håndball": "handball", "Volleyball": "volley", "Curling": "curling"}
def put(T, fan, div, sport, c, rows, url):
    clubs = [k for k in fan if k["div"] == div and k["sport"] == sport and k["c"] == c]
    if len(rows) < 4 or not clubs: print(f"  {div}: ingen tabell ({len(rows)} rader)"); return
    m = matcher(clubs, [r[0] for r in rows])
    name = {n: next(k["n"] for k in clubs if k["id"] == ids[0]) for n, ids in m.items()}
    T[div] = {"c": c, "sport": sport, "cols": COLS[sport], "src": url.split("/")[2], "url": url,
              "rows": [[name.get(r[0], r[0])] + r[1:] for r in rows], "at": datetime.date.today().isoformat()}
    print(f"  {div}: {len(rows)} lag, {len(m)} koblet")

if __name__ == "__main__":
    HTML = sys.argv[1]
    page = open(HTML, encoding="utf-8").read()
    src = page[page.index("const FAN = ["):page.index("].map(([id, c, n, sport, city")]
    fan = [dict(id=r[0], c=r[1], n=r[2], sport=r[3], div=r[8] if len(r) > 8 else "") for r in
           (json.loads(l.strip().rstrip(",")) for l in src.split("\n") if l.strip().startswith('["'))]
    i = page.index("const TABLES = "); j = page.index(";\n", i)
    T = json.loads(page[i + 15:j])
    for comp, sid in SWEHOCKEY.items():
        url = f"https://stats.swehockey.se/ScheduleAndResults/Standings/{sid}"
        secs = swehockey(sid)
        if comp == "Hockeyettan":
            for avd in ("Norra", "Södra"):
                put(T, fan, f"Hockeyettan, {avd}", "Ishockey", "SE", next((v for k, v in secs.items() if avd in k), []), url)
        else: put(T, fan, comp, "Ishockey", "SE", next(iter(secs.values()), []), url)
    for div, path in (("Handbollsligan", "herr"), ("Handbollsligan dam", "dam")):
        put(T, fan, div, "Håndball", "SE", handbollsligan(path), f"https://handbollsligan.se/{path}/tabell/")
    for div, slug in TOPH.items():
        put(T, fan, div, "Håndball", "DK", tophaandbold(slug), f"https://tophaandbold.dk/stillinger/{slug}")
    put(T, fan, "EliteHockey Ligaen", "Ishockey", "NO", hockey_no(datetime.datetime.now(ZoneInfo("Europe/Oslo")).strftime("%Y-%m-%dT%H:%M")), "https://live.hockey.no/")
    for n in (1, 2, 3):
        put(T, fan, f"Gudbrandsdal-serien, {n}. divisjon", "Curling", "NO", curling_gbs(n), f"{CURL}/pools/{n}-divisjon-sparebank-1-gudbrandsdal-serien")
    for div, path in (("Volleyligaen", "herrer"), ("Volleyligaen kvinder", "kvinder")):
        put(T, fan, div, "Volleyball", "DK", volleyligaen(path), f"https://volleyligaen.dk/{path}/stilling/")
    page = page[:i + 15] + json.dumps(T, ensure_ascii=False, separators=(",", ":")) + page[j:]
    open(HTML, "w", encoding="utf-8").write(page)
