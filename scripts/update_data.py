# Oppdaterer kamper (FIXTURES) og fotballtabeller (TABLES) i index.html.
# Fotball: FotMob, alle divisjoner. Andre lagidretter: TheSportsDB (lag-id-er i scripts/tsdb_teams.json).
# Kjøres hver time av .github/workflows/oppdater.yml. Bruk: python3 scripts/update_data.py index.html
import json, glob, re, sys, unicodedata, datetime, os, time, urllib.request
from zoneinfo import ZoneInfo
HTML = sys.argv[1]
html = open(HTML, encoding="utf-8").read()
fan = [dict(id=m[0], c=m[1], n=m[2], sport=m[3], div=m[4]) for m in re.findall(r'^\s*\["([^"]+)","(NO|SE|DK|FI|IS)","([^"]+)","([^"]+)",[^\n]*?(?:,"([^"]*)")?\],?\s*$', html[html.index("const FAN = ["):html.index("].map(([id, c, n, sport, city")], re.M)]
TZ = {"NO": "Europe/Oslo", "SE": "Europe/Stockholm", "DK": "Europe/Copenhagen", "FI": "Europe/Helsinki", "IS": "Atlantic/Reykjavik"}
DIV_LEAGUE = {"Eliteserien": 59, "OBOS-ligaen": 203, "PostNord-ligaen": 204, "Norsk Tipping-ligaen": 205, "Allsvenskan": 67, "Superettan": 168, "Ettan": 169,
  "Superligaen": 46, "1. division": 85, "2. division": 239, "3. division": 240, "Veikkausliiga": 51, "Ykkösliiga": 251, "Ykkönen": 8969,
  "Besta deildin": 215, "Lengjudeildin": 216, "2. deild": 10226}
# Kvinnefotball (Noah 2026-10-27: tabeller også for kvinner). Holdes utenfor sjekken av at nok ligaer svarte.
WOMEN_LEAGUE = {"Toppserien": 331, "1. divisjon kvinner": 332, "Damallsvenskan": 9089, "Elitettan": 10308, "A-Liga": 256, "Kansallinen Liiga": 10174}
WSUF = r"\s+(Kvinner|kvinner|dam|Dam|Kvinder|Naiset|kvenna)$"
COMP = {59: "Eliteserien", 203: "OBOS-ligaen", 204: "PostNord-ligaen", 205: "Norsk Tipping-ligaen", 67: "Allsvenskan", 168: "Superettan", 169: "Ettan",
  46: "Superligaen", 85: "1. division", 239: "2. division", 240: "3. division", 51: "Veikkausliiga", 251: "Ykkösliiga", 8969: "Ykkönen", 215: "Besta deildin",
  216: "Lengjudeildin", 10226: "2. deild", 331: "Toppserien", 332: "1. divisjon", 9089: "Damallsvenskan", 10308: "Elitettan", 256: "A-Liga", 10174: "Kansallinen Liiga", 42: "Champions League", 73: "Europa League", 10216: "Conference League", 10076: "Ligacupen"}
# Cupene med eget navn, så «Neste kamp» viser hvilken turnering det er (Noah 2026-10-28)
COMP.update({206: "NM-cupen", 171: "Svenska cupen", 242: "Pokalturneringen", 143: "Suomen Cup", 217: "Mjólkurbikarinn"})
for i in (68, 172, 9634, 60, 9754, 52, 10713): COMP[i] = "Kvalifisering"
def norm(s):
    s = s.lower().replace("þ", "th").replace("ð", "d").replace("æ", "ae").replace("ø", "o").replace("å", "a")
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", s)
AFF = r"\b(il|if|ik|fk|fc|bk|sk|ff|bif|gif|aif|tif|ifk|boif|bois|ac|umf|ks|ps|jk|sc|b&i|i\.f\.|fotball|fotboll|fodbold)\b"
def core(s): return norm(re.sub(AFF, " ", s.lower()))
ALIAS = {"Hamarkameratene": "HamKam", "Fredrikstad": "Fredrikstad FK", "Kristiansund": "Kristiansund BK", "Molde": "Molde FK", "Tromsø": "Tromsø IL",
  "Start": "IK Start", "KFUM": "KFUM Oslo", "Víkingur Reykjavík": "Víkingur", "KR Reykjavík": "KR", "Fram Reykjavík": "Fram", "ÍA Akranes": "ÍA",
  "FH Hafnarfjörður": "FH", "Odds Ballklubb": "Odd", "Odds Ballklubb 2": "Odd 2", "Eidsvold TF": "Eidsvold Turn", "Ull/Kisa": "Ullensaker/Kisa", "KFUM 2": "KFUM Oslo 2", "HK Kópavogs": "HK", "ÍR Reykjavík": "ÍR", "Throttur Vogar": "Þróttur Vogum", "Thór Akureyri": "Þór Akureyri", "KA Akureyri": "KA", "ÍBV Vestmannaeyjar": "ÍBV"}
