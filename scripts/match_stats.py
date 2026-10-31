# Kampfakta og statistikk for spilte fotballkamper (Noah 2026-10-25).
# Leser kamp-id-ene i FIXTURES (7. felt i hver spilte kamp) og lagrer én liten fil per kamp i data/kamp/<id>.json.
# Ferdigspilte kamper endrer seg ikke, så filer som finnes hentes ikke på nytt. Filer for kamper som ikke lenger vises slettes.
# Tallene er Opta-statistikken som FotMob viser. Bruk: python3 scripts/match_stats.py index.html
import json, os, sys, time, urllib.request
from lineup import lineup, events, stats
HTML = sys.argv[1]
DIR = os.path.join(os.path.dirname(os.path.abspath(HTML)), "data", "kamp")
os.makedirs(DIR, exist_ok=True)
s = open(HTML, encoding="utf-8").read()
i = s.index("const FIXTURES = "); j = s.index(";\n", i)
F = json.loads(s[i + 17:j])
ids = {str(m[6]) for v in F["teams"].values() for m in v.get("l", []) if len(m) > 6 and m[6]}
def fetch(u):
    for a in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read())
        except Exception: time.sleep(3 + 4 * a)
    return None
def compact(d):
    h, c = d["header"], d["content"]
    st = h.get("status", {})
    if not st.get("finished"): return None
    out = {"t": [x["name"] for x in h["teams"]], "s": [x["score"] for x in h["teams"]], "ko": st.get("utcTime")}
    lu = lineup(d)
    if lu: out["lu"] = lu; out["pv"] = 2
    ib = (c.get("matchFacts") or {}).get("infoBox") or {}
    if ib.get("Stadium"): out["v"] = ib["Stadium"].get("name")
    if ib.get("Referee"): out["ref"] = ib["Referee"].get("text")
    if ib.get("Attendance"): out["att"] = ib["Attendance"]
    if ib.get("Tournament"): out["comp"] = ib["Tournament"].get("leagueName"); out["rnd"] = ib["Tournament"].get("round")
    out["ev"], out["st"], out["st1"], out["st2"] = events(d), stats(d), stats(d, "FirstHalf"), stats(d, "SecondHalf")
    return out
have = {f[:-5] for f in os.listdir(DIR) if f.endswith(".json")}
# Filer fra før lagoppstilling, avsparkstid og omgangsstatistikk kom med (uten "ko" eller "st1") hentes på nytt, maks MAX_OLD per kjøring
MAX_OLD = int(os.environ.get("MAX_OLD", "200"))
# Filer med lagoppstilling uten spiller-id-er ("pv") hentes også på nytt, så spillerbildene kommer med
def stale(m):
    t = open(os.path.join(DIR, m + ".json"), encoding="utf-8").read()
    return not all(x in t for x in ('"ko"', '"st1"')) or ('"lu"' in t and '"pv"' not in t)
old = sorted(m for m in have & ids if stale(m))[:MAX_OLD]
new = 0
for mid in sorted(ids - have) + old:
    d = fetch(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}"); time.sleep(0.6)
    o = d and compact(d)
    if not o: continue
    json.dump(o, open(os.path.join(DIR, mid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":")); new += 1
for old in have - ids: os.remove(os.path.join(DIR, old + ".json"))
print(f"{len(ids)} kamper i FIXTURES, {new} nye kampfiler, {len(have - ids)} gamle slettet")
