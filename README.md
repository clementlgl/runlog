# mifitness-fetch

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

## Session Xiaomi

`~/.mifit/session.json` est monté dans le backend (utilisé par `POST /api/sync`).
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