def fetch(url, tries=3, timeout=40):
    for a in range(tries):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=timeout).read())
        except Exception: time.sleep(3 + 5 * a)
    return None
LEAGUE_IDS = list(DIV_LEAGUE.values()) + list(WOMEN_LEAGUE.values()) + [206, 171, 242, 143, 217, 10076, 68, 172, 9634, 60, 9754, 52, 10713, 42, 73, 10216]
T0 = time.time()
def lap(what): print(f"[{time.time() - T0:5.0f} s] {what}", flush=True)
leagues, ldata = {}, {}
# Ligaene hentes noen om gangen i stedet for én og én, så timesjobben holder seg kort
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(6) as pool:
    for lid, d in zip(LEAGUE_IDS, pool.map(lambda l: fetch(f"https://www.fotmob.com/api/data/leagues?id={l}"), LEAGUE_IDS)):
        if d and d.get("fixtures"): leagues[lid] = d["fixtures"]["allMatches"]; ldata[lid] = d
lap(f"FotMob: {len(leagues)} av {len(LEAGUE_IDS)} ligaer")
if len(leagues) < len(DIV_LEAGUE): sys.exit("FotMob svarte ikke for nok ligaer, avbryter uten endringer")
DIV_LEAGUE.update(WOMEN_LEAGUE)
names = {}  # FotMob-id -> navn
for lid, ms in leagues.items():
    for m in ms:
        for side in ("home", "away"): m[side]["name"] = re.sub(r"\s*\(W\)$", "", m[side]["name"]); names[m[side]["id"]] = m[side]["name"]
fm_of, unknown = {}, []
for k in fan:
    if k["sport"] != "Fotball" or not k["div"]: continue
    lid = DIV_LEAGUE.get(k["div"].split(", ")[0])
    cand = {}
    for m in leagues.get(lid, []):
        for side in ("home", "away"): cand[m[side]["id"]] = m[side]["name"]
    want = [k["n"]] + [a for a, b in ALIAS.items() if b == k["n"]]
    if re.search(WSUF, k["n"]): want.append(re.sub(WSUF, "", k["n"]))
    hit = [i for i, n in cand.items() if any(norm(n) == norm(w) for w in want)] or \
          [i for i, n in cand.items() if any(core(n) == core(w) and core(w) for w in want)] or \
          [i for i, n in cand.items() if any(core(w) and (core(w) in core(n) or core(n) in core(w)) and min(len(core(w)), len(core(n))) >= 4 for w in want)]
    if len(hit) == 1: fm_of[k["id"]] = hit[0]
    else: unknown.append((k["id"], k["n"], k["div"], [cand[i] for i in hit][:4]))
fan_by_fm = {v: k for k, v in fm_of.items()}
fan_name = {k["id"]: k["n"] for k in fan}
now = datetime.datetime.now(datetime.timezone.utc)
out = {}
for k in fan:
    fid = fm_of.get(k["id"])
    if not fid: continue
    tz = ZoneInfo(TZ[k["c"]])
    played, upcoming, seen = [], [], set()
    for lid, ms in leagues.items():
        for m in ms:
            if fid not in (m["home"]["id"], m["away"]["id"]) or m["id"] in seen: continue
            seen.add(m["id"]); st = m["status"]
            if st.get("cancelled"): continue
            home = m["home"]["id"] == fid; opp = m["away" if home else "home"]
            oname = fan_name.get(fan_by_fm.get(opp["id"]), opp["name"])
            t = datetime.datetime.fromisoformat(st["utcTime"].replace("Z", "+00:00")).astimezone(tz)
            comp = COMP.get(lid, "Cup")
            if st.get("finished") and st.get("scoreStr"):
                a, b = [int(x) for x in re.findall(r"\d+", st["scoreStr"])[:2]]
                played.append([t.strftime("%Y-%m-%d"), oname, 1 if home else 0, a if home else b, b if home else a, comp, int(m["id"])])
            elif (not st.get("started") and t > now) or (st.get("started") and not st.get("finished")):
                # En kamp som pågår (f.eks. en cupkamp midt i uka) er fortsatt «neste kamp» til den er ferdig
                upcoming.append((t, [t.strftime("%Y-%m-%d"), oname, 1 if home else 0, comp, t.strftime("%H:%M")]))
    slug = re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", names.get(fid, k["n"]).lower()).encode("ascii", "ignore").decode()).strip("-")
    e = {"s": "FotMob", "u": f"https://www.fotmob.com/teams/{fid}/fixtures/{slug}"}
    if upcoming: e["n"] = sorted(upcoming)[0][1]
    played.sort(key=lambda x: x[0], reverse=True)
    if played: e["l"] = played[:5]
    if len(e) > 2: out[k["id"]] = e
