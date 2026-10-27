# Siste nytt for hvert idrettslag (NEWS i index.html). Kjøres hver time av .github/workflows/oppdater.yml.
# Noah 2026-10-25: nyhetene skal være maks 3 dager gamle, oppdateres hele tiden, og lokalavisene skal med.
# Kilder:
#  1) 74 norske lokalaviser fra Amedia (GD, OA, Hamar Arbeiderblad, Romerikes Blad …) via Amedias åpne innholds-API.
#     Sakene har emneknagger som «Lillehammer Ishockeyklubb» og «Sport», som gjør treffene sikre.
#  2) RSS fra NRK-distriktene, SVT lokalt, regionale TV 2 i Danmark, Polaris-/Schibsted-aviser og de nasjonale sportsredaksjonene.
#  3) Bing News for lagene på omgang (de som er sjekket lengst siden først), så alle lag blir sjekket flere ganger om dagen.
# Tilstand (alle treff de siste 3 dagene og når hvert lag sist ble søkt etter) ligger i data/klubbnytt.json.
# Bruk: python3 scripts/club_news.py index.html
import json, os, re, sys, time, html as H, unicodedata, urllib.request, urllib.parse
import concurrent.futures as cf
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET
HTML = sys.argv[1]
ROOT = os.path.dirname(os.path.abspath(HTML))
STATE = os.path.join(ROOT, "data", "klubbnytt.json")
DAYS = 3
BING_PER_RUN = int(os.environ.get("BING_PER_RUN", "220"))
NOW = datetime.now(timezone.utc)
CUT = NOW - timedelta(days=DAYS)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
page = open(HTML, encoding="utf-8").read()
fan_src = page[page.index("const FAN = ["):page.index("].map(([id, c, n, sport, city")]
FAN = [json.loads(l.strip().rstrip(",")) for l in fan_src.split("\n") if l.strip().startswith('["')]
FAN = [dict(id=r[0], c=r[1], n=r[2], sport=r[3], city=r[4] or "", div=r[8] if len(r) > 8 else "") for r in FAN]

def get(url, tries=2, timeout=25):
    for a in range(tries):
        try: return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
        except Exception: time.sleep(2 + 3 * a)
    return None
def ascii_(x):
    x = x.replace("ø", "o").replace("Ø", "O").replace("æ", "ae").replace("Æ", "Ae").replace("þ", "th").replace("Þ", "Th").replace("ð", "d").replace("Ð", "D")
    return "".join(ch for ch in unicodedata.normalize("NFKD", x) if not unicodedata.combining(ch))
def low(x): return ascii_(x).lower()

# ---------- Idrett i teksten ----------
SPORTWORDS = {
    "Fotball": r"fotball|fotboll|fodbold|jalkapallo|f[oó]tbolt|knattspyrn|eliteserien|obos|postnord|norsk tipping-ligaen|allsvensk|superettan|ettan|superliga|1\. division|veikkausliiga|ykk[oö]s|kakkonen|besta deild|lengjudeild|toppserien|damallsvensk|kvindeliga|keeper|m[aå]lvakt|spiss|scoret|scoring",
    "Ishockey": r"hockey|ishockey|j[aä][aä]kiekko|[ií]shokk|puck|pucken|kiekko|ehl|shl|liiga|mestis",
    "Håndball": r"h[aå]ndball|handboll|h[aå]ndbold|k[aä]sipallo|handbolt|rema 1000-ligaen|herreligaen|kvindeligaen",
    "Basketball": r"basket|koripallo|k[oö]rfu|blno|korisliiga",
    "Volleyball": r"volleyball|volleyboll|lentopallo|blak",
    "Innebandy": r"innebandy|floorball|salibandy|f-liiga",
    "Bandy": r"bandy|j[aä][aä]pallo",
    "Pesäpallo": r"pes[aä]pallo|pesis|superpesis",
    "Friidrett": r"friidrett|friidrott|atletik|yleisurheilu|frj[aá]ls",
    "Svømming": r"sv[oø]mm|simning|sv[oø]mning|uinti|sund",
    "Orientering": r"orientering|suunnistus|ratleik",
}
SPORTRE = {k: re.compile(r"(?<!\w)(" + v + r")", re.I) for k, v in SPORTWORDS.items()}
ANYSPORT = re.compile(r"(?<!\w)(sport|idrett|idrott|urheilu|[ií]þr[oó]tt|kamp|match|ottelu|leik|seier|tap|vant|tapte|vann|f[oö]rlust|sejr|nederlag|voitto|tappio|sigur|tabell|serie|cup|trener|tr[aä]nare|tr[aæ]ner|valmentaja|[thþ]j[aá]lfari|spiller|spelare|spiller|pelaaja|leikma)", re.I)
LIVE = re.compile(r"^(følg|se|hør|følj|följ|seuraa|katso|fylgstu|direkte|live|quiz)\b|\bher\s*[:!]?$|\bquiz\b|\blive:|direkte:|\bslik var\b", re.I)
def sports_in(text): return {k for k, r in SPORTRE.items() if r.search(text)}
WOMEN = re.compile(r"(?<!\w)(kvinne|kvinner|damer|dam|kvinder|naiset|kvenna|jente|tjej|pige|tytt|kvennali|toppserien|damallsvensk|kvindeliga|kansallinen liiga)", re.I)

