#!/usr/bin/env python3
"""Caccia alla MGB: raccoglie annunci MG MGB / MGA chrome bumper da portali europei,
li normalizza in EUR, assegna un punteggio e scrive listings.json + fonti.json.

Uso:  python3 -I scraper.py --out DIR [--previous listings.json] [--budget 25000]

Fonti: AutoScout24 (IT, DE, AT, BE, NL, FR, ES, LU), Classic Trader, Marktplaats (NL),
2dehands (BE), Willhaben (AT). Legge solo le normali pagine di ricerca pubbliche,
con una pausa tra le richieste. I siti protetti da anti-bot non vengono toccati.
"""
import argparse, html, json, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
PAUSE = 1.5
MAX_PRICE_KEEP = 30000      # teniamo anche un po' sopra budget, marcati
CHROME_LAST_YEAR = 1974     # dal MY1975 (set. 1974) paraurti in gomma
FALLBACK_FX = {"EUR": 1.0, "GBP": 1.17, "CHF": 1.05, "SEK": 0.088, "DKK": 0.134, "NOK": 0.086, "PLN": 0.235, "CZK": 0.04}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "it-IT,it;q=0.9,en;q=0.8"})
    time.sleep(PAUSE)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def next_data(h):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h, re.S)
    return json.loads(m.group(1))["props"]["pageProps"] if m else {}

def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def fx_rates():
    try:
        x = fetch("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml")
        rates = {c: 1 / float(r) for c, r in re.findall(r"currency='(\w+)' rate='([\d.]+)'", x)}
        rates["EUR"] = 1.0
        return rates
    except Exception:
        return FALLBACK_FX

def year_of(s):
    m = re.search(r"(19[5-9]\d)", str(s or ""))
    return int(m.group(1)) if m else None

# ---------------------------------------------------------------- sorgenti

def autoscout(model):
    out, page = [], 1
    while page <= 20:
        url = (f"https://www.autoscout24.it/lst/mg/{model}?atype=C&cy=D%2CA%2CB%2CE%2CF%2CI%2CL%2CNL"
               f"&fregto=1976&priceto={MAX_PRICE_KEEP}&sort=price&desc=0&ustate=N%2CU&page={page}")
        p = next_data(fetch(url))
        for l in p.get("listings", []):
            v, loc = l.get("vehicle", {}), l.get("location", {})
            km = l.get("tracking", {}).get("mileage")
            out.append(dict(
                id="as24-" + l["id"], fonte="AutoScout24",
                url="https://www.autoscout24.it" + l["url"],
                titolo=" ".join(x for x in [v.get("make"), v.get("model"), v.get("modelVersionInput")] if x),
                prezzo=l.get("price", {}).get("priceRaw"), valuta="EUR",
                anno=year_of(l.get("tracking", {}).get("firstRegistration")),
                km=int(km) if km and km.isdigit() and int(km) < 900000 else None,
                paese=loc.get("countryCode"), citta=loc.get("city"),
                venditore="privato" if l.get("seller", {}).get("type") == "PrivateSeller" else "concessionario",
                foto=(l.get("images") or [None])[0], danneggiata=bool(v.get("isCurrentlyDamaged")),
                tipo_vendita="annuncio", testo="", _detail="as24"))
        if page >= (p.get("numberOfPages") or 1):
            break
        page += 1
    return out

def _astro(v):
    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], int):
        return [_astro(i) for i in v[1]] if v[0] == 1 else _astro(v[1])
    if isinstance(v, dict):
        return {k: _astro(x) for k, x in v.items()}
    return v

