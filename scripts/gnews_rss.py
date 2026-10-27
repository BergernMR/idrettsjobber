# Henter ferske sportsnyheter til forsiden (GNEWS) fra flere RSS-feeder per land, sorterer dem etter relevans og setter dem inn i index.html.
# Kjøres hver time av .github/workflows/oppdater.yml. Bruk: python3 scripts/gnews_rss.py index.html
# Hvis alle feedene for et land feiler, beholdes de gamle sakene for det landet.
import json, re, sys, html as H, urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

# Kilder per land: (navn, feed, betalingsmur 0 = gratis, 1 = kan kreve abonnement). Gratis kilder får litt forrang.
FEEDS = {
    "NO": [("NRK", "https://www.nrk.no/sport/toppsaker.rss", 0), ("NRK", "https://www.nrk.no/sport/siste.rss", 0),
           ("NRK", "https://www.nrk.no/sport/handball/toppsaker.rss", 0), ("TV 2", "https://www.tv2.no/rss/sport", 0),
           ("TV 2", "https://www.tv2.no/rss/sport/fotball", 0), ("TV 2", "https://www.tv2.no/rss/sport/vintersport", 0),
           ("TV 2", "https://www.tv2.no/rss/sport/handball", 0),
           ("NRK", "https://www.nrk.no/sport/skiskyting/toppsaker.rss", 0), ("NRK", "https://www.nrk.no/sport/alpint/toppsaker.rss", 0),
           ("NRK", "https://www.nrk.no/sport/hopp/toppsaker.rss", 0), ("VG", "https://www.vg.no/rss/feed/?categories=1072", 1),
           ("Aftenposten", "https://www.aftenposten.no/rss/sport", 1)],
    "SE": [("SVT", "https://www.svt.se/sport/rss.xml", 0), ("SVT", "https://www.svt.se/sport/fotboll/rss.xml", 0),
           ("SVT", "https://www.svt.se/sport/ishockey/rss.xml", 0), ("SVT", "https://www.svt.se/sport/vintersport/rss.xml", 0),
           ("SVT", "https://www.svt.se/sport/langdskidor/rss.xml", 0), ("SVT", "https://www.svt.se/sport/skidskytte/rss.xml", 0),
           ("SVT", "https://www.svt.se/sport/alpint/rss.xml", 0), ("SVT", "https://www.svt.se/sport/backhoppning/rss.xml", 0),
           ("Aftonbladet", "https://www.aftonbladet.se/sportbladet/rss.xml", 1), ("Expressen", "https://www.expressen.se/rss/sport", 1),
           ("DN", "https://www.dn.se/rss/sport/", 1)],  # Sydsvenskan sin «sport»-feed ga alle slags nyheter, derfor ute
    "DK": [("DR", "https://www.dr.dk/nyheder/service/feeds/sporten", 0), ("TV 2 Sport", "https://feeds.services.tv2.dk/api/feeds/sport/rss", 0),
           ("Politiken", "https://politiken.dk/rss/sport.rss", 1)],
    "FI": [("Yle", "https://yle.fi/rss/urheilu", 0), ("Yle", "https://feeds.yle.fi/uutiset/v1/majorHeadlines/YLE_URHEILU.rss", 0),
           ("MTV", "https://www.mtvuutiset.fi/api/feed/rss/urheilu", 0), ("Iltalehti", "https://www.iltalehti.fi/rss/urheilu.xml", 1),
           ("Ilta-Sanomat", "https://www.is.fi/rss/urheilu.xml", 1), ("HS", "https://www.hs.fi/rss/urheilu.xml", 1)],
    "IS": [("RÚV", "https://www.ruv.is/rss/ithrottir", 0), ("mbl.is", "https://www.mbl.is/feeds/sport/", 1),
           ("mbl.is", "https://www.mbl.is/feeds/fotbolti/", 1), ("mbl.is", "https://www.mbl.is/feeds/handbolti/", 1),
           ("Fótbolti.net", "https://fotbolti.net/rss.php", 0)],
}
# Siden viser 8 saker først og flere med «Vis flere»; resten er reserver slik at de som har valgt en favorittidrett får saker om den.
PER_LAND, MAKS_PER_IDRETT = 36, 12
# Idretter folk flest i hvert land bryr seg mest om, gir litt høyere relevans.
STORE = {"NO": {"Fotball", "Langrenn", "Skiskyting", "Hopp", "Alpint", "Kombinert", "Håndball"}, "SE": {"Fotball", "Ishockey", "Langrenn", "Skiskyting", "Alpint"},
         "DK": {"Fotball", "Håndball", "Sykling", "Badminton"}, "FI": {"Ishockey", "Fotball", "Formel 1", "Langrenn", "Hopp", "Skiskyting"},
         "IS": {"Fotball", "Håndball", "Basketball"}}
