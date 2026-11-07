# TAF WAREHOUSE V4.4 — Confirmations critiques et reprise

Les endpoints suivants acceptent désormais `Idempotency-Key` :
- `POST /api/transfers/{id}/dispatch`
- `POST /api/transfers/{id}/receive`
- `POST /api/releases/{id}/complete`
- `POST /api/counts/{id}/review`

La clé et l'empreinte de la requête sont conservées dans la même transaction SQLite que la mutation. Une répétition identique retourne le résultat initial. Un contenu différent avec la même clé est refusé (409). Le client web génère et conserve une clé en session pour ces opérations lors des tentatives de reprise.

Limites : pas de garantie de fonctionnement multi-instance PostgreSQL, pas de mode hors-ligne, pas de test de matériel réel. Une nouvelle signature manuscrite constitue un nouveau contenu : la reprise doit réutiliser exactement les mêmes données. Ne pas exposer la version locale sur Internet.
