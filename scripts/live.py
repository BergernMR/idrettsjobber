# Live-stilling for klubbene på siden. Henter dagens kamper fra FotMob hvert minutt
# og legger live.json på grenen "live" (siden leser den fra GitHub sitt API).
# Kjøres av .github/workflows/live.yml hvert 5. minutt. Bruk: python3 scripts/live.py index.html
import json, re, sys, time, datetime, subprocess, urllib.request
from zoneinfo import ZoneInfo
html = open(sys.argv[1], encoding="utf-8").read()
FM = {fm: fan for fan, fm in re.findall(r'"([a-z0-9-]+)":\{"s":"FotMob","u":"https://www\.fotmob\.com/teams/(\d+)/', html)}
NAME = {m[0]: m[1] for m in re.findall(r'^\s*\["([^"]+)","(?:NO|SE|DK|FI|IS)","([^"]+)"', html, re.M)}
LOOP_MIN, STEP = 24, 60
def fetch(url):
    for a in range(3):
        try: return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read())
        except Exception: time.sleep(3 + 3 * a)
    return None
def git(*a, inp=None): return subprocess.run(["git", *a], input=inp, capture_output=True, text=True).stdout.strip()
def snapshot():
    now = datetime.datetime.now(datetime.timezone.utc)
    days = {now.astimezone(ZoneInfo("Europe/Oslo")).strftime("%Y%m%d"), (now - datetime.timedelta(hours=4)).astimezone(ZoneInfo("Europe/Oslo")).strftime("%Y%m%d")}
    out, soon, ok = {}, False, False
    for d in sorted(days):
        data = fetch(f"https://www.fotmob.com/api/data/matches?date={d}&timezone=Europe%2FOslo")
        if not data: continue
        ok = True
        for lg in data.get("leagues", []):
            for m in lg.get("matches", []):
                st = m["status"]; ids = [str(m["home"]["id"]), str(m["away"]["id"])]
                if not any(i in FM for i in ids) or st.get("cancelled"): continue
                t = datetime.datetime.fromisoformat(st["utcTime"].replace("Z", "+00:00"))
                if not st.get("started"):
                    if datetime.timedelta(0) <= t - now <= datetime.timedelta(minutes=8): soon = True
                    continue
                if st.get("finished") and now - t > datetime.timedelta(hours=4): continue
                lt = (st.get("liveTime") or {}).get("short", "").replace("‎", "")
                state = "ft" if st.get("finished") else "ht" if lt.upper() in ("HT", "PAUSE") else "live"
                hs, as_ = m["home"].get("score", 0), m["away"].get("score", 0)
                for side, i in (("home", ids[0]), ("away", ids[1])):
                    if i not in FM: continue
                    oi = ids[1] if side == "home" else ids[0]; on = m["away" if side == "home" else "home"]["name"]
                    out[FM[i]] = [hs, as_, 1 if side == "home" else 0, NAME.get(FM.get(oi), on), state, lt if state == "live" else ""]
    return ok, out, soon
git("fetch", "-q", "origin", "live")
prev = git("show", "origin/live:live.json")
prev_m = json.loads(prev)["m"] if prev else None
start = time.time()
while True:
    ok, m, soon = snapshot()
    if ok and m != prev_m:
        body = json.dumps({"at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "m": m}, ensure_ascii=False, separators=(",", ":"))
        blob = git("hash-object", "-w", "--stdin", inp=body)
        tree = git("mktree", inp=f"100644 blob {blob}\tlive.json\n")
        commit = git("-c", "user.name=aurora-live", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com", "commit-tree", tree, "-m", "live")
        r = subprocess.run(["git", "push", "-qf", "origin", f"{commit}:refs/heads/live"], capture_output=True, text=True)
        print(time.strftime("%H:%M:%S"), len(m), "kamper", "push ok" if r.returncode == 0 else r.stderr)
        if r.returncode == 0: prev_m = m
    live = any(v[4] != "ft" for v in m.values())
    if not (live or soon) or time.time() - start > LOOP_MIN * 60: break
    time.sleep(STEP)