OSLO = ZoneInfo("Europe/Oslo")

# Siden skal bare ha nyheter om nordisk sport. Saker om utenlandske ligaer, klubber og stjerner tas bort,
# med mindre tittelen, ingressen eller stikkordene nevner noe nordisk (en nordisk utøver, et landslag osv.).
UTLAND = re.compile(r"\b(" + "|".join([
    r"Premier League", r"Championship", r"La ?Liga", r"Serie A", r"Bundesliga", r"Ligue 1", r"MLS", r"NHL", r"NBA", r"NFL", r"MLB",
    r"Englan\w*", r"Engelsk\w*", r"Spani\w*", r"Spánn?\w*", r"Espanja\w*", r"Itali\w*", r"Ítalí\w*", r"Tyskland\w*", r"Saksa\w*", r"Þýskal\w*",
    r"Frankrig\w*", r"Frankrike\w*", r"Ranska\w*", r"Frakkl\w*", r"Bandaríkj\w*", r"Infantino\w*",
    r"Arsenal\w*", r"Chelsea\w*", r"Liverpool\w*", r"Tottenham\w*", r"Manchester\w*", r"Man\.? (?:United|City|Utd)", r"Newcastle\w*",
    r"Aston Villa\w*", r"Everton\w*", r"Nottingham\w*", r"Forest", r"West Ham\w*", r"Brighton\w*", r"Brentford\w*", r"Fulham\w*",
    r"Wolves", r"Bournemouth\w*", r"Crystal Palace\w*", r"Leeds\w*", r"Sunderland\w*", r"Burnley\w*", r"Stamford Bridge", r"Anfield", r"Old Trafford",
    r"Real Madrid\w*", r"Barcelona\w*", r"Barça", r"Atlético\w*", r"Real Sociedad\w*", r"Sevilla\w*", r"Juventus\w*", r"Inter\b", r"Milan\w*",
    r"Napoli\w*", r"Lazio\w*", r"Roma\b", r"Torino\w*", r"Atalanta\w*", r"Bayern\w*", r"Dortmund\w*", r"Leverkusen\w*", r"Leipzig\w*", r"PSG", r"Paris Saint-Germain\w*",
    r"Ajax\w*", r"Benfica\w*", r"Porto\b", r"Celtic\w*", r"Rangers\w*", r"Parma\w*", r"Fiorentina\w*", r"Bologna\w*", r"Genoa\w*", r"Udinese\w*", r"Como\b",
    r"Sassuolo\w*", r"Cagliari\w*", r"Lecce\w*", r"Verona\w*", r"Pisa\b", r"Cremonese\w*", r"Villarreal\w*", r"Betis\w*", r"Valencia\w*", r"Athletic Bilbao", r"Girona\w*",
    r"Osasuna\w*", r"Celta\w*", r"Mallorca\w*", r"Getafe\w*", r"Espanyol\w*", r"Gil Vicente", r"Sporting\w*", r"Braga\w*", r"PSV\b", r"Feyenoord\w*", r"AZ Alkmaar",
    r"Frankfurt\w*", r"Stuttgart\w*", r"Wolfsburg\w*", r"Freiburg\w*", r"Hoffenheim\w*", r"Mainz\w*", r"Gladbach\w*", r"Union Berlin", r"Werder\w*", r"Hamburg\w*",
    r"Marseille\w*", r"Lyon\w*", r"Monaco\w*", r"Lille\b", r"Lens\b", r"Nice\b", r"Rennes\w*", r"Galatasaray\w*", r"Fenerbahçe\w*", r"Besiktas\w*",
    r"Ballon d'Or", r"El Clásico", r"El Clasico", r"Serie B", r"Bundesliga\w*", r"Eredivisie\w*", r"Liga Portugal", r"Süper Lig", r"Saudi\w*", r"Wimbledon\w*", r"US Open", r"Roland-Garros",
    r"LeBron\w*", r"MacKinnon\w*", r"Colorado\w*", r"Tampa\w*", r"Philadelphia\w*", r"Utah\w*", r"Lakers\w*", r"Celtics\w*", r"Ovetškin\w*", r"Ovetjkin\w*", r"Ovechkin\w*",
    r"ensk[ua]\w*", r"F1", r"Verstappen\w*", r"Leclerc\w*", r"Hamilton\w*", r"Norris\w*", r"Antonelli\w*", r"Piastri\w*", r"Indycar\w*",
    r"Messi\w*", r"Ronaldo\w*", r"Mbappé\w*", r"Salah\w*", r"Kane\b", r"Bellingham\w*", r"Yamal\w*", r"Kompany\w*", r"Guardiola\w*", r"Slot\b", r"Arteta\w*",
]) + r")", re.I)
NORDISK = re.compile(r"\b(" + "|".join([
    r"norsk\w*", r"nordm[ae]nn\w*", r"Norge\w*", r"Norges", r"Norjan?\w*", r"Noregs?",
    r"svensk\w*", r"Sverige\w*", r"Ruotsi\w*", r"Svíþjóð\w*", r"Tre Kronor", r"Blågult",
    r"dansk\w*", r"Danmark\w*", r"Tanska\w*", r"Danmörk\w*",
    r"finsk\w*", r"Finland\w*", r"suomalai\w*", r"Suome\w*", r"Suomi\w*", r"Leijon\w*", r"Huuhkaj\w*", r"Finnl\w*",
    r"island\w*", r"Ísland\w*", r"Íslend\w*", r"íslensk\w*",
    r"landslag\w*", r"landshold\w*", r"landslið\w*", r"maajoukkue\w*", r"nordisk\w*",
    r"Haaland\w*", r"Ødegaard\w*", r"Sørloth\w*", r"Nusa\w*", r"Bobb\w*", r"Aasgaard\w*", r"Strand Larsen\w*", r"Ryerson\w*", r"Selvik\w*", r"Nyland\w*", r"Hauger\w*", r"Glódís\w*", r"Hellberg\w*", r"Bottas\w*", r"Bottak\w*", r"Zuccarello\w*", r"Leo Carlsson\w*", r"Albert\b", r"Benoný\w*", r"Andri Lucas\w*", r"Hákon\w*", r"Orri\b", r"Ísak\w*", r"Sverrir\w*",
    r"(?:suomalais|ruotsalais|norjalais|tanskalais|islantilais)\w*", r"\w+(?:sson|ssonar|dóttir|dóttur)",
    r"Isak\w*", r"Gyökeres\w*", r"Kulusevski\w*", r"Elanga\w*", r"Højlund\w*", r"Eriksen\w*", r"Hjulmand\w*", r"Schmeichel\w*", r"Wind\b",
    r"Lehkonen\w*", r"Markka\w*", r"Barkov\w*", r"Rantanen\w*", r"Laine\w*", r"Aho\b", r"Granlund\w*", r"Hintz\w*", r"Pukki\w*", r"Hradecky\w*",
    r"Nylander\w*", r"Dahlin\w*", r"Hedman\w*", r"Pettersson\w*", r"Forsberg\w*", r"Ekholm\w*", r"Raanta\w*", r"Mikkola\w*",
    r"Albert Guðmunds\w*", r"Hákon\w*", r"Ísak Bergmann\w*", r"Orri Óskars\w*", r"Glimt\w*", r"Brann\w*", r"Molde\w*", r"Rosenborg\w*", r"Lillestrøm\w*",
    r"Solskjær\w*", r"Solbakken\w*", r"Klæbo\w*", r"Johaug\w*", r"Lægreid\w*", r"Bøs?\b", r"Warholm\w*", r"Ingebrigtsen\w*", r"Kristoffersen\w*",
    r"Kilde\b", r"Braathen\w*", r"Ruud\b", r"Hovland\w*", r"Østigård\w*", r"Ajer\b", r"Thorstvedt\w*", r"Berge\b", r"Graabak\w*", r"Riiber\w*", r"Grøvdal\w*",
    r"Jakob Ingebrigtsen", r"Duplantis\w*", r"Sjöström\w*", r"Ibrahimović\w*", r"Ibrahimovic\w*", r"Andreas Stjernen", r"Lindvik\w*", r"Granerud\w*",
    r"Vingegaard\w*", r"Axelsen\w*", r"Antonsen\w*", r"Rune\b", r"Mads Pedersen", r"Wozniacki\w*", r"Magnussen\w*", r"Hjulmand\w*", r"Damsgaard\w*", r"Dorgu\w*",
    r"Räikkönen\w*", r"Rovanperä\w*", r"Selänne\w*", r"Niskanen\w*", r"Pärmäkoski\w*", r"Gylfi\w*", r"Sigurðsson\w*", r"Guðmundsson\w*", r"Hlynsson\w*",
    r"Dahlqvist\w*", r"Sundling\w*", r"Andersson\w*", r"Karlsson\w*", r"Johansson\w*", r"Larsson\w*", r"Hansen\b", r"Johansen\b", r"Nilsen\b", r"Olsen\b", r"Pedersen\b", r"Jensen\b",
    r"Malmö\w*", r"Djurgård\w*", r"Hammarby\w*", r"AIK\b", r"Häcken\w*", r"FCK\b", r"Brøndby\w*", r"Midtjylland\w*", r"HJK\b", r"KuPS\b",
]) + r")", re.I)