# ---------- Navn og alias for hvert lag ----------
AFF = r"\b(il|if|ik|fk|fc|bk|sk|ff|bif|gif|aif|tif|ifk|ac|umf|ks|jk|sc|hk|hc|bbk|ibk|ibf|fbc|hf|tf|ki|bc|vbk|vk|ois|bois|goif|sif|fotball|fotboll|fodbold|hockey|håndball|handboll|håndbold|ishockey|basket|volley|innebandy|bandy|elite|kvinner|dam|kvinder|naiset|kvenna|ballklubb|idrettslag|idrettsforening|ishockeyklubb|håndballklubb|fotballklubb)\b"
AMBIG = {"start", "odd", "lyn", "moss", "fram", "inter", "sparta", "union", "viking", "sport", "rangers", "hawks", "indians", "hercules", "atlantis", "puma", "classic", "ready", "comet",
         "hunters", "falcon", "sisu", "atlas", "hermes", "kings", "lions", "jets", "stars", "tigers", "eagles", "wolves", "sharks", "bears", "dolphins", "miners", "towers", "fera",
         "loisto", "koll", "jaro", "honka", "vestri", "valur", "fylkir", "hamar", "grei", "frigg", "kolbotn", "tertnes", "fana", "flint", "aker", "oppsal", "gimle", "ullern", "sola",
         "trondheim", "bergen", "oslo", "stavanger", "copenhagen", "helsinki", "turku", "pori", "oulu", "kotka", "lahti", "rovaniemi", "jokerit", "tps", "hifk", "hjk", "ilves", "kups",
         "huima", "oilers", "kiri", "ura", "tahko", "maila", "veto", "jymy", "puma", "aik", "gais", "ifk", "hif", "fif", "bk", "kfum", "ka", "kr", "fh", "hk", "ia", "ir", "ib", "ibv", "ksf", "mif", "ok", "if", "il", "fk", "sk", "bif", "ob", "agf", "fcm", "fck", "fcn", "lfk", "lik"}
CITYSET = {low(k["city"]) for k in FAN if k["city"]} | {low(x) for x in re.findall(r'\["([^"]+)", [\d.-]+, [\d.-]+, "\w\w"\]', page)}
def initials(n):
    ws = [w for w in re.findall(r"[^\W\d_]+", n) if w.lower() not in ("kvinner", "dam", "kvinder", "naiset", "kvenna")]
    return "".join(w[0] for w in ws).upper() if len(ws) >= 2 else ""
CLUBS = []
for k in FAN:
    women = bool(re.search(r"\b(Kvinner|dam|Dam|Kvinder|Naiset|kvenna)$", k["n"]))
    base = re.sub(r"\s+(Kvinner|dam|Dam|Kvinder|Naiset|kvenna)$", "", k["n"]).strip()
    core = re.sub(r"\s+", " ", re.sub(AFF, " ", base, flags=re.I)).strip(" -/")
    strong = {low(base)} | ({low(k["n"])} if women else set())
    weak = set()
    if core and low(core) != low(base) and len(core) >= 4 and low(core) not in AMBIG: weak.add(low(core))
    if low(base) in AMBIG or len(base) < 3: strong = set(); weak = set()
    town = {x for x in strong | weak if x in CITYSET}
    CLUBS.append(dict(k=k, women=women, strong=strong - town, weak=weak - town, town=town, abbr=initials(base)))
def rx(words): return re.compile(r"(?<![\w])(" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![\w])") if words else None
for c in CLUBS:
    c["rs"], c["rw"], c["rt"] = rx(c["strong"]), rx(c["weak"]), rx(c["town"])