# Andre lagidretter fra TheSportsDB
TS = json.load(open(os.path.join(os.path.dirname(__file__), "tsdb_teams.json")))
# Forrige kjørings kamper, brukes for lag som ikke rekkes eller ikke svarer denne gangen
m = re.search(r"^const FIXTURES = (.*);$", html, re.M)
try: prev = json.loads(m.group(1))["teams"] if m else {}
except Exception: prev = {}
TS_BUDGET, fails = 12 * 60, 0  # TheSportsDB kan være treg fra GitHub; da stopper vi heller enn å vente i en halvtime
t_ts = time.time()
for fan_id, tid in TS.items():
    k = next((x for x in fan if x["id"] == fan_id), None)
    if not k or fan_id in out: continue
    if time.time() - t_ts > TS_BUDGET or fails >= 6:
        if fan_id in prev and prev[fan_id].get("s") == "TheSportsDB": out[fan_id] = prev[fan_id]
        continue
    B = "https://www.thesportsdb.com/api/v1/json/123/"
    nx = fetch(B + f"eventsnext.php?id={tid}", 2, 15); time.sleep(2.1)
    ls = fetch(B + f"eventslast.php?id={tid}", 2, 15); time.sleep(2.1)
    fails = fails + 1 if nx is None and ls is None else 0
    if nx is None and ls is None:
        if fan_id in prev and prev[fan_id].get("s") == "TheSportsDB": out[fan_id] = prev[fan_id]
        continue
    nx, ls = (nx or {}).get("events"), (ls or {}).get("results")
    d = {"team": tid, "next": nx, "last": ls}
    tz = ZoneInfo(TZ[k["c"]]); tid = d["team"]; e = {"s": "TheSportsDB"}
    def info(ev):
        home = ev.get("idHomeTeam") == tid
        ts = ev.get("strTimestamp") or (ev.get("dateEvent", "") + "T" + (ev.get("strTime") or "00:00:00"))
        t = datetime.datetime.fromisoformat(ts[:19]).replace(tzinfo=datetime.timezone.utc).astimezone(tz)
        lg = ev.get("strLeague", "") or ""
        lg = {"Swedish Hockey League": "SHL", "Swedish Hockey Allsvenskan": "HockeyAllsvenskan", "Finnish Liiga": "Liiga"}.get(lg, lg)
        lg = re.sub(r"^(Swedish|Norwegian|Danish|Finnish|Icelandic|_No League)\s*", "", lg).strip() or "Serie"
        return home, t, ev.get("strAwayTeam" if home else "strHomeTeam"), lg
    nx = [ev for ev in d.get("next") or [] if ev.get("strStatus") not in ("Match Finished", "FT", "Postponed", "Cancelled")]
    U = []
    for ev in nx:
        home, t, opp, lg = info(ev)
        if t > now: U.append((t, [t.strftime("%Y-%m-%d"), opp, 1 if home else 0, lg, t.strftime("%H:%M") if (ev.get("strTime") or "")[:5] not in ("", "00:00") else ""]))
    if U: e["n"] = sorted(U)[0][1]
    L = []
    for ev in d.get("last") or []:
        if ev.get("intHomeScore") in (None, "") or ev.get("intAwayScore") in (None, ""): continue
        home, t, opp, lg = info(ev); hs, as_ = int(ev["intHomeScore"]), int(ev["intAwayScore"])
        L.append([t.strftime("%Y-%m-%d"), opp, 1 if home else 0, hs if home else as_, as_ if home else hs, lg])
    L.sort(key=lambda x: x[0], reverse=True)
    if L: e["l"] = L[:5]
    if len(e) > 1: out[k["id"]] = e
