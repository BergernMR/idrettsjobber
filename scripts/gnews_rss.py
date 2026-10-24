# Henter ferske sportsnyheter til forsiden (GNEWS) fra flere RSS-feeder per land, sorterer dem etter relevans og setter dem inn i index.html.
# Kjøres hver time av .github/workflows/oppdater.yml. Bruk: python3 scripts/gnews_rss.py index.html
# Hvis alle feedene for et land feiler, beholdes de gamle sakene for det landet.
import json, re, sys, html as H, urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

# Kilder per land: (navn, feed, betalingsmur 0 = gratis, 1 = kan kreve abonnement). Gratis kilder får litt forrang.
FEEDS = {
    "NO": [("NRK", "https://www.nrk.no/sport/toppsaker.rss", 0), ("TV 2", "https://www.tv2.no/rss/sport", 0),
           ("VG", "https://www.vg.no/rss/feed/?categories=1072", 1)],
    "SE": [("SVT", "https://www.svt.se/sport/rss.xml", 0), ("Aftonbladet", "https://www.aftonbladet.se/sportbladet/rss.xml", 1),
           ("Expressen", "https://www.expressen.se/rss/sport", 1)],
    "DK": [("DR", "https://www.dr.dk/nyheder/service/feeds/sporten", 0), ("TV 2 Sport", "https://feeds.services.tv2.dk/api/feeds/sport/rss", 0)],
    "FI": [("Yle", "https://yle.fi/rss/urheilu", 0), ("MTV", "https://www.mtvuutiset.fi/api/feed/rss/urheilu", 0),
           ("Iltalehti", "https://www.iltalehti.fi/rss/urheilu.xml", 1), ("Ilta-Sanomat", "https://www.is.fi/rss/urheilu.xml", 1)],
    "IS": [("RÚV", "https://www.ruv.is/rss/ithrottir", 0), ("mbl.is", "https://www.mbl.is/feeds/sport/", 1),
           ("Fótbolti.net", "https://fotbolti.net/rss.php", 0)],
}
# Siden viser 8 saker; resten er reserver slik at de som har valgt en favorittidrett får saker om den.
PER_LAND, MAKS_PER_IDRETT = 16, 6
# Idretter folk flest i hvert land bryr seg mest om, gir litt høyere relevans.
STORE = {"NO": {"Fotball", "Langrenn", "Skiskyting", "Hopp", "Alpint", "Håndball"}, "SE": {"Fotball", "Ishockey", "Langrenn", "Skiskyting"},
         "DK": {"Fotball", "Håndball", "Sykling", "Badminton"}, "FI": {"Ishockey", "Fotball", "Formel 1", "Langrenn"},
         "IS": {"Fotball", "Håndball", "Basketball"}}
OSLO = ZoneInfo("Europe/Oslo")

