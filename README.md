# Aurora – Idretten i Norden

Jobber, utdanning, arrangementer og klubber innen idrett i Norge, Sverige, Danmark, Finland og Island.

Hele nettsiden ligger i `index.html`. Siden publiseres med GitHub Pages fra grenen `main`.

## Automatisk oppdatering

`.github/workflows/oppdater.yml` kjører hver time og henter:

- Neste kamp og siste resultater for fotballklubber i alle divisjoner (FotMob)
- Kamper for lag i andre lagidretter (TheSportsDB, lag-id-er i `scripts/tsdb_teams.json`)
- Fotballtabellene (FotMob)

Klubber uten data får lenke til terminlista hos sitt nasjonale forbund.
