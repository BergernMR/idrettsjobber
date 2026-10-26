# Kampoppsett og resultater for andre idretter enn fotball, fra forbundenes og ligaenes egne sider (Noah 2026-10-26).
# Brukes av update_data.py: collect(fan, now) gir {klubb-id: {"s", "u", "n", "l"}} i samme form som fotballkampene.
# Kilder:
#  - Svensk ishockey (SHL, HockeyAllsvenskan, Hockeyettan, SDHL): stats.swehockey.se, Svenska Ishockeyförbundets resultattjeneste
#  - Finsk ishockey (Liiga): liiga.fi sitt eget kampprogram
#  - Dansk håndball (Herreligaen, Kvindeligaen, 1. division herrer og kvinder): tophaandbold.dk, ligaenes egen side
#  - Svensk håndball (Handbollsligan herrer og damer): handbollsligan.se (bare kommende kamper; resultatene kommer fra TheSportsDB der laget finnes)
#  - Finsk innebandy (F-liiga menn og kvinner): fliiga.com, ligaens egen side
#  - Dansk innebandy (Unihoc Floorball Liga): resultater.floorball.dk, forbundets resultatservice (TMS)
import datetime, html as H, json, re, time, unicodedata, urllib.request
from zoneinfo import ZoneInfo

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
TZ = {"NO": "Europe/Oslo", "SE": "Europe/Stockholm", "DK": "Europe/Copenhagen", "FI": "Europe/Helsinki", "IS": "Atlantic/Reykjavik"}

def get(url, tries=3):
    for a in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode("utf-8", "replace")
        except Exception: time.sleep(3 + 5 * a)
    return None

def norm(s):
    s = s.lower().replace("æ", "ae").replace("ø", "o").replace("å", "a").replace("þ", "th").replace("ð", "d")
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", s)
AFF = r"\b(if|ik|hc|hf|hk|bk|sk|aif|is|soss|gois|bois|hockey|hockeyklubb|forening|dam|naiset|kvinner|kvinder|kvenna|ry|håndbold|håndboldklub|herrehåndbold|herrer|hh|fh|kh|handboll|hbk|team)\b"
def core(s): return norm(re.sub(AFF, " ", s.lower()))

ALIAS = {"Aarhus FK": "Århus Floorball Klub", "Pirkkalan Pirkat": "Pirkat", "Kiekko-Espoo": "K-Espoo", "Skanderborg AGF": "SAH", "NFH": "Nykøbing F. Håndboldklub", "H65 Höör": "Höörs HK H 65"}
def matcher(clubs, names):
    """Kobler lagnavnene i en liga til klubbene våre. Bare sikre treff (ett eneste kandidatnavn) brukes."""
    out = {}
    for k in clubs:
        want = re.sub(r"\s+(dam|Dam|Naiset|Kvinner|Kvinder|kvenna)$", "", k["n"]).strip()
        want = ALIAS.get(want, want)
        hit = [n for n in names if norm(n) == norm(want)] or [n for n in names if core(n) and core(n) == core(want)] or \
              [n for n in names if core(want) and core(n) and (core(want) in core(n) or core(n) in core(want)) and min(len(core(want)), len(core(n))) >= 3]
        # Samme lag kan stå flere ganger hos oss (eldre og nyere id); alle får kampene
        if len(hit) == 1: out.setdefault(hit[0], []).append(k["id"])
    return out

def entry(games, team, k, src, url, now, names):
    """games: [(utc-tid, hjemme, borte, hjemmemål|None, bortemål|None, turnering, tid kjent)] -> FIXTURES-element for laget."""
    tz = ZoneInfo(TZ[k["c"]]); up, played = [], []
    for t, h, a, hs, as_, comp, timed in games:
        if team not in (h, a): continue
        home = h == team; opp = names.get(a if home else h, a if home else h); lt = t.astimezone(tz)
        if hs is not None and as_ is not None:
            played.append([lt.strftime("%Y-%m-%d"), opp, 1 if home else 0, hs if home else as_, as_ if home else hs, comp])
        elif t > now:
            up.append((t, [lt.strftime("%Y-%m-%d"), opp, 1 if home else 0, comp, lt.strftime("%H:%M") if timed else ""]))
    e = {"s": src, "u": url}
    if up: e["n"] = sorted(up)[0][1]
    if played: e["l"] = sorted(played, key=lambda x: x[0], reverse=True)[:5]
    return e if len(e) > 2 else None