# Idrett (norsk navn, som på siden) og ord som avslører den, på alle språkene. Rekkefølgen teller: det spesifikke først.
IDRETTER = [
    ("Skiskyting", "skiskyting skidskytte skiskydning ampumahiihto skíðaskotfimi biathlon"),
    ("Hopp", "skihopp backhopp mäkihyppy skihop skíðastökk"),
    ("Alpint", "alpint alpin alppihiihto slalåm slalom utförsåkning"),
    ("Langrenn", "langrenn längdskid langrend hiihto skíðaganga"),
    ("Bordtennis", "bordtennis pingis pöytätennis borðtennis"),
    ("Innebandy", "innebandy salibandy floorball"),
    ("Bandy", "bandy jääpallo"),
    ("Ishockey", "ishockey jääkiekko íshokkí nhl shl sm-liiga metal ligaen hockey"),
    ("Håndball", "håndball handboll håndbold käsipallo handbolt handball hsí"),
    ("Basketball", "basket koripallo körfu nba"),
    ("Volleyball", "volleyball volleyboll lentopallo blak"),
    ("Fotball", "fotball fotboll fodbold jalkapallo knattspyrn football soccer eliteserien allsvenskan superliga "
                "veikkausliiga besta deild premier league champions league europa league conference league "
                "bundesliga la liga serie a ligue 1 uefa fifa obos-ligaen superettan huuhkajat landsliðið í fótbolta "
                "fótbolt bayern liverpool arsenal chelsea manchester barcelona real madrid juventus tottenham"),
    ("Friidrett", "friidrett friidrott atletik yleisurheilu frjálsíþrótt frjálsar athletics maraton"),
    ("Sykling", "sykkel sykling cykel cykling pyöräily hjólreið tour de france giro vuelta"),
    ("Svømming", "svømming svømning simning simhopp uinti sund sundi"),
    ("Formel 1", "formel 1 formula 1 formúla f1"),
    ("Rally", "rally ralli"),
    ("Motorsport", "motorsport moottoriurheilu speedway motocross"),
    ("Tennis", "tennis"),
    ("Golf", "golf"),
    ("Turn", "gymnastik telinevoimistelu fimleik turning"),
    ("Kunstløp", "kunstløp konståkning kunstskøjte taitoluistelu listdans"),
    ("Skøyter", "skøyte skridsko pikaluistelu skautahlaup"),
    ("Boksing", "boksing boksning boxning nyrkkeily hnefaleik"),
    ("Kampsport", "mma ufc kampsport judo karate taekwondo bryting brottning"),
    ("Sjakk", "sjakk schack skak shakki skák"),
    ("Dart", "dart darts pilkastelu pílukast"),
    ("Badminton", "badminton sulkapallo"),
    ("Curling", "curling"),
    ("Padel", "padel"),
    ("Seiling", "seiling segling sejlsport purjehdus siglingar"),
    ("Roing", "roing rodd roning soutu róður"),
    ("Kano", "kano kanot kajak melonta"),
    ("Orientering", "orientering suunnistus ratleik"),
    ("Ridning", "ridning ridesport ratsastus hestaíþrótt travsport trav"),
]

# Flerordsuttrykk som må holdes samlet.
FRASER = {"metal ligaen", "besta deild", "premier league", "champions league", "europa league", "conference league",
          "la liga", "serie a", "real madrid", "ligue 1", "tour de france", "formel 1", "formula 1", "landsliðið í fótbolta"}
def ordliste(tekst):
    t = " " + tekst + " "; ut = []
    for f in FRASER:
        if " " + f + " " in t: ut.append(f); t = t.replace(" " + f + " ", " ")
    return ut + t.split()
REGLER = [(navn, ordliste(ord)) for navn, ord in IDRETTER]

def finn_idrett(kategorier, lenke, tittel, tekst):
    # Kategorier er sikrest, så lenken (f.eks. /sport/ishockey/), så tittel og ingress.
    for kilde in [" ".join(kategorier), lenke, tittel, tekst]:
        k = " " + re.sub(r"[^\w-]+", " ", kilde.lower()) + " "
        for navn, ord in REGLER:
            for o in ord:
                # Korte ord og forkortelser må stå alene; lange ord kan være del av et sammensatt ord.
                if (len(o) <= 4 and " " + o + " " in k) or (len(o) > 4 and o in k):
                    return navn
    return "Sport"

def tekst(x, tag):
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", x, re.S)
    if not m: return ""
    v = re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", m.group(1).strip(), flags=re.S)
    return H.unescape(re.sub(r"<[^>]+>", " ", H.unescape(v))).strip()

def hent(kilde, url, betaling):
    xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AuroraBot/1.0)"}),
                                 timeout=30).read().decode("utf-8", "replace")
    saker = []
    for x in re.findall(r"<item[ >].*?</item>", xml, re.S)[:40]:
        tittel, lenke = tekst(x, "title"), tekst(x, "link")
        lenke = re.sub(r"\?origin=rss$", "", lenke)
        if not tittel or not lenke.startswith("https://") or "focusId=" in lenke: continue
        try: dato = parsedate_to_datetime(tekst(x, "pubDate")).astimezone(OSLO)
        except Exception: dato = None
        kat = [H.unescape(re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", c.strip())) for c in re.findall(r"<category[^>]*>(.*?)</category>", x, re.S)]
        bilde = re.search(r'<(?:media:content|media:thumbnail|enclosure)[^>]*url="(https://[^"]+)"', x)
        saker.append({"dato": dato, "idrett": finn_idrett(kat, lenke, tittel, tekst(x, "description")), "tittel": tittel,
                      "lenke": lenke, "kilde": kilde, "betaling": betaling, "bilde": H.unescape(bilde.group(1)) if bilde else None})
    return saker

def metatekst(url):
    try:
        side = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AuroraBot/1.0)"}),
                                      timeout=10).read(300000).decode("utf-8", "replace")
    except Exception: return ""
    m = re.findall(r'<meta[^>]+(?:name|property)=["\'](?:keywords|news_keywords|description|og:description|article:section|article:tag)["\'][^>]*content=["\']([^"\']*)', side)
    return H.unescape(" ".join(m))