# Kallenavn og forkortelser avisene bruker. Skrives med store bokstaver, så de sjekkes med riktig skrivemåte («TIL», ikke «til»)
NICK = {"til": ["TIL"], "rbk": ["RBK"], "nofb-haugesund": ["FKH"], "nofb-aalesund": ["AaFK"], "kbk": ["KBK"], "lsk": ["LSK"], "vif": ["VIF"],
        "godset": ["Godset"], "ffk": ["FFK"], "s08": ["S08"], "glimt": ["Glimt"], "nofb-kfum-oslo": ["KFUM"],
        "lik": ["LIK"], "vifh": ["VIF Hockey"], "oilers": ["Oilers"], "storhamar": ["Storhamar Hockey"], "nofb-ik-start": ["IK Start"],
        "nofb-stabaek": ["Stabæk"], "nofb-bryne": ["Bryne FK"], "nofb-hodd": ["Hødd"], "nofb-moss": ["Moss FK"]}
NICKRX = {cid: re.compile(r"(?<![\w])(" + "|".join(map(re.escape, v)) + r")(?![\w])") for cid, v in NICK.items()}
NICKLOW = {cid: {low(x) for x in v} for cid, v in NICK.items()}
def match(country, title, extra="", tags=(), sportish=False, hint=(), amedia=False):
    """Hvilke lag handler saken om? Krever et sikkert navnetreff, og at saken handler om riktig idrett."""
    t_low = low(title + " " + extra); tags_low = {low(x) for x in tags}
    found = sports_in(title + " " + extra + " " + " ".join(tags)) | set(hint)
    # Lokalaviser og distriktssendinger skriver om alt mulig: der må saken være merket sport eller nevne en idrett
    nick = {cid for cid, r in NICKRX.items() if r.search(title + " " + extra) or NICKLOW[cid] & tags_low}
    sporty = sportish or bool(found) or (amedia and "sport" in tags_low) or "sport" in tags_low or bool(nick)
    if not sporty: return []
    # Direktesendinger og quiz er ikke nyheter
    if LIVE.search(title): return []
    women_text = bool(WOMEN.search(title + " " + extra + " " + " ".join(tags)))
    hits = []
    for c in CLUBS:
        k = c["k"]
        if k["c"] != country: continue
        strong = k["id"] in nick or (c["rs"] and c["rs"].search(t_low)) or any(x in tags_low for x in c["strong"]) or (amedia and c["abbr"] and len(c["abbr"]) >= 3 and low(c["abbr"]) in tags_low)
        weak = c["rw"] and c["rw"].search(t_low)
        town = (c["rt"] and c["rt"].search(t_low)) or any(x in tags_low for x in c["town"])
        if not (strong or weak or town): continue
        # Navn som også er et sted (Lillehammer, Arendal …) og korte kjernenavn krever at idretten står i saken
        if (town or weak) and not strong and k["sport"] not in found: continue
        if found and k["sport"] not in found: continue
        if c["women"] != women_text and not (c["women"] and strong and any(low(w) in t_low for w in ("kvinner", "dam", "kvinder", "naiset", "kvenna"))):
            # Herrelaget når saken ikke handler om kvinner, kvinnelaget når den gjør det, hvis begge finnes
            twin = any(o is not c and o["k"]["c"] == k["c"] and o["k"]["sport"] == k["sport"] and o["women"] != c["women"] and
                       re.sub(r"\s+(Kvinner|dam|Dam|Kvinder|Naiset|kvenna)$", "", o["k"]["n"]) == re.sub(r"\s+(Kvinner|dam|Dam|Kvinder|Naiset|kvenna)$", "", k["n"]) for o in CLUBS)
            if twin or c["women"]: continue
            # Herrelag uten kvinnelag i lista: bare når laget er nevnt ved navn, ikke bare stedet
            if not (c["rs"] and c["rs"].search(low(title))): continue
        hits.append(k["id"])
    # Samme navn i flere idretter uten at idretten står i saken: for usikkert
    if not found and len({next(k["sport"] for k in FAN if k["id"] == h) for h in hits}) > 1: return []
    return hits if len(hits) <= 3 else []

PAY = ("aftenposten.no bt.no adressa.no aftenbladet.no dn.no rbnett.no itromso.no smp.no h-avis.no ba.no fvn.no f-b.no sa.no op.no gp.se sydsvenskan.se dn.se svd.se nt.se barometern.se "
       "vlt.se na.se bt.se hd.se unt.se corren.se berlingske.dk politiken.dk jyllands-posten.dk jv.dk stiften.dk fyens.dk hs.fi hbl.fi kaleva.fi ess.fi vasabladet.fi").split()
