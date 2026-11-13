#!/usr/bin/env bash
# Export Mi Fitness workouts (summaries + per-second detail/GPS) into data/.
# Usage: ./fetch.sh [FROM] [TO]   (defaults: last 30 days)
# Runs mifit through mifit_patch.py, which adds the run record format v7.
set -euo pipefail
cd "$(dirname "$0")"

FROM="${1:-$(date -d '30 days ago' +%F)}"
TO="${2:-$(date +%F)}"
DATA="${DATA_DIR:-../data}"
mkdir -p "$DATA"

mifit() { poetry run python -I mifit_patch.py "$@"; }

mifit export workouts       --from "$FROM" --to "$TO" --long --json "$DATA/workouts_${FROM}_${TO}.json"
mifit export workout_detail --from "$FROM" --to "$TO" --long --json "$DATA/workout_detail_${FROM}_${TO}.json"

ls -lh "$DATA"/
