# Henter nye idrettsjobber fra NAV (Norge), Ledigajobb.se (Sverige) og Duunitori (Finland) og legger dem til i JOBS.
# Kjøres hver time av .github/workflows/oppdater.yml. Bruk: python3 scripts/jobs_fetch.py index.html
# Jobbene får sammendraget fra annonsen. Den daglige rutinen skriver dem om på enkel norsk og legger til oppgaver og detaljerte krav ("+ " foran det som bare er fint å ha).
import json, re, sys, time, html as H, urllib.request, urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

UA = {"User-Agent": "Mozilla/5.0 (compatible; AuroraBot/1.0; +https://github.com/BergernMR/idrettsjobber)"}
I_DAG = datetime.now(ZoneInfo("Europe/Oslo")).strftime("%Y-%m-%d")
MAKS_NYE = 8  # per land og kjøring, så en feil i et filter ikke fyller siden

# Ord som viser at det er en idrettsjobb, og ord som avslører at det ikke er det.
IDRETT = re.compile(r"idrett|idrott|trener|tränare|valmentaja|coach|turn|svøm|simhall|badvärd|bad(e)?anlegg|uimahalli|fotball|fotboll|"
                    r"håndball|handboll|ishockey|jääkiekko|ski|sport|urheilu|liikunta|kroppsøving|kroppsöving|treningssenter|gym|"
                    r"personlig trener|personlig tränare|instruktør|instruktör|ohjaaja|friidrett|friidrott|klatre|klätter|padel|tennis|golf|"
                    r"svømmehall|ishall|arena|stadion|idrettslag|förening|seura|uinti|uinn|uima|liikun|urheil|valmentaj|idrottsledare|sporthall", re.I)
IKKE = re.compile(r"personlig assistent|personlig assistans|brukerstyrt|bpa\b|opfor|dyrepleie|djurvård|kirkegård|kyrkogård|"
                  r"selger|säljare|säljande|myyjä|psykoterapeut|sykepleier|sjuksköterska|undersköterska|sairaanhoitaja|lähihoitaja|"
                  r"korps|drilltropp|superprof|militær|hund|stallansvarlig|øvingsbane|turisthytte|veidrift|barnehagelærer|förskollärare|ski(ft|pper)|skift|lager|truck|kassa|kokk|kock|vaktmester|städ|renhold|siivo", re.I)

NAV_JA = re.compile(r"Trenere og idrettsdommere|Sports- og aktivitetsinstruktører|Sports-, rekreasjons- og kultursenterledere")
NAV_NEI = re.compile(r"Hjemmehjelper|Dyrepassere|Programvareutviklere|Renholdere|Andre lærere|Anleggsmaskinførere|Bygningsingeniører|Elektrikere")

def kategori(t):
    t = t.lower()
    for cat, ord in [("larer", r"lærer|lärare|opettaja|pedagog"), ("trening", r"treningssenter|gym|personlig tr|pt\b|hälsa|fitness"),
                     ("anlegg", r"hall|anlegg|arena|badvärd|bad\b|uimahalli|drift|stadion"),
                     ("ledelse", r"leder|ledare|chef|daglig|manager|johtaja|päällikkö|direktør|sjef"),
                     ("trener", r"trener|tränare|valmentaja|coach|instruktør|instruktör|ohjaaja"),
                     ("klubb", r"klubb|forbund|förbund|förening|seura|liitto|idrettslag")]:
        if re.search(ord, t): return cat
    return "annet"