MAYBE = "mvt.se st.nu allehanda.se gd.se op.se nlt.se sla.se nwt.se nsd.se kuriren.nu smp.se blt.se kristianstadsbladet.se ystadsallehanda.se ksml.fi savonsanomat.fi kouvolansanomat.fi kymensanomat.fi ita-savo.fi aamulehti.fi satakunnankansa.fi ostnyland.fi vg.no dagbladet.no nettavisen.no aftonbladet.se expressen.se ekstrabladet.dk bt.dk is.fi iltalehti.fi mbl.is".split()
def pw(url, premium=None):
    if premium is not None: return 2 if premium else 0
    h = re.sub(r"^(www|m)\.", "", urllib.parse.urlparse(url).hostname or "")
    if any(h == d or h.endswith("." + d) for d in PAY): return 2
    if any(h == d or h.endswith("." + d) for d in MAYBE): return 1
    return 0

state = json.load(open(STATE, encoding="utf-8")) if os.path.exists(STATE) else {"items": {}, "checked": {}}
items = state["items"]  # klubb-id -> [[iso-tid, tittel, lenke, kilde, betalingsmur]]
def add(cid, when, title, url, src, p):
    if when < CUT or when > NOW + timedelta(hours=2): return
    lst = items.setdefault(cid, [])
    key = re.sub(r"[?#].*$", "", url)
    if any(re.sub(r"[?#].*$", "", x[2]) == key or low(x[1]) == low(title) for x in lst): return
    lst.append([when.isoformat(timespec="minutes"), title.strip(), url, src, p])

# ---------- 1) Amedia ----------
AMEDIA = {"akersposten.no": "Akershus Amtstidende", "amta.no": "Amta", "an.no": "Avisa Nordland", "ao.no": "Akershus Amtstidende", "auraavis.no": "Aura Avis",
  "avisa-hordaland.no": "Avisa Hordaland", "avisa-valdres.no": "Avisa Valdres", "ba.no": "Bergensavisen", "budstikka.no": "Budstikka", "bygdebladet.no": "Bygdebladet",
  "bygdeposten.no": "Bygdeposten", "dalane-tidende.no": "Dalane Tidende", "dt.no": "Drammens Tidende", "eikerbladet.no": "Eikerbladet", "eub.no": "Eidsvoll Ullensaker Blad",
  "f-b.no": "Fredriksstad Blad", "fanaposten.no": "Fanaposten", "firda.no": "Firda", "firdaposten.no": "Firdaposten", "fremover.no": "Fremover", "frostingen.no": "Frostingen",
  "gd.no": "GD", "gjengangeren.no": "Gjengangeren", "glomdalen.no": "Glåmdalen", "h-a.no": "Hamar Arbeiderblad", "h-avis.no": "Haugesunds Avis", "ha-halden.no": "Halden Arbeiderblad",
  "hadeland.no": "Hadeland", "hardanger-folkeblad.no": "Hardanger Folkeblad", "ifinnmark.no": "iFinnmark", "indre.no": "Indre Akershus Blad", "jarlsbergavis.no": "Jarlsberg Avis",
  "jbl.no": "Jærbladet", "kv.no": "Kommunal Rapport", "kvinnheringen.no": "Kvinnheringen", "laagendalsposten.no": "Laagendalsposten", "lierposten.no": "Lierposten",
  "lofot-tidende.no": "Lofot-Tidende", "lofotposten.no": "Lofotposten", "merakerposten.no": "Merakerposten", "moss-avis.no": "Moss Avis", "nab.no": "Nordre Aker Budstikke",
  "namdalsavisa.no": "Namdalsavisa", "nettavisen.no": "Nettavisen", "nidaros.no": "Nidaros", "nordhordland.no": "Nordhordland", "nordlys.no": "Nordlys", "oa.no": "Oppland Arbeiderblad",
  "oblad.no": "Østlandets Blad", "op.no": "Østlandets-Posten", "ostlendingen.no": "Østlendingen", "pd.no": "Porsgrunns Dagblad", "ranablad.no": "Rana Blad", "raumnes.no": "Raumnes",
  "rb.no": "Romerikes Blad", "rha.no": "Rakkestad Avis", "ringblad.no": "Ringerikes Blad", "ringsaker-blad.no": "Ringsaker Blad", "sa.no": "Sarpsborg Arbeiderblad",
  "sandnesposten.no": "Sandnesposten", "sb.no": "Sandefjords Blad", "smaalenene.no": "Smaalenenes Avis", "snasningen.no": "Snåsningen", "sognavis.no": "Sogn Avis",
  "steinkjer-avisa.no": "Steinkjer-Avisa", "strandbuen.no": "Strandbuen", "sydvesten.no": "Sydvesten", "t-a.no": "Trønder-Avisa", "ta.no": "Telemarksavisa", "tb.no": "Tønsbergs Blad",
  "telen.no": "Telen", "tk.no": "Tidens Krav", "tvedestrandsposten.no": "Tvedestrandsposten", "vestbyavis.no": "Vestby Avis"}