# Nordiske idrettslag fra siden selv (FAN), ligaer og serier. Korte eller tvetydige navn står utenfor.
TVETYDIG = {"Sport", "Rangers", "Oilers", "Hawks", "Blue Hawks", "White Hawks", "Indians", "Hercules", "Atlantis", "Puma", "Classic", "Ready", "Comet", "Hunters", "Copenhagen", "Falcon", "Sisu", "Atlas", "Hermes", "Kings", "Lions", "Jets", "Stars", "Tigers", "Eagles", "Wolves", "Sharks", "Bears", "Dolphins", "Miners", "Towers", "Spirit", "Fera", "Loisto", "Koll", "Start", "Odd", "Lyn", "Moss", "Fram", "Inter", "Sparta", "Ilves", "Jaro", "Honka", "Union", "Lahti", "Skövde", "Vestri",
            "Valur", "Víkingur", "Þór", "Haukar", "Fylkir", "Stjarnan", "Grótta", "Leiknir", "Völsungur", "Real", "City", "United"}
LIGAER = ["Eliteserien", "OBOS-ligaen", "Toppserien", "Allsvenskan", "Superettan", "Damallsvenskan", "Superligaen", "Superliga", "1. division",
          "Veikkausliiga", "Ykkösliiga", "Besta deild", "Lengjudeild", "SHL", "HockeyAllsvenskan", "Liiga", "Metal Ligaen", "Fjordkraft-ligaen",
          "REMA 1000-ligaen", "Handbollsligan", "Håndboldligaen", "Herreligaen", "Kvindeligaen", "Olís-deild", "BLNO", "Basketligaen", "Korisliiga",
          "Elitserien", "Pesäpallo", "Superpesis", "NM", "SM", "DM", "Norway Cup", "Gothia Cup", "Birken", "Vasaloppet", "Holmenkollen", "Lahti"]