def hent(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")

def tekst(h, n=320):
    t = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …"

def pent(navn):
    # NAV skriver ofte arbeidsgiver og sted med store bokstaver.
    return " ".join(w.capitalize() if w.isupper() and len(w) > 2 else w for w in (navn or "").split()) if (navn or "").isupper() else (navn or "")

def norsk_dato(d):
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", d or "")
    return f"{m[3]}-{int(m[2]):02d}-{int(m[1]):02d}" if m else ""

def nav():
    jobber, sett = [], set()
    for q in ["idrett", "idrettslag", "trener", "svømmehall", "treningssenter"]:
        side = hent(f"https://arbeidsplassen.nav.no/stillinger?q={urllib.parse.quote(q)}&sort=published")
        # Søkeresultatet ligger som JSON inni Next.js-biter (self.__next_f.push([1, "..."])) på siden.
        s = "".join(json.loads(m) for m in re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', side))
        i = s.find('"searchResult":{"ads":')
        if i < 0: continue
        ads, _ = json.JSONDecoder().raw_decode(s, i + len('"searchResult":{"ads":'))
        for a in ads:
            if a["uuid"] in sett: continue
            sett.add(a["uuid"])
            styrk = " ".join(c.get("name", "") for c in a.get("categoryList") or [] if c.get("categoryType") == "STYRK08")
            tittel = a.get("jobTitle") if a.get("jobTitle") not in (None, "", "$undefined") else a.get("title") or ""
            alt = " ".join([tittel, a.get("title") or "", (a.get("employer") or {}).get("name") or ""])
            # Idrettsyrker i NAVs yrkeskoder, eller idrettsord i tittel/arbeidsgiver. Aldri yrker som åpenbart er noe annet.
            if not (NAV_JA.search(styrk) or IDRETT.search(alt)) or NAV_NEI.search(styrk) or IKKE.search(alt): continue
            kat = styrk
            sted = (a.get("locationList") or [{}])[0]
            sammendrag = ((a.get("generatedSearchMetadata") or {}).get("shortSummary")) or tekst(a.get("description"))
            jobber.append({"c": "NO", "t": tittel, "tr": a.get("title", "") if a.get("title") != tittel else "", "emp": pent((a.get("employer") or {}).get("name")),
                           "place": pent(sted.get("city") or sted.get("municipal") or ""), "dl": norsk_dato(a.get("applicationDue")),
                           "url": "https://arbeidsplassen.nav.no/stillinger/stilling/" + a["uuid"], "sum": sammendrag, "nokkel": a["uuid"],
                           "cat": kategori(tittel + " " + kat)})
    return jobber

def jsonld(url):
    for m in re.findall(r'<script[^>]*ld\+json[^>]*>(.*?)</script>', hent(url), re.S):
        try: d = json.loads(m)
        except Exception: continue
        for x in d if isinstance(d, list) else d.get("@graph", [d]):
            if isinstance(x, dict) and x.get("@type") == "JobPosting": return x
    return None

def fra_jsonld(land, url, nokkel, d, halvaar_er_standard=False):
    org = d.get("hiringOrganization") or {}
    loc = d.get("jobLocation") or {}
    loc = (loc[0] if isinstance(loc, list) and loc else loc) or {}
    adr = loc.get("address") or {}
    dl = (d.get("validThrough") or "")[:10]
    # Ledigajobb setter fristen til et halvt år fram når annonsen ikke har en ekte frist.
    if halvaar_er_standard and dl and (datetime.fromisoformat(dl) - datetime.now()).days > 150: dl = ""
    tittel = H.unescape(d.get("title") or "")
    tittel = tittel[:1].upper() + tittel[1:]
    return {"c": land, "t": tittel, "tr": "", "emp": pent(H.unescape(org.get("name") or "")) if isinstance(org, dict) else "",
            "place": adr.get("addressLocality") or "", "dl": dl, "url": url, "sum": tekst(d.get("description")), "nokkel": nokkel,
            "cat": kategori(tittel)}

def ledigajobb():
    jobber, sett = [], set()
    for side in ["idrottspedagog-jobb", "tranare-jobb", "idrottslarare-jobb", "badvakt-jobb"]:
        try: s = hent("https://ledigajobb.se/pr/" + side)
        except Exception: continue
        for url, nokkel, slug in re.findall(r'(https://ledigajobb\.se/jobb/([0-9a-z]+)/([^"\s]+))', s):
            tittel = urllib.parse.unquote(slug).replace("-", " ")
            if nokkel in sett or not IDRETT.search(tittel) or IKKE.search(tittel): continue
            sett.add(nokkel)
            jobber.append(("SE", url, nokkel))
    return jobber

def duunitori():
    jobber, sett = [], set()
    for side in ["ammatti/urheiluvalmentaja", "ala/liikuntapalvelut-ja-urheiluala"]:
        try: s = hent("https://duunitori.fi/tyopaikat/" + side)
        except Exception: continue
        for sti, slug, nokkel in re.findall(r'href="(/tyopaikat/tyo/([a-z0-9-]+)-(\d+))"', s):
            if nokkel in sett or IKKE.search(slug.replace("-", " ")): continue
            sett.add(nokkel)
            jobber.append(("FI", "https://duunitori.fi" + sti, nokkel))
    return jobber

def geo(sted, land):
    if not sted: return None
    try:
        time.sleep(1.1)  # Nominatim tillater ett oppslag i sekundet
        r = json.loads(hent("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": sted, "countrycodes": land.lower(), "format": "json", "limit": 1})))
        return [sted, round(float(r[0]["lat"]), 2), round(float(r[0]["lon"]), 2)] if r else None
    except Exception: return None

