# Kampfakta og statistikk for spilte fotballkamper (Noah 2026-10-25).
# Leser kamp-id-ene i FIXTURES (7. felt i hver spilte kamp) og lagrer én liten fil per kamp i data/kamp/<id>.json.
# Ferdigspilte kamper endrer seg ikke, så filer som finnes hentes ikke på nytt. Filer for kamper som ikke lenger vises slettes.
# Tallene er Opta-statistikken som FotMob viser. Bruk: python3 scripts/match_stats.py index.html
import json, os, sys, time, urllib.request
HTML = sys.argv[1]
DIR = os.path.join(os.path.dirname(os.path.abspath(HTML)), "data", "kamp")
os.makedirs(DIR, exist_ok=True)
s = open(HTML, encoding="utf-8").read()
i = s.index("const FIXTURES = "); j = s.index(";\n", i)
F = json.loads(s[i + 17:j])
ids = {str(m[6]) for v in F["teams"].values() for m in v.get("l", []) if len(m) > 6 and m[6]}
# Statistikken som vises, i denne rekkefølgen: FotMob-navn -> kort nøkkel (siden oversetter nøkkelen)
WANT = [("Ball possession", "poss"), ("Expected goals (xG)", "xg"), ("Total shots", "shots"), ("Shots on target", "sot"), ("Big chances", "big"),
        ("Corners", "corners"), ("Accurate passes", "passes"), ("Fouls committed", "fouls"), ("Offsides", "offside"), ("Yellow cards", "yellow"), ("Red cards", "red"), ("Saves", "saves")]
def fetch(u):
    for a in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read())
        except Exception: time.sleep(3 + 4 * a)
    return None
def compact(d):
    h, c = d["header"], d["content"]
    st = h.get("status", {})
    if not st.get("finished"): return None
    out = {"t": [x["name"] for x in h["teams"]], "s": [x["score"] for x in h["teams"]]}
    ib = (c.get("matchFacts") or {}).get("infoBox") or {}
    if ib.get("Stadium"): out["v"] = ib["Stadium"].get("name")
    if ib.get("Referee"): out["ref"] = ib["Referee"].get("text")
    if ib.get("Attendance"): out["att"] = ib["Attendance"]
    if ib.get("Tournament"): out["comp"] = ib["Tournament"].get("leagueName"); out["rnd"] = ib["Tournament"].get("round")
    ev = []
    for e in ((c.get("matchFacts") or {}).get("events") or {}).get("events") or []:
        tm = str(e.get("time")) + (f"+{e['overloadTime']}" if e.get("overloadTime") else "")
        side = 0 if e.get("isHome") else 1
        if e["type"] == "Goal":
            a = (e.get("assistStr") or "").replace("assist by ", "")
            kind = "pen" if e.get("goalDescription") == "Penalty" or e.get("isPenaltyShootoutEvent") else "own" if e.get("ownGoal") else "g"
            ev.append([tm, side, kind, e.get("nameStr") or "", a, e.get("newScore")])
        elif e["type"] == "Card":
            ev.append([tm, side, "r" if "Red" in (e.get("card") or "") else "y", e.get("nameStr") or ""])
        elif e["type"] == "Half" and str(e.get("time")) == "45": ev.append([tm, -1, "ht", "", "", None])
    out["ev"] = ev
    rows = {}
    for p in (((c.get("stats") or {}).get("Periods") or {}).get("All") or {}).get("stats") or []:
        for x in p.get("stats") or []:
            if x.get("title") and x.get("stats") and None not in x["stats"] and x["title"] not in rows: rows[x["title"]] = x["stats"]
    out["st"] = [[k, *rows[t]] for t, k in WANT if t in rows]
    return out
have = {f[:-5] for f in os.listdir(DIR) if f.endswith(".json")}
new = 0
for mid in sorted(ids - have):
    d = fetch(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}"); time.sleep(0.6)
    o = d and compact(d)
    if not o: continue
    json.dump(o, open(os.path.join(DIR, mid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":")); new += 1
for old in have - ids: os.remove(os.path.join(DIR, old + ".json"))
print(f"{len(ids)} kamper i FIXTURES, {new} nye kampfiler, {len(have - ids)} gamle slettet")
