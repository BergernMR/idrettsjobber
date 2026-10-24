# Henter ferske sportsnyheter til forsiden (GNEWS) fra gratis RSS-feeder, én per land, og setter dem inn i index.html.
# Kjøres hver time av .github/workflows/oppdater.yml. Bruk: python3 scripts/gnews_rss.py index.html
# Hvis en feed feiler, beholdes de gamle sakene for det landet.
import json, re, sys, html as H, urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

FEEDS = {
    "NO": ("NRK", "https://www.nrk.no/sport/toppsaker.rss"),
    "SE": ("SVT", "https://www.svt.se/sport/rss.xml"),
    "DK": ("DR", "https://www.dr.dk/nyheder/service/feeds/sporten"),
    "FI": ("Yle", "https://yle.fi/rss/urheilu"),
    "IS": ("RÚV", "https://www.ruv.is/rss/ithrottir"),
}
PER_LAND, MAKS_PER_IDRETT = 8, 4
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

def hent(kilde, url):
    xml = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AuroraBot/1.0)"}),
                                 timeout=30).read().decode("utf-8", "replace")
    saker, sett = [], set()
    for x in re.findall(r"<item[ >].*?</item>", xml, re.S):
        tittel, lenke = tekst(x, "title"), tekst(x, "link")
        lenke = re.sub(r"\?origin=rss$", "", lenke)
        if not tittel or not lenke.startswith("https://") or "focusId=" in lenke or lenke in sett: continue
        sett.add(lenke)
        try: dato = parsedate_to_datetime(tekst(x, "pubDate")).astimezone(OSLO)
        except Exception: dato = None
        kat = [H.unescape(re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", c.strip())) for c in re.findall(r"<category[^>]*>(.*?)</category>", x, re.S)]
        bilde = re.search(r'<(?:media:content|media:thumbnail|enclosure)[^>]*url="(https://[^"]+)"', x)
        saker.append({"dato": dato, "idrett": finn_idrett(kat, lenke, tittel, tekst(x, "description")), "tittel": tittel,
                      "lenke": lenke, "kilde": kilde, "bilde": H.unescape(bilde.group(1)) if bilde else None})
    saker.sort(key=lambda s: s["dato"] or datetime.min.replace(tzinfo=OSLO), reverse=True)
    # Bland idretter: maks fire saker fra samme idrett, med mindre det ikke finnes nok andre.
    valgt, tall = [], {}
    for s in saker:
        if tall.get(s["idrett"], 0) < MAKS_PER_IDRETT: valgt.append(s); tall[s["idrett"]] = tall.get(s["idrett"], 0) + 1
    valgt += [s for s in saker if s not in valgt]
    return sorted(valgt[:PER_LAND], key=lambda s: s["dato"] or datetime.min.replace(tzinfo=OSLO), reverse=True)

p = sys.argv[1]; s = open(p, encoding="utf-8").read()
i = s.index("const GNEWS = "); j = s.index(";\n", i); G = json.loads(s[i + 14:j])
img = G.get("img", {})
for land, (kilde, url) in FEEDS.items():
    try: saker = hent(kilde, url)
    except Exception as e: print(land, "feilet:", e); continue
    if len(saker) < 3: print(land, "for få saker, beholder de gamle"); continue
    G["r"][land] = [[x["dato"].strftime("%Y-%m-%d") if x["dato"] else "", x["idrett"], x["tittel"], x["lenke"], x["kilde"], 0] for x in saker]
    for x in saker:
        if x["bilde"] and x["lenke"] not in img: img[x["lenke"]] = x["bilde"]
    print(land, [f'{x["idrett"]}: {x["tittel"][:50]}' for x in saker])
lenker = {n[3] for v in G["r"].values() for n in v}
G["img"] = {u: b for u, b in img.items() if u in lenker}
ny = json.dumps(G, ensure_ascii=False, separators=(",", ":"))
if ny != s[i + 14:j]:
    G["at"] = datetime.now(OSLO).strftime("%Y-%m-%d")
    s = s[:i + 14] + json.dumps(G, ensure_ascii=False, separators=(",", ":")) + s[j:]
    open(p, "w", encoding="utf-8").write(s)