def amedia(dom):
    u = f"https://services.api.no/api/acpcomposer/v1.1/search/content/?publicationDomain=www.{dom}&sort=lastPublishedDate&limit=100&types=story"
    b = get(u); out = []
    if not b: return out
    for x in json.loads(b).get("_embedded") or []:
        f = x.get("fields") or {}
        try: when = datetime.fromisoformat(f["publishedDate"].replace("+0100", "+01:00").replace("+0200", "+02:00")).astimezone(timezone.utc)
        except Exception: continue
        tags = [t.get("displayName", "") for t in x.get("tags") or []]
        out.append((when, x.get("title") or "", x.get("leadText") or "", tags, f"https://www.{dom}{f.get('relativeUrl', '')}", f.get("isPremium")))
    return out
n_am = 0
with cf.ThreadPoolExecutor(8) as ex:
    for dom, arts in zip(AMEDIA, ex.map(amedia, AMEDIA)):
        for when, title, lead, tags, url, prem in arts:
            for cid in match("NO", title, lead, tags, amedia=True):
                add(cid, when, title, url, AMEDIA[dom], pw(url, prem)); n_am += 1

# ---------- 2) RSS ----------
RSS = {"NO": [("NRK " + d.replace("-", " ").title(), f"https://www.nrk.no/{d}/toppsaker.rss", False) for d in
              ("innlandet", "vestland", "rogaland", "trondelag", "nordland", "tromsogfinnmark", "sorlandet", "vestfoldogtelemark", "buskerud", "ostfold", "stor-oslo", "mr")] +
              [("NRK", "https://www.nrk.no/sport/siste.rss", True), ("TV 2", "https://www.tv2.no/rss/sport", True), ("Adresseavisen", "https://www.adressa.no/rss", False),
               ("Fædrelandsvennen", "https://www.fvn.no/rss", False), ("iTromsø", "https://www.itromso.no/rss", False), ("Sunnmørsposten", "https://www.smp.no/rss", False),
               ("Romsdals Budstikke", "https://www.rbnett.no/rss", False), ("Varden", "https://www.varden.no/rss", False), ("Agderposten", "https://www.agderposten.no/rss", False),
               ("VG", "https://www.vg.no/rss/feed/?categories=1072", True), ("Aftenposten", "https://www.aftenposten.no/rss/sport", True)],
       "SE": [("SVT " + r.title(), f"https://www.svt.se/nyheter/lokalt/{r}/rss.xml", False) for r in
              ("blekinge", "dalarna", "gavleborg", "halland", "helsingborg", "jamtland", "jonkoping", "norrbotten", "skane", "smaland", "sodertalje", "sormland", "stockholm",
               "uppsala", "varmland", "vast", "vasterbotten", "vasternorrland", "vastmanland", "orebro", "ost")] +
              [("SVT", "https://www.svt.se/sport/rss.xml", True), ("SVT", "https://www.svt.se/sport/fotboll/rss.xml", True), ("SVT", "https://www.svt.se/sport/ishockey/rss.xml", True),
               ("Aftonbladet", "https://www.aftonbladet.se/sportbladet/rss.xml", True), ("Expressen", "https://www.expressen.se/rss/sport", True)] +
              # Lokalaviser (hele avisen; sportssakene kjennes igjen på /sport/ i lenken)
              [(n, f"https://www.{d}/rss", False) for d, n in (("nt.se", "NT"), ("corren.se", "Corren"), ("unt.se", "UNT"), ("vlt.se", "VLT"), ("na.se", "NA"), ("mvt.se", "MVT"),
               ("st.nu", "Sundsvalls Tidning"), ("allehanda.se", "Allehanda"), ("gd.se", "Gefle Dagblad"), ("op.se", "Östersunds-Posten"), ("nlt.se", "NLT"), ("sla.se", "SLA"),
               ("nwt.se", "NWT"), ("nsd.se", "NSD"), ("kuriren.nu", "Norrbottens-Kuriren"), ("bt.se", "Borås Tidning"), ("smp.se", "Smålandsposten"), ("barometern.se", "Barometern"),
               ("blt.se", "BLT"), ("kristianstadsbladet.se", "Kristianstadsbladet"), ("hd.se", "HD"), ("ystadsallehanda.se", "Ystads Allehanda"))] +
              # Egne sider for hver idrett, også for de lavere divisjonene
              [("Hockeysverige", "https://www.hockeysverige.se/feed", True), ("Hockeyettan", "https://www.hockeyettan.se/feed", True),
               ("Handbollskanalen", "https://handbollskanalen.se/feed", True), ("Innebandymagazinet", "https://www.innebandymagazinet.se/feed", True),
               ("Bandypuls", "https://bandypuls.se/feed", True)],
       "DK": [("TV Syd", "https://www.tvsyd.dk/rss", False), ("TV 2 Fyn", "https://www.tv2fyn.dk/rss", False), ("TV Midtvest", "https://www.tvmidtvest.dk/rss", False),
              ("TV 2 Øst", "https://www.tv2east.dk/rss", False), ("TV 2 Kosmopol", "https://www.tv2kosmopol.dk/rss", False),
              ("TV2 Nord", "https://www.tv2nord.dk/rss", False), ("TV2 Østjylland", "https://www.tv2ostjylland.dk/rss", False),
              ("hbold.dk", "https://www.hbold.dk/feed", True), ("Volleyball Danmark", "https://www.volleyball.dk/feed", True),
              ("DR", "https://www.dr.dk/nyheder/service/feeds/sporten", True), ("TV 2 Sport", "https://feeds.services.tv2.dk/api/feeds/sport/rss", True)],
       "FI": [("Yle", "https://yle.fi/rss/urheilu", True), ("MTV", "https://www.mtvuutiset.fi/api/feed/rss/urheilu", True), ("Iltalehti", "https://www.iltalehti.fi/rss/urheilu.xml", True),
              ("Ilta-Sanomat", "https://www.is.fi/rss/urheilu.xml", True), ("HS", "https://www.hs.fi/rss/urheilu.xml", True),
              ("Aamulehti", "https://www.aamulehti.fi/rss/urheilu.xml", True), ("Satakunnan Kansa", "https://www.satakunnankansa.fi/rss/urheilu.xml", True),
              ("Salibandy.fi", "https://www.salibandy.fi/feed", True)] +
              [(n, f"https://www.{d}/rss", False) for d, n in (("ksml.fi", "Keskisuomalainen"), ("savonsanomat.fi", "Savon Sanomat"), ("ess.fi", "Etelä-Suomen Sanomat"),
               ("kouvolansanomat.fi", "Kouvolan Sanomat"), ("kymensanomat.fi", "Kymen Sanomat"), ("ita-savo.fi", "Itä-Savo"), ("hbl.fi", "HBL"), ("vasabladet.fi", "Vasabladet"),
               ("ostnyland.fi", "Östnyland"))],
       "IS": [("RÚV", "https://www.ruv.is/rss/ithrottir", True), ("mbl.is", "https://www.mbl.is/feeds/sport/", True), ("mbl.is", "https://www.mbl.is/feeds/fotbolti/", True),
              ("mbl.is", "https://www.mbl.is/feeds/handbolti/", True), ("Fótbolti.net", "https://fotbolti.net/rss.php", True), ("Karfan.is", "https://www.karfan.is/feed", True)]}
