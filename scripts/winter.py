# Verdenscup og mesterskap i vintersport (Noah 2026-10-26: «legg til mer vinteridrett, spesielt ski»).
# Langrenn, alpint, hopp og kombinert fra FIS sin terminliste, skiskyting fra IBU sin resultattjeneste.
# Skriver const WINTER i index.html: {at, r: [[idrett, start (UTC), sted, nasjon, øvelse, kjønn, lenke, pall, beste nordiske]]}
# Pall: [[navn, nasjon]] for de tre beste. Beste nordiske: [[plass, navn, nasjon]] for de beste fra Norden utenfor pallen.
# Bruk: python3 scripts/winter.py index.html
import datetime, html as H, json, os, re, sys, time, urllib.request
from zoneinfo import ZoneInfo

HTML = sys.argv[1]
ROOT = os.path.dirname(os.path.abspath(HTML))
CACHE = os.path.join(ROOT, "data", "vinter.json")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
NOW = datetime.datetime.now(datetime.timezone.utc)
SEASON = int(os.environ.get("SEASON") or (NOW.year + 1 if NOW.month >= 7 else NOW.year))
NORDIC = {"NOR", "SWE", "FIN", "DEN", "ISL"}
FIS = {"CC": "Langrenn", "AL": "Alpint", "JP": "Hopp", "NK": "Kombinert"}
# Lokal tid på arenaen. FIS oppgir klokkeslett i lokal tid
NAT_TZ = {"FIN": "Europe/Helsinki", "EST": "Europe/Tallinn", "USA": "America/Denver", "CAN": "America/Edmonton", "JPN": "Asia/Tokyo", "CHN": "Asia/Shanghai",
          "KOR": "Asia/Seoul", "GBR": "Europe/London", "ISL": "Atlantic/Reykjavik"}

def get(url, tries=3):
    for a in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "replace")
        except Exception: time.sleep(3 + 5 * a)
    return None
def txt(x): return [y.strip() for y in H.unescape(re.sub(r"<[^>]+>", "\n", x)).split("\n") if y.strip() and y.strip() != "-->"]
def name(n):
    # «HAGSTROEM Johanna» -> «Johanna Hagstroem»
    parts = n.split(); sur = [p for p in parts if p.isupper() and len(p) > 1]; first = [p for p in parts if p not in sur]
    cap = lambda x: "Mc" + x[2:].capitalize() if x.startswith("MC") and len(x) > 3 else x.capitalize()
    return " ".join(first + ["-".join(cap(x) for x in p.split("-")) for p in sur]) or n

cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
res = cache.setdefault("res", {})  # lenke -> [pall, beste nordiske]
evc = cache.setdefault("ev", {})   # "CC:63002" -> {"t": hentet, "r": renn}. Hentes på nytt daglig, eller hver time rundt rennhelgen

def podium(rows):
    """rows: [(plass, navn, nasjon)] -> (pall, beste nordiske utenfor pallen)"""
    ok, last = [], 0
    for r in rows:
        if not (r[0] and r[0].isdigit()): continue
        # Etter resultatlista kommer lister over dem som ikke fullførte, med startnummer først: stopp der
        if int(r[0]) < last: break
        ok.append(r); last = int(r[0])
    rows = ok
    top = [[int(p), name(n), c] for p, n, c in rows if int(p) <= 3][:5]
    nor = [[int(p), name(n), c] for p, n, c in rows if int(p) > 3 and c in NORDIC][:3]
    return top, nor

# ---------- FIS ----------
def fis_events(sector):
    out = []
    for cat in ("WC", "WSC"):
        s = get(f"https://www.fis-ski.com/DB/general/calendar-results.html?sectorcode={sector}&seasoncode={SEASON}&categorycode={cat}")
        if not s: continue
        for block in re.split(r'<div class="table-row reset-padding"', s)[1:]:
            m = re.search(r'event-details\.html\?sectorcode=\w+&eventid=(\d+)', block)
            d = re.search(r'>(\d{2}(?:-\d{2})? \w{3}(?: \d{4})?(?:-\d{2} \w{3})? \d{4})<', block)
            nat = re.search(r'flag-([A-Z]{3})', block)
            if m and nat: out.append((m.group(1), nat.group(1), cat))
    return list(dict.fromkeys(out))

def fis_races(sector, eid, nat, cat):
    s = get(f"https://www.fis-ski.com/DB/general/event-details.html?sectorcode={sector}&eventid={eid}&seasoncode={SEASON}")
    if not s: return []
    place = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S)
    place = " ".join(txt(place.group(1))) if place else ""
    place = re.sub(r"\s*\(\w{3}\)\s*$", "", place).strip()
    tz = ZoneInfo(NAT_TZ.get(nat, "Europe/Oslo"))
    out = []
    for block in re.split(r'<div class="table-row', s)[1:]:
        block = block[block.find(">") + 1:]
        rid = re.search(r'results\.html\?sectorcode=\w+&(?:amp;)?raceid=(\d+)', block)
        if not rid: continue
        t = txt(block)
        d = next((x for x in t if re.fullmatch(r"\d{1,2} [A-Z][a-z]{2}(?: \d{4})?", x)), None)
        if d and not re.search(r"\d{4}$", d):
            # Kommende renn står uten år: høstmånedene hører til året før sesongen slutter
            d += " " + str(SEASON - 1 if datetime.datetime.strptime(d.split()[1], "%b").month >= 7 else SEASON)
        tm = next((x for x in t if re.fullmatch(r"\d{2}:\d{2}", x)), None)
        if not d: continue
        cats = [x for x in t if x in ("WC", "WSC", "TRA", "SPWQ", "SPMQ", "QUA", "PRA")]
        if cats and cats[0] not in ("WC", "WSC"): continue
        g = next((x for x in t if x in ("M", "W", "A", "X")), "")
        # Øvelsen står rett etter renn-nummeret (fire sifre)
        ci = next((i for i, x in enumerate(t) if re.fullmatch(r"\d{4}", x)), None)
        title = next((x for x in t[ci + 1:] if x[0].isupper() or x[0].isdigit()), "") if ci is not None else ""
        if re.search(r"Qualification|Training|Trial", title, re.I): continue
        when = datetime.datetime.strptime(f"{d} {tm or '12:00'}", "%d %b %Y %H:%M").replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        out.append(dict(when=when, timed=bool(tm), place=place, nat=nat, title=title, g={"A": "X"}.get(g, g), url=f"https://www.fis-ski.com/DB/general/results.html?sectorcode={sector}&raceid={rid.group(1)}",
                        cancelled="Cancelled" in block and "Not cancelled" not in block, cat=cat))
    return out