# ---------- Svensk ishockey ----------
SWEHOCKEY = {"SHL": 20961, "HockeyAllsvenskan": 20962, "Hockeyettan": 21041, "SDHL": 20960}
def swehockey(sid, comp):
    s = get(f"https://stats.swehockey.se/ScheduleAndResults/Schedule/{sid}")
    if not s: return []
    games, day = [], None
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        cells = [" ".join(H.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        for c in cells:
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", c)
            if m: day = m.group(1); break
        g = next((c for c in cells if " - " in c and not re.match(r"^\d+ - \d+$", c) and not re.match(r"^\(", c)), None)
        if not g or not day: continue
        h, a = [x.strip() for x in g.split(" - ", 1)]
        a = re.sub(r"\s+(Postponed|Uppskjuten|Inställd)$", "", a)
        tm = next((c for c in cells if re.fullmatch(r"\d{2}:\d{2}", c)), "")
        sc = next((c for c in cells if re.fullmatch(r"\d+ - \d+", c)), None)
        t = datetime.datetime.fromisoformat(f"{day}T{tm or '12:00'}").replace(tzinfo=ZoneInfo("Europe/Stockholm")).astimezone(datetime.timezone.utc)
        hs, as_ = (int(x) for x in sc.split(" - ")) if sc else (None, None)
        games.append((t, h, a, hs, as_, comp, bool(tm)))
    return games

# ---------- Liiga ----------
def liiga(now):
    season = now.year + 1 if now.month >= 7 else now.year
    out = []
    for tour in ("runkosarja", "playoffs"):
        s = get(f"https://liiga.fi/api/v2/games?tournament={tour}&season={season}")
        try: d = json.loads(s) if s else []
        except Exception: d = []
        for g in d:
            t = datetime.datetime.fromisoformat(g["start"].replace("Z", "+00:00"))
            done = g.get("ended")
            out.append((t, g["homeTeam"]["teamName"], g["awayTeam"]["teamName"], g["homeTeam"].get("goals") if done else None,
                        g["awayTeam"].get("goals") if done else None, "Liiga" if tour == "runkosarja" else "Sluttspill", True))
    return out

# ---------- Dansk håndball ----------
TOPH = {"Herreligaen": "herreligaen", "Kvindeligaen": "kvindeligaen", "1. division (håndbold)": "1-division-herrer", "1. division kvinder (håndbold)": "1-division-kvinder"}
def lines(s):
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S)
    return [x.strip() for x in H.unescape(re.sub(r"<[^>]+>", "\n", s)).split("\n") if x.strip()]
def tophaandbold(slug, comp):
    s = get(f"https://tophaandbold.dk/kampprogram/{slug}")
    if not s: return []
    L, out = lines(s), []
    for i, x in enumerate(L):
        m = re.fullmatch(r"(\d{2})-(\d{2})-(\d{2}) (\d{2}:\d{2})", x)
        if not m or i + 3 >= len(L): continue
        h, sc, a = L[i + 1], L[i + 2], L[i + 3]
        t = datetime.datetime.fromisoformat(f"20{m.group(3)}-{m.group(2)}-{m.group(1)}T{m.group(4)}").replace(tzinfo=ZoneInfo("Europe/Copenhagen")).astimezone(datetime.timezone.utc)
        g = re.fullmatch(r"(\d+)-(\d+)", sc)
        out.append((t, h, a, int(g.group(1)) if g else None, int(g.group(2)) if g else None, comp, True))
    return out

# ---------- Svensk håndball ----------
SV_MON = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAJ": 5, "JUN": 6, "JUL": 7, "AUG": 8, "SEP": 9, "OKT": 10, "NOV": 11, "DEC": 12}
def handbollsligan(path, comp, now):
    s = get(f"https://handbollsligan.se/{path}/spelschema/")
    if not s: return []
    L, out = lines(s), []
    for i, x in enumerate(L):
        m = re.match(r"^(?:Mån|Tis|Ons|Tors|Fre|Lör|Sön)\s+(\d{1,2})\s+([A-ZÅÄÖ]{3})\s+(\d{2}:\d{2})", x)
        if not m or i + 3 >= len(L) or SV_MON.get(m.group(2)) is None: continue
        mon = SV_MON[m.group(2)]; yr = now.year + (1 if mon < now.month - 2 else 0)
        t = datetime.datetime(yr, mon, int(m.group(1)), *map(int, m.group(3).split(":")), tzinfo=ZoneInfo("Europe/Stockholm")).astimezone(datetime.timezone.utc)
        out.append((t, L[i + 1], L[i + 3], None, None, comp, True))
    return out

# ---------- Innebandy ----------
def fliiga(path, comp):
    s = get(f"https://fliiga.com/ottelut/{path}/")
    if not s: return []
    out = []
    for c in re.split(r'<div class="grid-item match-card', s)[1:]:
        ts = re.search(r'data-match-gameday="(\d+)"', c)
        tn = re.findall(r'<span class="team-name">(.*?)</span>', c)
        if not ts or len(tn) != 2: continue
        hg = re.search(r'class="home-goals[^"]*">(\d+)<', c); ag = re.search(r'class="away-goals[^"]*">(\d+)<', c)
        played = "match-Played" in c[:200] and hg and ag
        t = datetime.datetime.fromtimestamp(int(ts.group(1)), datetime.timezone.utc)
        out.append((t, H.unescape(tn[0]), H.unescape(tn[1]), int(hg.group(1)) if played else None, int(ag.group(1)) if played else None, comp, True))
    return out

def tms(base, pulje, comp, tz):
    """Kampprogram fra TMS, resultattjenesten flere danske forbund bruker (floorball, volleyball)."""
    s = get(f"{base}/tms/Turneringer-og-resultater/Pulje-Komplet-Kampprogram.aspx?PuljeId={pulje}")
    if not s: return []
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        c = [" ".join(H.unescape(re.sub(r"<[^>]+>", " ", x)).split()) for x in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if len(c) < 6: continue
        m = re.fullmatch(r"(\d{2})-(\d{2})-(\d{2})(?: kl\. (\d{2}:\d{2}))?", c[1])
        if not m: continue
        t = datetime.datetime.fromisoformat(f"20{m.group(3)}-{m.group(2)}-{m.group(1)}T{m.group(4) or '12:00'}").replace(tzinfo=ZoneInfo(tz)).astimezone(datetime.timezone.utc)
        g = re.fullmatch(r"(\d+) - (\d+)", c[5])
        out.append((t, c[2], c[3], int(g.group(1)) if g else None, int(g.group(2)) if g else None, comp, bool(m.group(4))))
    return out

def collect(fan, now):
    out = {}
    def add(games, clubs, src, url):
        names = {n for g in games for n in (g[1], g[2])}
        m = matcher(clubs, names)
        disp = {n: next(k["n"] for k in clubs if k["id"] == cids[0]) for n, cids in m.items()}
        for n, cids in m.items():
            for cid in cids:
                k = next(x for x in clubs if x["id"] == cid)
                e = entry(games, n, k, src, url, now, disp)
                if e: out[cid] = e
        return sum(len(v) for v in m.values())
    se = [k for k in fan if k["sport"] == "Ishockey" and k["c"] == "SE"]
    for comp, sid in SWEHOCKEY.items():
        women = comp == "SDHL"
        clubs = [k for k in se if bool(re.search(r"\bdam$", k["n"])) == women and (k["div"] or "").split(",")[0] == comp]
        n = add(swehockey(sid, comp), clubs, "Svenska Ishockeyförbundet", f"https://stats.swehockey.se/ScheduleAndResults/Schedule/{sid}")
        print(f"  {comp}: {n} av {len(clubs)} lag")
    for div, slug in TOPH.items():
        clubs = [k for k in fan if k["sport"] == "Håndball" and k["c"] == "DK" and k["div"] == div]
        comp = div.replace(" (håndbold)", "")
        print(f"  {comp}: {add(tophaandbold(slug, comp), clubs, 'Tophåndbold', f'https://tophaandbold.dk/kampprogram/{slug}')} av {len(clubs)} lag")
    for div, path in (("Handbollsligan", "herr"), ("Handbollsligan dam", "dam")):
        clubs = [k for k in fan if k["sport"] == "Håndball" and k["c"] == "SE" and k["div"] == div]
        print(f"  {div}: {add(handbollsligan(path, div, now), clubs, 'Handbollsligan', f'https://handbollsligan.se/{path}/spelschema/')} av {len(clubs)} lag")
    for div, path in (("F-liiga", "miehet"), ("F-liiga naiset", "naiset")):
        clubs = [k for k in fan if k["sport"] == "Innebandy" and k["c"] == "FI" and k["div"] == div]
        print(f"  {div}: {add(fliiga(path, 'F-liiga'), clubs, 'F-liiga', f'https://fliiga.com/ottelut/{path}/')} av {len(clubs)} lag")
    clubs = [k for k in fan if k["sport"] == "Innebandy" and k["c"] == "DK"]
    url = "https://resultater.floorball.dk/tms/Turneringer-og-resultater/Pulje-Komplet-Kampprogram.aspx?PuljeId=612"
    print(f"  Floorball Liga: {add(tms('https://resultater.floorball.dk', 612, 'Floorball Liga', 'Europe/Copenhagen'), clubs, 'Floorball Danmark', url)} av {len(clubs)} lag")
    fi = [k for k in fan if k["sport"] == "Ishockey" and k["c"] == "FI" and k["div"] == "Liiga"]
    print(f"  Liiga: {add(liiga(now), fi, 'Liiga', 'https://liiga.fi/fi/ohjelma')} av {len(fi)} lag")
    return out

if __name__ == "__main__":
    import sys
    page = open(sys.argv[1], encoding="utf-8").read()
    src = page[page.index("const FAN = ["):page.index("].map(([id, c, n, sport, city")]
    rows = [json.loads(l.strip().rstrip(",")) for l in src.split("\n") if l.strip().startswith('["')]
    fan = [dict(id=r[0], c=r[1], n=r[2], sport=r[3], div=r[8] if len(r) > 8 else "") for r in rows]
    res = collect(fan, datetime.datetime.now(datetime.timezone.utc))
    print(len(res), "lag")
    for k, v in list(res.items())[:4]: print(k, v)