# Navn og andre tunge ord i tittelen, brukt til å se når flere kilder skriver om samme sak.
def nokkelord(tittel):
    ord = re.findall(r"\w{4,}", tittel)
    return {o.lower() for i, o in enumerate(ord) if o[0].isupper() and i > 0 or o[0].isdigit() or len(o) >= 8}

def velg(land, saker):
    na = datetime.now(OSLO)
    for s in saker:
        timer = (na - s["dato"]).total_seconds() / 3600 if s["dato"] else 48
        s["ord"] = nokkelord(s["tittel"])
        s["poeng"] = 10 * 0.5 ** (max(timer, 0) / 12) + (1.5 if s["idrett"] in STORE[land] else 0) \
            - (1.5 if s["idrett"] == "Sport" else 0) - s["betaling"]
    # Saker som flere kilder skriver om, er viktigere. Vi viser bare den beste av dem.
    for s in saker:
        like = [o for o in saker if o is not s and o["kilde"] != s["kilde"] and len(s["ord"] & o["ord"]) >= 2]
        s["like"] = like; s["poeng"] += 3 * min(len({o["kilde"] for o in like}), 2)
    saker.sort(key=lambda s: -s["poeng"])
    valgt, brukt, idr, kil = [], set(), {}, {}
    maks_kilde = PER_LAND // len(FEEDS[land]) + 3
    for runde in (0, 1):
        for s in saker:
            if len(valgt) >= PER_LAND or s["lenke"] in brukt or any(o["lenke"] in brukt for o in s["like"]): continue
            if runde == 0 and (idr.get(s["idrett"], 0) >= MAKS_PER_IDRETT or kil.get(s["kilde"], 0) >= maks_kilde): continue
            valgt.append(s); brukt.add(s["lenke"]); idr[s["idrett"]] = idr.get(s["idrett"], 0) + 1; kil[s["kilde"]] = kil.get(s["kilde"], 0) + 1
    return sorted(valgt, key=lambda s: -s["poeng"])

p = sys.argv[1]; s = open(p, encoding="utf-8").read()
i = s.index("const GNEWS = "); j = s.index(";\n", i); G = json.loads(s[i + 14:j])
img = G.get("img", {})
for land, kilder in FEEDS.items():
    saker = []
    for kilde, url, betaling in kilder:
        try: saker += hent(kilde, url, betaling)
        except Exception as e: print(land, kilde, "feilet:", e)
    # Uten kategori i feeden (f.eks. VG): les ingressen og stikkordene i selve saken for å finne idretten.
    for x in sorted([x for x in saker if x["idrett"] == "Sport"], key=lambda x: x["dato"] or datetime.min.replace(tzinfo=OSLO), reverse=True)[:12]:
        x["idrett"] = finn_idrett([], "", "", metatekst(x["lenke"]))
    saker = velg(land, saker)
    if len(saker) < 3: print(land, "for få saker, beholder de gamle"); continue
    # Rekkefølgen er relevans (viktigst først); siden flytter favorittidrettene fram.
    G["r"][land] = [[x["dato"].strftime("%Y-%m-%d") if x["dato"] else "", x["idrett"], x["tittel"], x["lenke"], x["kilde"], x["betaling"]] for x in saker]
    for x in saker:
        if x["bilde"] and x["lenke"] not in img: img[x["lenke"]] = x["bilde"]
    print(land, [f'{x["kilde"]}/{x["idrett"]}/{x["poeng"]:.1f}: {x["tittel"][:40]}' for x in saker])
lenker = {n[3] for v in G["r"].values() for n in v}
G["img"] = {u: b for u, b in img.items() if u in lenker}
ny = json.dumps(G, ensure_ascii=False, separators=(",", ":"))
if ny != s[i + 14:j]:
    G["at"] = datetime.now(OSLO).strftime("%Y-%m-%d")
    s = s[:i + 14] + json.dumps(G, ensure_ascii=False, separators=(",", ":")) + s[j:]
    open(p, "w", encoding="utf-8").write(s)