def classic_trader(model):
    out = []
    for page in range(1, 15):
        try:
            h = fetch(f"https://www.classic-trader.com/uk/cars/search/mg/{model}?page={page}")
        except urllib.error.HTTPError as e:
            if e.code == 404 and page > 1:
                break
            raise
        ads = []
        for attrs in re.findall(r"<astro-island([^>]*)>", h):
            if "ResultPageCarData" not in attrs:
                continue
            m = re.search(r'props="([^"]*)"', attrs)
            ads.append(_astro(json.loads(html.unescape(m.group(1))))["vehicleAd"])
        if not ads:
            break
        for a in ads:
            pr, loc, s = a.get("price") or {}, a.get("location") or {}, a.get("seller") or {}
            body = ((a.get("vehicle") or {}).get("bodyDetailed") or {}).get("label") or ""
            km = a.get("mileageByUnit")
            if km and a.get("mileageUnit") == "mls":
                km = round(km * 1.609)
            out.append(dict(
                id=f"ct-{a['id']}", fonte="Classic Trader", url=a.get("url"),
                titolo=(a.get("titleBySeller") or a.get("title") or "") + (f" ({body})" if body else ""),
                prezzo=None if pr.get("isOnRequest") else pr.get("originalAmount"),
                valuta=pr.get("originalCurrency") or "EUR",
                anno=a.get("yearOfProduction"), km=km,
                paese=loc.get("countryCode"), citta=loc.get("city"),
                venditore="concessionario" if s.get("isDealer") else ("casa d'aste" if s.get("isAuctionHouse") else "privato"),
                foto=((a.get("images") or [{}])[0].get("thumbnailUrl") or {}).get("medium"),
                danneggiata=False, perizia=bool(a.get("hasReport")), n_foto=a.get("imagesCount"),
                tipo_vendita="asta" if pr.get("isAuctionSale") else "annuncio",
                testo=a.get("titleBySeller") or "", _detail="ct"))
        if len(ads) < 15:
            break
    return out

def adevinta(host, fonte, paese, query):
    """Marktplaats (NL) e 2dehands (BE): stessa piattaforma."""
    p = next_data(fetch(f"https://www.{host}/l/auto-s/mg/q/{query}/"))
    out = []
    for l in p.get("searchRequestAndResponse", {}).get("listings", []):
        attrs = {a["key"]: a.get("value") for a in l.get("attributes", [])}
        pi = l.get("priceInfo", {})
        cents = pi.get("priceCents") or 0
        pics = l.get("pictures") or []
        foto = (pics[0].get("mediumUrl") or pics[0].get("largeUrl")) if pics else None
        if foto and foto.startswith("//"):
            foto = "https:" + foto
        out.append(dict(
            id=f"{host.split('.')[0]}-{l['itemId']}", fonte=fonte, url=f"https://www.{host}{l.get('vipUrl','')}",
            titolo=l.get("title"), prezzo=cents / 100 if cents else None, valuta="EUR",
            anno=year_of(attrs.get("constructionYear")) or year_of(l.get("title")),
            km=int(attrs["mileage"]) if str(attrs.get("mileage", "")).isdigit() else None,
            paese=paese, citta=(l.get("location") or {}).get("cityName"),
            venditore="privato" if not (l.get("sellerInformation") or {}).get("showWebsiteUrl") and "classic" not in str((l.get("sellerInformation") or {}).get("sellerName", "")).lower() else "concessionario",
            foto=foto, danneggiata=False,
            tipo_vendita="offerta" if pi.get("priceType") in ("FAST_BID", "MIN_BID", "BID") else "annuncio",
            testo=l.get("description") or l.get("categorySpecificDescription") or "", _detail=None))
    return out

def willhaben(query):
    p = next_data(fetch(f"https://www.willhaben.at/iad/gebrauchtwagen/auto/gebrauchtwagenboerse?keyword={query}&rows=90"))
    out = []
    for ad in (p.get("searchResult", {}).get("advertSummaryList", {}) or {}).get("advertSummary", []):
        a = {x["name"]: (x.get("values") or [None])[0] for x in ad.get("attributes", {}).get("attribute", [])}
        out.append(dict(
            id=f"wh-{ad.get('id')}", fonte="Willhaben",
            url="https://www.willhaben.at/iad/" + (a.get("SEO_URL") or ""),
            titolo=a.get("HEADING") or ad.get("description"),
            prezzo=float(a["PRICE"]) if a.get("PRICE") else None, valuta="EUR",
            anno=year_of(a.get("YEAR_MODEL")), km=int(float(a["MILEAGE"])) if a.get("MILEAGE") else None,
            paese="AT", citta=a.get("LOCATION"),
            venditore="privato" if a.get("ISPRIVATE") == "1" else "concessionario",
            foto=a.get("MMO"), danneggiata=False, tipo_vendita="annuncio",
            testo=ad.get("description") or "", _detail=None))
    return out