def lag_regex(navn):
    navn = sorted({n for n in navn if len(n) >= 4 and n not in TVETYDIG}, key=len, reverse=True)
    return re.compile(r"(?<![\wÀ-ÿ])(" + "|".join(re.escape(n) for n in navn) + r")(?![\wÀ-ÿ])")
def nordiske_navn(sidekilde):
    i = sidekilde.index("const FAN = ["); j = sidekilde.index("].map(", i)
    return re.findall(r'\["[^"]+",\s*"(?:NO|SE|DK|FI|IS)",\s*"([^"]+)"', sidekilde[i:j])
LAGNAVN = None  # settes når index.html er lest

# Lagidretter der utenlandske ligaer fyller feedene. Her må saken ha noe nordisk i seg for å bli med.
LAGIDRETT = {"Fotball", "Ishockey", "Basketball", "Håndball", "Volleyball", "Formel 1", "Motorsport", "Tennis", "Golf", "Boksing", "Kampsport", "Sport"}
# Korte live-oppdateringer fra utenlandske kamper, f.eks. «2-1: Lontani, Parma»
LIVETICKER = re.compile(r"^\s*\d+\s*[-–]\s*\d+\s*[:!]|setter \d+\s*[-–]\s*\d+|med rødt kort$|^Se (høydepunktene|målene|scoringene)|^Här (gör|är|ser)|^Katso", re.I)