def fis_result(url):
    s = get(url)
    if not s: return None
    rows = []
    for r in re.findall(r'<a class="table-row"[^>]*>(.*?)</a>', s, re.S):
        t = txt(r)
        nat = next((x for x in t if re.fullmatch(r"[A-Z]{3}", x)), None)
        nm = next((x for x in t if re.search(r"[A-Z]{2,} ", x) or re.search(r"^[A-Z][A-Z' -]+ [A-Z][a-z]", x)), None)
        if t and nat and t[0].isdigit(): rows.append((t[0], nm or nat, nat))
    return podium(rows) if rows else None

# ---------- IBU ----------
IBU = "https://api.biathlonresults.com/modules/sportapi/api/"
def ibu():
    sid = f"{str(SEASON - 1)[2:]}{str(SEASON)[2:]}"
    ev = json.loads(get(IBU + f"Events?SeasonId={sid}&Level=1") or "[]")
    out = []
    for e in ev:
        comps = json.loads(get(IBU + f"Competitions?EventId={e['EventId']}") or "[]")
        for c in comps:
            when = datetime.datetime.fromisoformat(c["StartTime"].replace("Z", "+00:00"))
            g = {"SW": "W", "SM": "M", "MX": "X"}.get(c.get("catId"), "")
            out.append(dict(when=when, place=e.get("ShortDescription") or e.get("Organizer"), nat=e.get("Nat"), title=c.get("ShortDescription") or c.get("Description"), g=g,
                            url=f"https://www.biathlonworld.com/inside-ibu/results?raceId={c['RaceId']}", rid=c["RaceId"], done=c.get("StatusId") == 11 or c.get("ResultStatus") == "OFFICIAL",
                            cat="WSC" if "Championships" in (e.get("Description") or "") else "WC"))
    return out
def ibu_result(rid):
    d = json.loads(get(IBU + f"Results?RaceId={rid}") or "{}")
    rows = [(x.get("Rank") or "", x.get("Name") or "", x.get("Nat") or "") for x in d.get("Results") or []]
    return podium(rows) if rows else None

races = []
for sector, sport in FIS.items():
    evs = fis_events(sector)
    for eid, nat, cat in evs:
        key, c = f"{sector}:{eid}", evc.get(f"{sector}:{eid}")
        near = c and any(abs((datetime.datetime.fromisoformat(r["when"]) - NOW).total_seconds()) < 3 * 86400 for r in c["r"])
        if not c or near or any(not r.get("title") or r["title"][0].islower() for r in c["r"]) or datetime.datetime.fromisoformat(c["t"]) < NOW - datetime.timedelta(hours=20):
            got = fis_races(sector, eid, nat, cat); time.sleep(0.4)
            if got or not c: c = evc[key] = {"t": NOW.isoformat(), "r": [{**r, "when": r["when"].isoformat()} for r in got]}
        for r in c["r"]:
            races.append({**r, "when": datetime.datetime.fromisoformat(r["when"]), "sport": sport})
    print(f"{sport}: {len(evs)} renn-helger")
try:
    b = ibu()
    for r in b: r["sport"] = "Skiskyting"
    races += b; print(f"Skiskyting: {len(b)} renn")
except Exception as ex: print("IBU feilet:", ex)

out = []
for r in sorted(races, key=lambda r: r["when"]):
    if r.get("cancelled"): continue
    past = r["when"] < NOW - datetime.timedelta(hours=3)
    key = r["url"]
    if past and key not in res and r["when"] > NOW - datetime.timedelta(days=40):
        p = ibu_result(r["rid"]) if r["sport"] == "Skiskyting" else fis_result(key)
        if p and p[0]: res[key] = p
    p = res.get(key)
    if past and r["when"] < NOW - datetime.timedelta(days=21): continue
    out.append([r["sport"], r["when"].strftime("%Y-%m-%dT%H:%MZ"), r["place"], r["nat"], r["title"], r["g"], key, p[0] if p else None, p[1] if p else None, r["cat"], 1 if r.get("timed", True) else 0])
os.makedirs(os.path.dirname(CACHE), exist_ok=True)
json.dump({"res": res, "ev": evc}, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
line = "const WINTER = " + json.dumps({"at": NOW.strftime("%Y-%m-%dT%H:%MZ"), "r": out}, ensure_ascii=False, separators=(",", ":")) + ";"
page = open(HTML, encoding="utf-8").read()
page = re.sub(r"^const WINTER = .*;$", lambda m: line, page, count=1, flags=re.M)
open(HTML, "w", encoding="utf-8").write(page)
print(f"Vintersport: {len(out)} renn i lista")
