# Recalage GPS sur les chemins (map matching) — test

Objectif : corriger l'imprécision du GPS en recalant les traces sur les chemins OpenStreetMap, pour une carte plus propre et une distance plus juste. Deux outils comparés sur 4 sorties réelles (dont une en forêt sur petits sentiers sinueux et un fractionné).

## Résultats

| Sortie | Montre | GPS brut | mappymatch (LCSS) | Valhalla (Meili, piéton) |
|---|---|---|---|---|
| Fractionné, parc boisé | 5 980 m | 6 026 m | 6 136 m (+2 %) | 6 162 m (+2 %) |
| Continue | 6 720 m | 6 739 m | 7 175 m (+6 %) | 6 852 m (+2 %) |
| Continue | 8 094 m | 8 145 m | 9 183 m (+13 %) | 8 442 m (+4 %) |
| Continue, 10 km | 10 021 m | 10 061 m | 10 614 m (+5 %) | 10 680 m (+6 %) |

Écart médian point GPS → chemin : 6–11 m (mappymatch), 4–6 m (Valhalla).

- **mappymatch** : écarté. Les sentiers sinueux (pourtant présents dans OSM) sont remplacés par les allées voisines plus droites, et des allers-retours aux carrefours gonflent la distance (jusqu'à +1 km). ~75 s par sortie (relecture du PBF régional ; corrigeable avec un extrait réduit).
- **Valhalla** : retenu. Suit les sentiers, pas d'allers-retours inventés, ~0,1 s par sortie. Reste quelques petites boucles parasites et une distance un peu au-dessus de la montre : garder la distance de la montre comme référence, utiliser le tracé recalé pour la carte.

Réglages Valhalla qui comptent :

- `search_radius: 50` (m) : à 30 m, un seul point trop loin de tout chemin coupe le tracé et la réponse s'arrête là.
- À une discontinuité, Valhalla renvoie la suite dans `alternates` : les parts sont assemblées dans l'ordre (`original_index`), les trous comblés par le GPS brut.

## Reproduire

Données OSM : extrait régional [Geofabrik](https://download.geofabrik.de/europe/france.html) (`aquitaine-latest.osm.pbf`, ~290 Mo), réduit à la zone des sorties. Aucune requête Overpass (l'API publique refuse l'usage automatisé).

```bash
cd experiments/map-matching
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
mkdir -p work/custom_files
curl -fL -o work/aquitaine-latest.osm.pbf https://download.geofabrik.de/europe/france/aquitaine-latest.osm.pbf
# Zone des sorties + marge (west south east north), ~4 min sur le PBF régional
.venv/bin/python clip_pbf.py work/aquitaine-latest.osm.pbf work/custom_files/zone.osm.pbf <w> <s> <e> <n>
```

mappymatch (réseau piéton construit localement depuis le PBF) :

```bash
.venv/bin/python match_runs.py work/custom_files/zone.osm.pbf ../../data/workout_detail_all.json work/out.json <start_epoch> [...]
```

Valhalla (tuiles construites au premier démarrage, ~1-2 min) puis recalage et carte :

```bash
docker compose up -d
until curl -sf localhost:8002/status >/dev/null; do sleep 5; done
.venv/bin/python valhalla_runs.py work/out.json work/out_valhalla.json
.venv/bin/python build_compare.py work/out_valhalla.json work/compare.html
python3 -m http.server 8765 --bind 127.0.0.1 --directory work   # http://localhost:8765/compare.html
docker compose down
```

> `work/` (traces GPS, carte, extraits OSM) est ignoré par git : les traces révèlent où l'on court.

## Intégration envisagée dans Runlog

- Valhalla en service Docker dans le homelab (extrait réduit à la métropole : quelques Mo, tuiles en 1-2 min) ; une sortie hors zone garde son tracé brut.
- Backend : `VALHALLA_URL` optionnel ; tracé recalé calculé à l'analyse et stocké à part (le tracé brut reste la référence).
- Interface : bascule « Tracé recalé / GPS brut » sur la carte.