HINT = {"fotbolti.net": ["Fotball"], "/fotbolti/": ["Fotball"], "/handbolti/": ["Håndball"], "/fotboll/": ["Fotball"], "/ishockey/": ["Ishockey"], "/handball/": ["Håndball"],
        "hockeysverige.se": ["Ishockey"], "hockeyettan.se": ["Ishockey"], "handbollskanalen.se": ["Håndball"], "innebandymagazinet.se": ["Innebandy"], "bandypuls.se": ["Bandy"],
        "hbold.dk": ["Håndball"], "volleyball.dk": ["Volleyball"], "salibandy.fi": ["Innebandy"], "karfan.is": ["Basketball"]}
# Lenken sier ofte hvilken avdeling og idrett saken hører til (nt.se/sport/ishockey/…, ksml.fi/urheilu/…)
SPORTPATH = re.compile(r"/(sport|sporten|urheilu|idrett|idraet|ithrottir)(/|$)", re.I)
PATHHINT = {"ishockey": "Ishockey", "hockey": "Ishockey", "jaakiekko": "Ishockey", "handboll": "Håndball", "handbold": "Håndball", "kasipallo": "Håndball",
            "innebandy": "Innebandy", "salibandy": "Innebandy", "floorball": "Innebandy", "bandy": "Bandy", "basket": "Basketball", "koripallo": "Basketball",
            "volleyboll": "Volleyball", "lentopallo": "Volleyball", "pesapallo": "Pesäpallo", "fotboll": "Fotball", "fodbold": "Fotball", "jalkapallo": "Fotball"}