def detail_text(r):
    """Scarica la descrizione completa per i candidati (solo AutoScout24 e Classic Trader)."""
    try:
        h = fetch(r["url"])
        if r["_detail"] == "as24":
            ld = next_data(h).get("listingDetails", {})
            v = ld.get("vehicle", {})
            r["carrozzeria"] = v.get("bodyType")
            r["colore"] = v.get("bodyColor")
            return strip_tags(ld.get("description"))
        if r["_detail"] == "ct":
            texts = []
            for attrs in re.findall(r"<astro-island([^>]*)>", h):
                m = re.search(r'props="([^"]*)"', attrs)
                if m and "description" in m.group(1):
                    for d in re.findall(r'"description":\[0,"((?:[^"\\]|\\.)*)"\]', html.unescape(m.group(1))):
                        texts.append(json.loads('"' + d + '"'))
            return strip_tags(max(texts, key=len)) if texts else ""
    except Exception:
        return ""
    return ""

# ---------------------------------------------------------------- filtri e punteggio

NOT_MODEL = re.compile(r"\b(midget|mgc|mg ?c\b|mgf|tf ?1\d|zr|zs|mg ?3|mg ?4|mg ?5|hs\b|ehs|marvel|cyberster|v8\b|metro|maestro|montego|y.?type|t.?type|td\b|tc\b)", re.I)
MODEL_RE = re.compile(r"\bmg\s*-?\s*[ab]\b|\bmg[ab]\b", re.I)
PARTS = re.compile(r"\b(ricambi|onderdelen|ersatzteile|pièces|parts?|motore|motor|engine|hardtop|velgen|cerchi|felgen|wheels?|bumper set|stoßstange|sedili|stoelen|kofferbak|cover)\b", re.I)
RUBBER = re.compile(r"rubber.?bumper|gummi.?(stoß|stoss)|paraurti in gomma|rubberen bumper|caoutchouc", re.I)
CHROME = re.compile(r"chrom|cromat|chroom", re.I)
GT_RE = re.compile(r"\bgt\b|coup[eé]", re.I)
RHD = re.compile(r"\brhd\b|guida a destra|rechtsgestuurd|rechtslenker|volant à droite|right.hand", re.I)

GOOD = [
    (r"restaur(at[ao]|ata|ato|ed|iert|ation|eerd)|gerestaureerd|rebuilt|ricostruit|overhaul|revisionat|überholt|gereviseerd", 8, "restaurata/revisionata"),
    (r"\basi\b|fiva|targa oro|h.kennzeichen|oldtimer.?zulassung|heritage certificate|british motor heritage", 5, "certificazioni storiche"),
    (r"rust.?free|senza ruggine|rostfrei|roestvrij|sans rouille|no rust|roestvrije", 6, "dichiarata senza ruggine"),
    (r"overdrive", 3, "overdrive"),
    (r"documenta|fatture|invoices|rechnungen|facturen|storico|history file|service history|onderhoudshistorie", 4, "documentazione"),
    (r"matching numbers|numeri originali", 3, "matching numbers"),
    (r"tüv|tuv|\bapk\b|\bct\b ok|revisione|collaudo|§ ?57a|pickerl", 3, "revisione/TÜV valida"),
    (r"concours|top condition|ottime condizioni|condizioni eccellenti|sehr gut|zustand ?[12]\b|uitstekende staat|excellent", 5, "ottime condizioni dichiarate"),
    (r"nuov[ao] cappott|new hood|neues verdeck|nieuwe kap|soft.?top nuov", 2, "capote nuova"),
    (r"lhd|guida a sinistra|linksgestuurd|linkslenker|left.hand", 2, "guida a sinistra"),
]
BAD = [
    (r"da restaurare|to restore|for restoration|restoration project|project car|projekt|restauratieproject|restauratie object|à restaurer|barn.?find|scheunenfund|schuurvondst", -20, "da restaurare"),
    (r"non marciante|not running|nicht fahrbereit|niet rijdend|ne roule pas|motore bloccato|seized", -15, "non marciante"),
    (r"incidentat|damaged|unfall|schade aan|accidentée", -10, "incidentata"),
    (r"(?<!senza )(?<!no )ruggine|\brust(?!.?free)|(?<!r)roest(?!vrij)|rost(?!frei)|rouille|durchgerostet", -6, "ruggine menzionata"),
    (r"senza documenti|no papers|ohne papiere|zonder papieren|sans papiers|libretto mancante", -15, "senza documenti"),
    (r"asta|auction|veiling|versteigerung|enchère", -2, "in asta (prezzo finale incerto)"),
]
HOME = {"IT": 10, "FR": 8, "AT": 8, "DE": 8, "CH": 4, "BE": 7, "NL": 7, "LU": 7, "ES": 6, "GB": 2}