def nordisk_signal(tekst):
    return bool(NORDISK.search(tekst) or LAGNAVN.search(tekst))

def nordisk(x, ekstra=""):
    # Utenlandsk sport er lov bare når nordiske utøvere eller lag er med i saken (Noah 2026-10-24).
    # «Med» betyr nevnt i tittel, ingress eller sakens egen beskrivelse, ikke bare i en lang liste med stikkord.
    if nordisk_signal(x["tittel"]): return True
    alt = x["ingress"] + " " + ekstra
    utland = UTLAND.search(x["tittel"]) or UTLAND.search(x["ingress"]) or LIVETICKER.search(x["tittel"])
    return nordisk_signal(alt) if utland else True

# Idrett (norsk navn, som på siden) og ord som avslører den, på alle språkene. Rekkefølgen teller: det spesifikke først.
IDRETTER = [
    ("Skiskyting", "skiskyting skiskytter skidskytt skiskydning ampumahiihto skíðaskotfimi biathlon"),
    ("Kombinert", "kombinert kombinertløper nordisk kombination kombineret yhdistetty nordic combined"),
    ("Hopp", "skihopp hoppuka backhopp mäkihyppy mäkihyppääjä skihop skíðastökk hoppbakke"),
    ("Freestyle", "snowboard freestyle freeski skicross slopestyle lumilautailu kumpareet puckelpist"),
    ("Alpint", "alpint alpinist alpin alppihiihto slalåm slalom storslalåm utförsåkning utforrenn super-g"),
    ("Langrenn", "langrenn langrennsløper längdskid langdskid längdåk langrend hiihto hiihtäjä skíðaganga tour de ski "
                 "vasaloppet birkebeinerrennet holmenkollen skiforbund skidförbund skiforbundet skidlandslag skilandslaget"),
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
    ("Skøyter", "skøyte skøyteløper skridsko pikaluistelu skautahlaup"),
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
          "la liga", "serie a", "real madrid", "tour de ski", "nordisk kombination", "nordic combined", "ligue 1", "tour de france", "formel 1", "formula 1", "landsliðið í fótbolta"}
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
        ingress = tekst(x, "description")
        saker.append({"dato": dato, "idrett": finn_idrett(kat, lenke, tittel, ingress), "tittel": tittel, "ingress": ingress,
                      "lenke": lenke, "kilde": kilde, "betaling": betaling, "bilde": H.unescape(bilde.group(1)) if bilde else None})
    return saker

def metatekst(url, bare_beskrivelse=False):
    try:
        side = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; AuroraBot/1.0)"}),
                                      timeout=10).read(300000).decode("utf-8", "replace")
    except Exception: return ""
    felt = "description|og:description" if bare_beskrivelse else "keywords|news_keywords|description|og:description|article:section|article:tag"
    m = re.findall(r'<meta[^>]+(?:name|property)=["\'](?:' + felt + r')["\'][^>]*content=["\']([^"\']*)', side)
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
LAGNAVN = lag_regex(nordiske_navn(s) + LIGAER)
i = s.index("const GNEWS = "); j = s.index(";\n", i); G = json.loads(s[i + 14:j])
img = G.get("img", {})
for land, kilder in FEEDS.items():
    saker = []
    for kilde, url, betaling in kilder:
        try: saker += hent(kilde, url, betaling)
        except Exception as e: print(land, kilde, "feilet:", e)
    # Bare nordisk sport: ved tvil (utenlandsk navn i tittelen) leses også stikkordene i selve saken.
    tvil = [x for x in saker if not nordisk(x)]
    for x in tvil[:60]:
        if nordisk(x, metatekst(x["lenke"], True)): x["ok"] = True
    bort = [x for x in tvil if not x.get("ok")]
    saker = [x for x in saker if x not in bort]
    if bort: print(land, "tok bort", len(bort), "utenlandske:", [x["tittel"][:40] for x in bort])
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
