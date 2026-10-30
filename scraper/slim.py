"""Prepara i dati per il sito: toglie le foto incorporate, aggiunge la foto grande e
conserva verdetti e "vettura del giorno" dell'ultima revisione.
Uso: python3 -I scraper/slim.py <cartella output scraper> <cartella data del sito>"""
import json, os, sys
from datetime import datetime, timezone

src, dst = sys.argv[1], sys.argv[2]
new = json.load(open(os.path.join(src, "listings.json")))["rows"]
prev_path = os.path.join(dst, "listings.json")
prev = {r["id"]: r for r in json.load(open(prev_path))["rows"]} if os.path.exists(prev_path) else {}
pick = next((i for i, r in prev.items() if r.get("consigliata")), None)
ids = {r["id"] for r in new}
for r in new:
    r.pop("foto_data", None)
    if r.get("foto"):
        r["foto_hd"] = r["foto"].replace("/250x188.webp", "/720x540.webp")
    old = prev.get(r["id"], {})
    if not r.get("verdetto") and old.get("verdetto"):
        r["verdetto"] = old["verdetto"]
    r["consigliata"] = bool(r.get("consigliata")) or (r["id"] == pick and not any(x.get("consigliata") for x in new))
if not any(r["consigliata"] for r in new) and new:
    best = next((r for r in new if r.get("entro_budget")), new[0])
    best["consigliata"] = True
json.dump({"rows": new}, open(prev_path, "w"), ensure_ascii=False)
os.replace(os.path.join(src, "fonti.json"), os.path.join(dst, "fonti.json")) if os.path.exists(os.path.join(src, "fonti.json")) else None
json.dump({"aggiornato": datetime.now(timezone.utc).isoformat(timespec="seconds")}, open(os.path.join(dst, "meta.json"), "w"))
print(len(new), "annunci;", sum(1 for r in new if r.get("verdetto")), "con verdetto")
