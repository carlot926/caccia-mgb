# Caccia alla MGB

Un concorso d'eleganza tra amici per scegliere una MG MGB o MGA con paraurti cromati, entro 25.000 €.

- **Sito**: https://carlot926.github.io/caccia-mgb/
- **Annunci**: ogni mattina GitHub Actions lancia `scraper/scraper.py`, che legge AutoScout24 (8 paesi UE), Classic Trader, Marktplaats, 2dehands e Willhaben. Poi `scraper/slim.py` prepara `data/` e il sito viene ripubblicato.
- **Voti, preferiti e proposte**: Supabase, con accesso tramite Google. Lo schema e le regole di sicurezza sono in `supabase/schema.sql`.

## Struttura

| Percorso | Contenuto |
|---|---|
| `index.html` | Il sito: una sola pagina, senza passaggio di build |
| `privacy.html` | Informativa privacy, richiesta da Google per l'accesso |
| `data/` | Annunci del giorno, esito delle fonti, data dell'aggiornamento |
| `assets/` | Foto e foto scontornate delle preferite |
| `scraper/` | Raccolta degli annunci e preparazione dei dati |
| `supabase/` | Schema del database e dati di partenza |
| `.github/workflows/aggiorna.yml` | Aggiornamento giornaliero e pubblicazione |
