# Lagoppstilling fra FotMob sin matchDetails, i kort form (brukes av match_stats.py og live.py).
# [{"f": formasjon, "s": [[draktnr, navn, x, y, bytter], …] startellever, "b": [[draktnr, navn, byttet inn-minutt, byttet ut-minutt], …], "c": trener}, borte]
# x og y er plassering på banen (0–1), y = 0 ved eget mål.
# bytter: hvem som tok plassen, i rekkefølge: [[minutt, draktnr, navn], …] (tom hvis spilleren ble stående hele kampen)
def lineup(d):
    content = (d or {}).get("content") or {}
    l = content.get("lineup") or {}
    # Byttene fra kamphendelsene: swap = [inn, ut]
    swaps = {}
    for e in (((content.get("matchFacts") or {}).get("events") or {}).get("events") or []):
        sw = e.get("swap") or []
        if e.get("type") == "Substitution" and len(sw) == 2 and sw[1].get("id"):
            swaps[str(sw[1]["id"])] = (str(sw[0].get("id") or ""), e.get("time"))
    # Bare offisiell oppstilling ("standard"), ikke forrige kamps lag eller gjetning
    if l.get("lineupType") != "standard": return None
    out = []
    for side in ("homeTeam", "awayTeam"):
        tm = l.get(side) or {}
        st = tm.get("starters") or []
        if len(st) < 7: return None
        who = {str(x.get("id")): x for x in st + (tm.get("subs") or [])}
        def chain(x):
            out, cur, seen = [], str(x.get("id")), set()
            while cur in swaps and cur not in seen:
                seen.add(cur); nid, tmin = swaps[cur]; y = who.get(nid)
                if not y: break
                out.append([tmin, str(y.get("shirtNumber") or ""), y.get("name") or ""]); cur = nid
            return out
        def p(x):
            vl = x.get("verticalLayout") or {}
            return [str(x.get("shirtNumber") or ""), x.get("name") or "", round(vl.get("x", .5), 3), round(vl.get("y", .5), 3), chain(x)]
        subs = []
        for x in tm.get("subs") or []:
            ev = (x.get("performance") or {}).get("substitutionEvents") or []
            subs.append([str(x.get("shirtNumber") or ""), x.get("name") or "", next((e.get("time") for e in ev if e.get("type") == "subIn"), None),
                         next((e.get("time") for e in ev if e.get("type") == "subOut"), None)])
        coach = tm.get("coach")
        out.append({"f": tm.get("formation") or "", "s": [p(x) for x in st], "b": subs, "c": coach.get("name") if isinstance(coach, dict) else None})
    return out

# Statistikken som vises, i denne rekkefølgen: FotMob-navn -> kort nøkkel (siden oversetter nøkkelen)
WANT = [("Ball possession", "poss"), ("Expected goals (xG)", "xg"), ("Total shots", "shots"), ("Shots on target", "sot"), ("Big chances", "big"),
        ("Corners", "corners"), ("Accurate passes", "passes"), ("Fouls committed", "fouls"), ("Offsides", "offside"), ("Yellow cards", "yellow"), ("Red cards", "red"), ("Saves", "saves")]
# Mål, kort og pause: [minutt, 0 hjemme / 1 borte / -1, type, navn, målgivende, stilling]
def events(d):
    c = (d or {}).get("content") or {}
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
    return ev
def stats(d):
    c = (d or {}).get("content") or {}
    rows = {}
    for p in (((c.get("stats") or {}).get("Periods") or {}).get("All") or {}).get("stats") or []:
        for x in p.get("stats") or []:
            if x.get("title") and x.get("stats") and None not in x["stats"] and x["title"] not in rows: rows[x["title"]] = x["stats"]
    return [[k, *rows[t]] for t, k in WANT if t in rows]
