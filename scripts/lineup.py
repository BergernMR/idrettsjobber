# Lagoppstilling fra FotMob sin matchDetails, i kort form (brukes av match_stats.py og live.py).
# [{"f": formasjon, "s": [[draktnr, navn, x, y], …] startellever, "b": [[draktnr, navn, byttet inn-minutt], …], "c": trener}, borte]
# x og y er plassering på banen (0–1), y = 0 ved eget mål.
def lineup(d):
    l = ((d or {}).get("content") or {}).get("lineup") or {}
    # Bare offisiell oppstilling ("standard"), ikke forrige kamps lag eller gjetning
    if l.get("lineupType") != "standard": return None
    out = []
    for side in ("homeTeam", "awayTeam"):
        tm = l.get(side) or {}
        st = tm.get("starters") or []
        if len(st) < 7: return None
        def p(x):
            vl = x.get("verticalLayout") or {}
            return [str(x.get("shirtNumber") or ""), x.get("name") or "", round(vl.get("x", .5), 3), round(vl.get("y", .5), 3)]
        subs = []
        for x in tm.get("subs") or []:
            ev = (x.get("performance") or {}).get("substitutionEvents") or []
            subs.append([str(x.get("shirtNumber") or ""), x.get("name") or "", next((e.get("time") for e in ev if e.get("type") == "subIn"), None)])
        coach = tm.get("coach")
        out.append({"f": tm.get("formation") or "", "s": [p(x) for x in st], "b": subs, "c": coach.get("name") if isinstance(coach, dict) else None})
    return out