lap(f"TheSportsDB ferdig ({fails} feil på rad til slutt)")
# Ishockey og andre idretter fra forbundenes og ligaenes egne kampoppsett (går foran TheSportsDB)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures_other
try:
    for fid, v in fixtures_other.collect(fan, now).items():
        # Har forbundet bare kommende kamper, beholdes resultatene fra TheSportsDB
        if "l" not in v and "l" in out.get(fid, {}): v["l"] = out[fid]["l"]
        out[fid] = v
except Exception as ex: print("fixtures_other feilet:", ex)
lap("Forbund og ligaer ferdig")
# Fotballtabeller fra de samme FotMob-filene; lagnavn byttes til navnene siden bruker
def tables(html):
    i = html.index("const TABLES = "); j = html.index(";\n", i)
    T = json.loads(html[i + 15:j])
    for div, lid in WOMEN_LEAGUE.items():
        k = next((x for x in fan if x["div"] == div), None)
        if k and div not in T: T[div] = {"c": k["c"], "src": "FotMob", "url": f"https://www.fotmob.com/leagues/{lid}/table", "rows": []}
    for key, tb in T.items():
        base, sub = (key.split(", ") + [""])[:2]
        d = ldata.get(DIV_LEAGUE.get(base)); 
        if not d: continue
        dd = d["table"][0]["data"]
        if "tables" in dd:
            tl = dd["tables"]
            if sub:
                m = re.search(r"\d+", sub); idx = int(m.group()) - 1 if m else (0 if sub == "Norra" else 1)
                parts = [tl[idx]] if idx < len(tl) else []
            elif base in WOMEN_LEAGUE:
                parts = [max(tl, key=lambda x: len(x["table"]["all"]))]
            else:
                parts = [x for x in tl if re.search(r"Championship|Relegation", x["leagueName"])] or tl[-1:]
            rows = [r for p in parts for r in p["table"]["all"]]
        else: parts = [dd]; rows = dd["table"]["all"]
        if not rows: continue
        # Nedrykk og nedrykkskvalifisering slik FotMob oppgir dem (plassene telles fra 0 i hele tabellen).
        # Seks plasser eller flere er bare delingen av ligaen i to grupper, ikke nedrykk, og hoppes over.
        z, off = {"r": [], "q": []}, 0
        for p in parts:
            for lg in p.get("legend") or []:
                kind = {"Relegation": "r", "Relegation qualification": "q"}.get(lg.get("title"))
                ix = lg.get("indices") or []
                if kind and len(ix) < 6: z[kind] += [off + i for i in ix]
            off += len(p["table"]["all"])
        if z["r"] or z["q"]: tb["z"] = z
        else: tb.pop("z", None)
        out_rows = []
        for r in rows:
            gf, ga = [int(x) for x in r["scoresStr"].split("-")[:2]]
            nm = fan_name.get(fan_by_fm.get(str(r["id"])), re.sub(r"\s*\(W\)$", "", r["name"]))
            out_rows.append([nm, r["played"], r["wins"], r["draws"], r["losses"], gf, ga, r["pts"]])
        tb["rows"] = out_rows; tb["src"] = "FotMob"; tb["at"] = datetime.date.today().isoformat()
    T = {d: tb for d, tb in T.items() if tb["rows"]}
    return html[:i + 15] + json.dumps(T, ensure_ascii=False, separators=(",", ":")) + html[j:]
html = tables(html)
src = "FotMob og TheSportsDB, hentet {}".format(datetime.date.today().isoformat())
line = "const FIXTURES = " + json.dumps({"src": "FotMob", "at": datetime.date.today().isoformat(), "teams": out}, ensure_ascii=False, separators=(",", ":")) + ";"
html = re.sub(r"const FIXTURES = .*?;\n", lambda _: line + "\n", html, count=1)
open(HTML, "w", encoding="utf-8").write(html)
print(len(out), "lag;", sum("n" in v for v in out.values()), "med neste kamp;", sum(v["s"] == "FotMob" for v in out.values()), "fotball")
print("ukjente:", len(unknown))
for u in unknown: print("  ", u)
