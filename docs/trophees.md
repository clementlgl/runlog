# Trophées — propositions

Idées de trophées pour Runlog, calibrées sur les données au 2026-11-14 :
20 sorties de course (sept.–nov. 2026), 123 km cumulés, 10 km au plus long,
4:50/km de meilleure allure moyenne, 8 séances de fractionné.

✅ = déjà débloqué avec les données actuelles.

## 1. Distance sur une sortie

Paliers bronze → or.

- 5 km ✅
- 10 km ✅
- 15 km
- Semi-marathon (21,1 km)
- Marathon (42,2 km)

## 2. Volume cumulé

- 100 km ✅
- 250 km
- 500 km
- 1 000 km
- Mois à 100 km

## 3. Records perso

Calculés sur la meilleure fenêtre glissante des `samples`, pas sur la moyenne de la sortie.

- Meilleur temps sur 1 km, 5 km et 10 km. Le trophée se redébloque à chaque record battu ; l'historique des dates est conservé.
- Objectifs chrono :
  - 5 km en moins de 25 min
  - 10 km en moins de 50 min
  - 1 km en moins de 4:00

## 4. Régularité

- Série de 4, 8 puis 12 semaines d'affilée avec au moins 2 sorties
- Semaine à 3 sorties ou plus
- 10, 50 et 100 sorties au total

## 5. Fractionné

S'appuie sur `run_analysis` (`workout_type = 'intervals'`).

- Premier fractionné ✅
- 10 séances de fractionné
- 25 séances de fractionné
- « Métronome » : toutes les répétitions d'une séance à moins de 3 % d'écart d'allure

## 6. Qualité de course

- Negative split : 2e moitié plus rapide que la 1re (sorties de 5 km ou plus)
- 1 h de course continue
- Cadence moyenne de 170 spm ou plus sur une sortie de 5 km ou plus

## 7. Ludique

- Lève-tôt : départ avant 7 h, heure locale (via `utc_offset_s`)
- Noctambule : départ après 21 h, heure locale
- Explorateur : 5 parcours GPS distincts (s'appuie sur les `route_shapes`)

## Écartés pour l'instant

- Zones cardio : il faudrait configurer la FC max ou les zones, ce que l'app ne permet pas encore.

## Approche technique proposée

- **Backend** : calcul à la volée depuis `runs`, `samples` et `run_analysis`, exposé par `GET /api/trophies`. Pas de nouvelle table : la date de déblocage est celle de la sortie qui a déclenché le trophée.
- **Frontend** : page `/trophees` avec les trophées débloqués (date + lien vers la sortie) et les trophées verrouillés avec leur progression (ex. « 123 / 250 km »).
- **Page d'une sortie** : badge « 🏆 nouveau » sur la sortie qui débloque un trophée.

## Périmètre

- **Complet** : catégories 1 à 7, avec paliers.
- **Core** : catégories 1 à 4, sans paliers.