def keep(r):
    t = f"{r['titolo']} {r['testo']}"
    if NOT_MODEL.search(r["titolo"] or ""):
        return False
    if r["fonte"] in ("Marktplaats", "2dehands", "Willhaben") and not MODEL_RE.search(r["titolo"] or ""):
        return False
    if r["prezzo"] is not None and (r["prezzo"] < 3000 or (r["prezzo"] < 6000 and PARTS.search(r["titolo"] or ""))):
        return False
    if r["anno"] and r["anno"] < 1955:
        return False
    if RUBBER.search(t) and not CHROME.search(t):
        return False
    return True

def score(r, budget):
    t = f"{r['titolo']} {r['testo']}"
    note, pts = [], 0
    # paraurti
    if r["anno"] and r["anno"] <= 1973:
        r["paraurti"] = "chrome"
    elif r["anno"] == 1974:
        r["paraurti"] = "chrome (verificare: 1974 di transizione)"
    elif CHROME.search(t):
        r["paraurti"] = "chrome (conversione?)"
    elif r["anno"] is None:
        r["paraurti"] = "da verificare"
    else:
        r["paraurti"] = "rubber"
    if r["paraurti"] == "rubber":
        r["punteggio"] = 0
        return r
    r["modello"] = "MGA" if re.search(r"\bmg\s*a\b|\bmga\b", t, re.I) and not re.search(r"\bmgb\b|mg\s*b\b", r["titolo"] or "", re.I) else "MGB"
    r["carrozzeria"] = "GT" if GT_RE.search(f"{r['titolo']} {r.get('carrozzeria') or ''}") else "Roadster"

    # condizione dal testo (0..45 circa)
    cond = 18
    for pat, w, label in GOOD + BAD:
        if re.search(pat, t, re.I):
            cond += w
            note.append(("+" if w > 0 else "−") + " " + label)
    if r.get("danneggiata"):
        cond -= 10
        note.append("− segnalata come danneggiata")
    if r.get("perizia"):
        cond += 4
        note.append("+ perizia disponibile")
    cond = max(0, min(45, cond))
    pts += cond

    # prezzo (0..25): ideale tra 14k e il budget; sotto 9k quasi sempre un progetto
    p = r["prezzo_eur"]
    if p is None:
        pts += 8
        note.append("prezzo non indicato")
    elif p > budget:
        pts += max(0, 10 - (p - budget) / 300)
        note.append(f"sopra budget di {round(p - budget):,} €".replace(",", "."))
    elif p >= 14000:
        pts += 25
    elif p >= 9000:
        pts += 18
    else:
        pts += 8
        note.append("prezzo molto basso: probabile da sistemare")

    # chilometri (0..8)
    if r["km"]:
        pts += 8 if r["km"] < 60000 else 6 if r["km"] < 100000 else 4 if r["km"] < 150000 else 2
    else:
        pts += 3

    # logistica dall'Italia (0..10) e guida a destra
    pts += HOME.get(r["paese"] or "", 5)
    if RHD.search(t):
        pts -= 6
        note.append("− guida a destra")

    # affidabilità annuncio (0..7)
    pts += 4 if r["venditore"] == "concessionario" else 2
    if len(r["testo"]) > 400:
        pts += 3
    if r["paraurti"].startswith("chrome (verificare"):
        pts -= 2
    r["punteggio"] = round(max(0, min(100, pts)))
    r["note"] = "; ".join(note)
    return r