def rss(job):
    c, (src, url, sportish) = job
    b = get(url); out = []
    if not b: return c, src, sportish, out
    try: root = ET.fromstring(re.sub(rb"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", b))
    except Exception: return c, src, sportish, out
    for it in root.iter("item"):
        t = H.unescape(it.findtext("title") or "").strip(); link = (it.findtext("link") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", H.unescape(it.findtext("description") or ""))
        cats = [x.text or "" for x in it.findall("category")]
        try: when = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception: continue
        out.append((when, t, desc[:400], cats, link))
    return c, src, sportish, out
n_rss = 0
with cf.ThreadPoolExecutor(10) as ex:
    for (c, src, sportish, arts), (_, (_, furl, _)) in zip(ex.map(rss, [(c, f) for c, fs in RSS.items() for f in fs]), [(c, f) for c, fs in RSS.items() for f in fs]):
        hint = [s for key, v in HINT.items() if key in furl for s in v]
        for when, t, desc, cats, link in arts:
            path = urllib.parse.urlparse(link).path.lower()
            h2 = hint + [v for k2, v in PATHHINT.items() if f"/{k2}/" in path]
            # Hele lokalaviser: bare sportssakene, så «Hamar» i en trafikksak ikke blir en klubbnyhet
            if not sportish and furl.endswith("/rss") and any(d in furl for d in (".se/", ".nu/", ".fi/")) and not (SPORTPATH.search(path) or h2 or "Urheilu" in cats): continue
            for cid in match(c, t, desc, cats, sportish or bool(SPORTPATH.search(path)), h2):
                add(cid, when, t, link, src, pw(link)); n_rss += 1

# ---------- 3) Bing News på omgang ----------
WORD = {"Fotball": "fotball fotboll fodbold jalkapallo fótbolti", "Ishockey": "ishockey ishockey ishockey jääkiekko íshokkí", "Håndball": "håndball handboll håndbold käsipallo handbolti",
        "Basketball": "basket basket basketball koripallo körfubolti", "Volleyball": "volleyball volleyboll volleyball lentopallo blak", "Bandy": "bandy bandy bandy jääpallo bandy",
        "Innebandy": "innebandy innebandy floorball salibandy floorball", "Friidrett": "friidrett friidrott atletik yleisurheilu frjálsar", "Svømming": "svømming simning svømning uinti sund",
        "Orientering": "orientering orientering orientering suunnistus ratleikur", "Pesäpallo": "pesäpallo pesäpallo pesäpallo pesäpallo pesäpallo"}
CI = {"NO": 0, "SE": 1, "DK": 2, "FI": 3, "IS": 4}
MKT = {"NO": ("nb", "NO"), "SE": ("sv", "SE"), "DK": ("da", "DK"), "FI": ("fi", "FI"), "IS": ("is", "IS")}
checked = state["checked"]
order = sorted(CLUBS, key=lambda c: checked.get(c["k"]["id"], ""))[:BING_PER_RUN]
# Andre idretter enn fotball har færre saker i avisene, så de får en ekstra runde hver time (Noah 2026-10-26)
picked = {c["k"]["id"] for c in order}
order += [c for c in sorted(CLUBS, key=lambda c: checked.get(c["k"]["id"], "")) if c["k"]["sport"] != "Fotball" and c["k"]["id"] not in picked][:int(os.environ.get("BING_EXTRA", "120"))]
JUNK = re.compile(r"odds|bet|apuest|wett|casino|transfer|flashscore|sofascore|livescore|fotmob|besoccer|soccerway|wikipedia|tipset|spelpro|sportsgambler|scores24|aiscore|youtube|facebook|instagram|tiktok", re.I)
JUNKT = re.compile(r"fixtures|results|live score|livescore|prediction|predictions|\btips\b|\bodds\b|\bvs\.?\s.*\b(h2h|stream)|livestream|tv-tider|tv guide|spelschema|speltips|vedonlyönti|vihje", re.I)
def bing(c):
    k = c["k"]; ws = WORD.get(k["sport"], k["sport"]).split(); word = ws[CI[k["c"]]] if len(ws) == 5 else k["sport"]  # idretter uten oversettelse (f.eks. Curling) søkes med navnet
    base = re.sub(r"\s+(Kvinner|dam|Dam|Kvinder|Naiset|kvenna)$", "", k["n"])
    q = f'"{base}" {word}' + (" " + {"NO": "kvinner", "SE": "dam", "DK": "kvinder", "FI": "naiset", "IS": "kvenna"}[k["c"]] if c["women"] else "")
    lang, cc = MKT[k["c"]]
    b = get("https://www.bing.com/news/search?" + urllib.parse.urlencode({"q": q, "format": "rss", "setlang": lang, "cc": cc, "qft": 'interval="7"'}))
    out = []
    if not b: return c, None
    s = re.sub(r'xmlns:News="[^"]*"', 'xmlns:News="urn:bing"', b.decode("utf-8", "replace"), count=1)
    try: root = ET.fromstring(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", s))
    except Exception: return c, None
    for it in root.iter("item"):
        t = H.unescape(it.findtext("title") or "").strip()
        link = it.findtext("link") or ""; real = urllib.parse.parse_qs(urllib.parse.urlparse(link).query).get("url", [link])[0]
        src = (it.findtext("{urn:bing}Source") or "").strip() or urllib.parse.urlparse(real).hostname
        desc = re.sub(r"<[^>]+>", " ", H.unescape(it.findtext("description") or ""))
        try: when = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc)
        except Exception: continue
        host = urllib.parse.urlparse(real).hostname or ""
        if host.endswith("fotball.no") or "fiksId" in real or "|" in t or re.search(r"(?i)speltips|odds|betting|vedonly|stream|live:|livestream|tv-tider|på tv|slik ser du", t): continue
        # Odds-, resultat- og overgangssider er ikke nyheter
        if JUNK.search(src + " " + (urllib.parse.urlparse(real).hostname or "")) or JUNKT.search(t): continue
        out.append((when, t, desc, real, src))
    return c, out
n_bing = 0
with cf.ThreadPoolExecutor(4) as ex:
    for c, arts in ex.map(bing, order):
        if arts is None: continue
        checked[c["k"]["id"]] = NOW.isoformat(timespec="minutes")
        for when, t, desc, real, src in arts:
            # Bing-treffet må fortsatt nevne laget selv
            if c["k"]["id"] in match(c["k"]["c"], t, desc, (), True, [c["k"]["sport"]] if c["k"]["sport"] in sports_in(t + " " + desc) else []): add(c["k"]["id"], when, t, real, src, pw(real)); n_bing += 1

# ---------- Lagre ----------
for cid in list(items):
    items[cid] = sorted([x for x in items[cid] if datetime.fromisoformat(x[0]) >= CUT], key=lambda x: x[0], reverse=True)[:12]
    if not items[cid]: del items[cid]
known = {k["id"] for k in FAN}
state = {"items": {k: v for k, v in items.items() if k in known}, "checked": {k: v for k, v in checked.items() if k in known}}
os.makedirs(os.path.dirname(STATE), exist_ok=True)
json.dump(state, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
LOCAL = timezone(timedelta(hours=1))
clubs = {cid: [[datetime.fromisoformat(x[0]).astimezone(LOCAL).strftime("%Y-%m-%d"), x[1], x[2], x[3], x[4]] for x in v[:8]] for cid, v in state["items"].items()}
js = "const NEWS = " + json.dumps({"at": NOW.strftime("%Y-%m-%d"), "t": NOW.isoformat(timespec="minutes"), "days": DAYS, "clubs": clubs}, ensure_ascii=False, separators=(",", ":")) + ";"
page = open(HTML, encoding="utf-8").read()
page = re.sub(r"^const NEWS = .*;$", lambda m: js, page, count=1, flags=re.M)
open(HTML, "w", encoding="utf-8").write(page)
print(f"Klubbnyheter: {len(clubs)} lag med saker fra de siste {DAYS} dagene ({n_am} fra Amedia, {n_rss} fra RSS, {n_bing} fra Bing; {len(order)} lag søkt i Bing denne gangen)")
