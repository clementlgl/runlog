# Runlog

Analyse des courses Mi Fitness : FastAPI + DuckDB (backend) et SvelteKit (frontend), lancés avec Docker Compose.

```
backend/   FastAPI, DuckDB, ingestion Polars, mifit_patch.py (format v7), fetch.sh
frontend/  SvelteKit 3 + Tailwind 4, proxy /api/* -> backend
data/      exports JSON mifit + runs.duckdb (non versionné)
```

## Lancer

```bash
docker compose up -d --build
```

- App : http://localhost:3000
- API + docs : http://localhost:8000/docs

## Configuration

Optionnelle : copier `.env.example` en `.env` (non versionné) et ajuster. Sans `.env`, les valeurs par défaut conviennent à un poste local.

| Variable | Défaut | Rôle |
|---|---|---|
| `RUNLOG_BIND` | `127.0.0.1` | Interface d'écoute de l'app (`0.0.0.0` pour la joindre depuis le LAN, derrière Caddy) |
| `RUNLOG_PORT` | `3000` | Port de l'app sur l'hôte |
| `RUNLOG_ORIGIN` | `http://localhost:<RUNLOG_PORT>` | URL publique exacte de l'app ; à défaut, la synchro est refusée (CSRF) |
| `BACKEND_BIND` / `BACKEND_PORT` | `127.0.0.1` / `8000` | API et `/docs`, inutiles à l'app |
| `MIFIT_REGION` | `de` | Région du compte Xiaomi, imposée à la connexion (`de` = Europe) |
| `MIFIT_SESSION_DIR` | `~/.mifit` | Dossier contenant `session.json` |
| `RUNLOG_DATA_DIR` | `./data` | Exports JSON et base `runs.duckdb` |

Exemple derrière un reverse proxy :

```ini
RUNLOG_BIND=0.0.0.0
RUNLOG_ORIGIN=https://runlog.example.com
MIFIT_SESSION_DIR=/opt/runlog/mifit-session
RUNLOG_DATA_DIR=/opt/runlog/data
```

## Session Xiaomi

Connexion depuis l'app : panneau **Synchroniser**, bouton **Se connecter à Xiaomi**. La page de connexion Xiaomi s'ouvre dans un nouvel onglet : s'y connecter à son compte et valider ; la session est enregistrée avec la région `MIFIT_REGION`.

`session.json` (dossier `MIFIT_SESSION_DIR`) est monté dans le backend, utilisé par la synchro.
Il donne accès à tout le compte Xiaomi : `chmod 600`, jamais dans git.
Après un `mifit login`, remettre `"region": "de"` dans ce fichier (compte FR).

## API

| Méthode | Route | |
|---|---|---|
| GET | `/api/runs?sport=running` | liste des séances |
| GET | `/api/runs/{id}` | résumé |
| GET | `/api/runs/{id}/samples` | FC, distance, pas, cadence, allure à la seconde |
| GET | `/api/runs/{id}/track` | GPS `[lon, lat]` |
| GET | `/api/stats/weekly` | volume hebdo |
| POST | `/api/sync?days=30` | récupère depuis le cloud Xiaomi puis ingère |
| POST | `/api/ingest` | ré-ingère les JSON de `data/` |

## Dev sans Docker

```bash
cd backend && poetry install && poetry run uvicorn app.main:app --reload
```
```bash
cd frontend && pnpm install && pnpm dev
```

## Développement

Hooks pre-commit (ruff, Prettier, contrôles de base), après `pnpm install` dans `frontend/` :

```bash
pre-commit install
```

La CI (`.github/workflows/ci.yml`) lance pre-commit, les tests backend, `pnpm check`, le build frontend et `docker compose build` sur chaque PR, chaque push sur `main` et à la demande.
