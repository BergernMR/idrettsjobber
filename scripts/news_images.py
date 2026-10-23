# Finner delingsbildet (og:image) til hver forsidenyhet i GNEWS og lagrer det i GNEWS.img {lenke: bilde}.
# Bildet vises som forhåndsvisning med lenke til saken, slik som når saken deles. Bruk: python3 scripts/news_images.py index.html
import json, re, sys, html as H, urllib.request
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
i = s.index("const GNEWS = "); j = s.index(";\n", i); G = json.loads(s[i + 14:j])
old = G.get("img", {}); img = {}
urls = [n[3] for v in G["r"].values() for n in v]
for u in urls:
    if u in old: img[u] = old[u]; continue
    try:
        page = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (compatible; AuroraBot/1.0)"}), timeout=20).read(400000).decode("utf-8", "replace")
    except Exception: continue
    m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]*content=["\']([^"\']+)', page) or \
        re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\'](?:og:image|twitter:image)["\']', page)
    if m and m.group(1).startswith("https://"): img[u] = H.unescape(m.group(1))
G["img"] = img
s = s[:i + 14] + json.dumps(G, ensure_ascii=False, separators=(",", ":")) + s[j:]
open(p, "w", encoding="utf-8").write(s)
print(len(img), "av", len(urls), "nyheter har bilde")