p = sys.argv[1]; s = open(p, encoding="utf-8").read()
a = s.index("const JOBS = ["); b = s.index("\n];", a)
jobs_tekst = s[a:b]
finnes = set(re.findall(r'J\("([a-z]+\d+)"', jobs_tekst))
def ny_id(prefiks):
    n = max([int(x[1:]) for x in finnes if x[0] == prefiks] + [0]) + 1
    finnes.add(f"{prefiks}{n}"); return f"{prefiks}{n}"

nye = []
try: kandidater = nav()
except Exception as e: print("NAV feilet:", e); kandidater = []
nye += [j for j in kandidater if j["nokkel"] not in jobs_tekst][:MAKS_NYE]
for kilde, land in [(ledigajobb, "SE"), (duunitori, "FI")]:
    try: liste = kilde()
    except Exception as e: print(land, "feilet:", e); continue
    lagt = 0
    for _, url, nokkel in liste:
        if lagt >= MAKS_NYE: break
        if (f"/jobb/{nokkel}/" if land == "SE" else f"-{nokkel}\"") in jobs_tekst: continue
        try: d = jsonld(url)
        except Exception: d = None
        if not d: continue
        j = fra_jsonld(land, url, nokkel, d, halvaar_er_standard=land == "SE")
        if not IDRETT.search(j["t"]) or IKKE.search(j["t"]): continue
        if j["dl"] and j["dl"] < I_DAG: continue
        nye.append(j); lagt += 1

if not nye: print("Ingen nye jobber"); sys.exit()
rader, geo_ny, lagt_til = [], {}, {}
for j in nye:
    jid = ny_id({"NO": "n", "SE": "s", "FI": "f"}[j["c"]])
    a_ = lambda v: json.dumps(v, ensure_ascii=False)
    rader.append(f'  J({a_(jid)},{a_(j["c"])},{a_(j["t"])},{a_(j["tr"])},{a_(j["emp"])},{a_(j["place"])},{a_(j["dl"])},{a_(j["cat"])},{a_(j["url"])},\n'
                 f'    {a_(j["sum"])},"","",[],[])')
    lagt_til[jid] = I_DAG
    g = geo(j["place"], j["c"])
    if g: geo_ny[jid] = g
    print("Ny jobb:", jid, j["t"], "–", j["emp"], j["place"])
s = s[:b] + ",\n" + ",\n".join(rader) + s[b:]
for navn, ny in [("ADDED_AT", lagt_til), ("GEO", geo_ny)]:
    m = re.search(rf"^const {navn} = (\{{.*\}});$", s, re.M)
    d = json.loads(m[1]); d.update(ny)
    s = s[:m.start(1)] + json.dumps(d, ensure_ascii=False) + s[m.end(1):]
# Oppdater datoene «Sist oppdatert …» og «hentet inn …» på alle språk.
MND = {"nb": "januar februar mars april mai juni juli august september oktober november desember",
       "is": "janúar febrúar mars apríl maí júní júlí ágúst september október nóvember desember",
       "en": "January February March April May June July August September October November December"}
def datoer(iso):
    y, m, d = map(int, iso.split("-")); nb, is_, en = (MND[k].split()[m - 1] for k in ("nb", "is", "en"))
    return [f"{d}. {nb} {y}", f"{d} {nb} {y}", f"{d}.{m}.{y}", f"{d}. {is_} {y}", f"{d} {en} {y}"]
MND_NR = {n: i + 1 for i, n in enumerate(MND["nb"].split())}
linjer = s.split("\n")
for i, l in enumerate(linjer):
    m = re.search(r"(?:Sist oppdatert (?:<b>)?|Stillingene er hentet inn )(\d{1,2})\. ([a-zæøå]+) (\d{4})", l)
    if not m or m[2] not in MND_NR: continue
    gml = f"{m[3]}-{MND_NR[m[2]]:02d}-{int(m[1]):02d}"
    for a, b in zip(datoer(gml), datoer(I_DAG)): l = l.replace(a, b)
    linjer[i] = l
s = "\n".join(linjer)
open(p, "w", encoding="utf-8").write(s)