def dedupe(rows):
    """Stessa auto su più portali: stesso prezzo, anno e km compatibili. Tiene l'annuncio più ricco."""
    groups = {}
    for r in sorted(rows, key=lambda r: -len(r["testo"] or "")):
        if r["prezzo_eur"] is None:
            groups[r["id"]] = r
            continue
        key = (r["prezzo_eur"], r["anno"], r.get("modello"))
        hit = groups.get(key)
        if hit and (not hit["km"] or not r["km"] or abs(hit["km"] - r["km"]) < 2000):
            hit["anche_su"] = ", ".join(x for x in [hit.get("anche_su"), r["fonte"]] if x)
            continue
        groups[key if key not in groups else r["id"]] = r
    return list(groups.values())

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--previous")
    ap.add_argument("--budget", type=float, default=25000)
    ap.add_argument("--details", type=int, default=60, help="quanti candidati approfondire")
    a = ap.parse_args()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    jobs = [
        ("AutoScout24", lambda: autoscout("mgb") + autoscout("mga")),
        ("Classic Trader", lambda: classic_trader("mgb") + classic_trader("mga")),
        ("Marktplaats", lambda: adevinta("marktplaats.nl", "Marktplaats", "NL", "mgb") + adevinta("marktplaats.nl", "Marktplaats", "NL", "mga")),
        ("2dehands", lambda: adevinta("2dehands.be", "2dehands", "BE", "mgb") + adevinta("2dehands.be", "2dehands", "BE", "mga")),
        ("Willhaben", lambda: willhaben("mgb") + willhaben("mga")),
    ]
    rows, fonti = {}, []
    for name, fn in jobs:
        t0 = time.time()
        try:
            got = fn()
            for r in got:
                rows.setdefault(r["id"], r)
            fonti.append(dict(fonte=name, stato="ok", annunci_letti=len(got), secondi=round(time.time() - t0), aggiornato=now))
        except Exception as e:
            fonti.append(dict(fonte=name, stato="errore", annunci_letti=0, errore=str(e)[:200], secondi=round(time.time() - t0), aggiornato=now))
        print(fonti[-1], file=sys.stderr)

    fx = fx_rates()
    rows = [r for r in rows.values() if keep(r)]
    for r in rows:
        r["prezzo_eur"] = round(r["prezzo"] * fx.get(r["valuta"], 1.0)) if r["prezzo"] else None
    rows = [r for r in rows if r["prezzo_eur"] is None or r["prezzo_eur"] <= MAX_PRICE_KEEP]

    # descrizioni complete per i candidati più promettenti
    prelim = sorted((score(dict(r), a.budget) for r in rows), key=lambda r: -r["punteggio"])
    want = {r["id"] for r in prelim if r["_detail"] and r["paraurti"] != "rubber"}
    for r in [r for r in rows if r["id"] in want][: a.details]:
        txt = detail_text(r)
        if txt:
            r["testo"] = txt

    prev = {}
    if a.previous:
        try:
            prev = {r["id"]: r for r in json.load(open(a.previous))["rows"]}
        except Exception:
            pass
    final = []
    for r in rows:
        r = score(r, a.budget)
        if r["paraurti"] == "rubber":
            continue
        old = prev.get(r["id"], {})
        r["primo_avvistamento"] = old.get("primo_avvistamento") or now[:10]
        r["nuovo"] = not old
        r["prezzo_precedente"] = old.get("prezzo_eur") if old.get("prezzo_eur") not in (None, r["prezzo_eur"]) else old.get("prezzo_precedente")
        r["entro_budget"] = r["prezzo_eur"] is not None and r["prezzo_eur"] <= a.budget
        r["verdetto"] = old.get("verdetto", "")       # riscritto dalla revisione giornaliera
        r["testo"] = (r["testo"] or "")[:1500]
        r.pop("_detail", None)
        r["aggiornato"] = now
        final.append(r)
    final = dedupe(final)
    final.sort(key=lambda r: (-r["punteggio"], r["prezzo_eur"] or 1e9))
    for i, r in enumerate(final, 1):
        r["rank"] = i

    import os
    os.makedirs(a.out, exist_ok=True)
    json.dump({"rows": final}, open(os.path.join(a.out, "listings.json"), "w"), ensure_ascii=False)
    json.dump({"rows": fonti}, open(os.path.join(a.out, "fonti.json"), "w"), ensure_ascii=False)
    print(f"{len(final)} annunci chrome bumper, {sum(r['entro_budget'] for r in final)} entro budget", file=sys.stderr)

if __name__ == "__main__":
    main()
