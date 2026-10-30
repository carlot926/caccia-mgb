"""Raccoglie la galleria completa di foto per ogni auto in concorso (esterni, interni, motore).
Legge le preferite da Supabase (lettura pubblica) e scrive data/gallerie.json: {id: [url, ...]}.
Le gallerie già trovate restano se un sito non risponde. Uso: python3 -I scraper/gallerie.py data/gallerie.json"""
import html, json, os, re, sys, time, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SB = "https://qbalnqgcuhguscrsqclo.supabase.co/rest/v1/preferiti?select=id,dati"
KEY = "sb_publishable_IiyWgOsJUkq_fK8b7eJZ0Q_Luaw7CQ_"
MAX = 40

def get(url, headers=None):
    time.sleep(1.2)
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def autoscout(url):
    h = get(url)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    imgs = json.loads(m.group(1))["props"]["pageProps"]["listingDetails"].get("images") or []
    return [re.sub(r"/\d+x\d+\.webp$", "/1280x960.webp", u) for u in imgs]

def classic_trader(url):
    h = html.unescape(get(url))
    return list(dict.fromkeys(re.findall(r'"originalImageUrl":\[0,"(https://cdn\.classic-trader\.com/[^"]+)"\]', h)))

def wordpress(url):
    h = get(url)
    found = re.findall(r'https://[^"\'\s)]+/wp-content/uploads/[^"\'\s)]+?\.(?:jpe?g|png|webp)', h)
    full = [u for u in found if not re.search(r"-\d+x\d+\.(?:jpe?g|png|webp)$", u)]
    return [u for u in dict.fromkeys(full) if not re.search(r"logo|icon|favicon|placeholder", u, re.I)]

def gallery(d):
    for url in [d.get("url"), d.get("url_alternativo")]:
        if not url:
            continue
        try:
            if "autoscout24." in url:
                return autoscout(url)
            if "classic-trader.com" in url:
                return classic_trader(url)
            if "/cars-for-sale/" in url or "autostorico" in url:
                return wordpress(url)
        except Exception as e:
            print("  non letta:", url, e, file=sys.stderr)
    return []

def main():
    out = sys.argv[1]
    old = json.load(open(out)) if os.path.exists(out) else {}
    favs = json.loads(urllib.request.urlopen(urllib.request.Request(SB, headers={"apikey": KEY}), timeout=30).read())
    res = {}
    for f in favs:
        g = gallery(f["dati"])[:MAX] or old.get(f["id"], [])
        if g:
            res[f["id"]] = g
        print(f["id"], len(g), "foto", file=sys.stderr)
    json.dump(res, open(out, "w"), indent=0)

if __name__ == "__main__":
    main()
