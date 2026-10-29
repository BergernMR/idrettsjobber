# Kamphistorikk for fotballagene på siden (Noah 2026-10-29: «hele kampprogrammet for mange år tilbake»).
# Henter alle sesonger FotMob har for ligaene og cupene i update_data.py (stort sett 2010 og fram til nå) og lager én fil per lag:
# data/historikk/<lag-id>.json = {"at": dato, "m": [[avspark, motstander, hjemme 1/0, egne mål, motstanderens mål, turnering, kamp-id], …]}
# Vanlig kjøring henter bare siste sesong i hver liga og oppdaterer filene. HIST_FULL=1 henter alle sesonger på nytt.
# Bruk: python3 scripts/history.py index.html
import json, os, re, sys, time, datetime, urllib.request
from concurrent.futures import ThreadPoolExecutor
HTML = sys.argv[1]
html = open(HTML, encoding="utf-8").read()
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_data.py"), encoding="utf-8").read()
g = {}
exec(src[src.index("DIV_LEAGUE = "):src.index("def norm(")], g)
exec(re.search(r"^LEAGUE_IDS = .*$", src, re.M).group(0), g)
COMP, LEAGUE_IDS = g["COMP"], g["LEAGUE_IDS"]
FM = {fm: fan for fan, fm in re.findall(r'"([a-z0-9-]+)":\{"s":"FotMob","u":"https://www\.fotmob\.com/teams/(\d+)/', html)}
DIR = os.path.join(os.path.dirname(os.path.abspath(HTML)), "data", "historikk")
os.makedirs(DIR, exist_ok=True)
FULL = os.environ.get("HIST_FULL") == "1"
def fetch(u):
    for a in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read())
        except Exception: time.sleep(3 + 4 * a)
    return None
def score(st):
    s = re.match(r"\s*(\d+)\s*-\s*(\d+)", st.get("scoreStr") or "")
    return (int(s.group(1)), int(s.group(2))) if s and st.get("finished") and not st.get("cancelled") else (None, None)
# Første runde: gjeldende sesong i hver liga (gir også listen over sesonger)
with ThreadPoolExecutor(6) as pool: cur = dict(zip(LEAGUE_IDS, pool.map(lambda l: fetch(f"https://www.fotmob.com/api/data/leagues?id={l}"), LEAGUE_IDS)))
jobs = []
for lid, d in cur.items():
    if not d: continue
    seasons = d.get("allAvailableSeasons") or []
    jobs += [(lid, s) for s in (seasons[1:] if FULL else [])]
with ThreadPoolExecutor(6) as pool: old = list(pool.map(lambda j: (j[0], fetch(f"https://www.fotmob.com/api/data/leagues?id={j[0]}&season={urllib.request.quote(j[1])}")), jobs))
got = {}  # lag-id -> {kamp-id: rad}
for lid, d in [(l, d) for l, d in cur.items()] + old:
    for m in ((d or {}).get("fixtures") or {}).get("allMatches") or []:
        st = m.get("status") or {}
        if st.get("cancelled") or not st.get("utcTime"): continue
        hs, as_ = score(st)
        for side, other, home in (("home", "away", 1), ("away", "home", 0)):
            fan = FM.get(str(m[side]["id"]))
            if not fan: continue
            gf, ga = (hs, as_) if home else (as_, hs)
            got.setdefault(fan, {})[str(m["id"])] = [st["utcTime"][:16], re.sub(r"\s*\(W\)$", "", m[other]["name"]), home, gf, ga, COMP.get(lid, ""), str(m["id"])]
today = datetime.date.today().isoformat()
n = 0
for fan, ms in got.items():
    p = os.path.join(DIR, fan + ".json")
    have = {}
    if os.path.exists(p) and not FULL:
        have = {r[6]: r for r in json.load(open(p, encoding="utf-8"))["m"]}
    new = {**have, **ms}
    if new == have: continue
    rows = sorted(new.values(), key=lambda r: r[0])
    json.dump({"at": today, "m": rows}, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":")); n += 1
print(f"historikk: {len(jobs)} gamle sesonger hentet, {n} lagfiler oppdatert, {len(got)} lag med kamper")
