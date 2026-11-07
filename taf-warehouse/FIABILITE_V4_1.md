# TAF WAREHOUSE V4.1 — Fiabilité des opérations (chantier 3)

## Implémenté
- Idempotence des demandes de sortie et de transfert via l'en-tête HTTP `Idempotency-Key` (8–128 caractères ASCII alphanumériques, tiret, point, underscore).
- Enregistrement atomique de la clé, de l'empreinte du corps et de la réponse dans la même transaction SQLite `BEGIN IMMEDIATE` que la création métier.
- Une répétition avec même clé et même corps renvoie le même identifiant sans créer un second dossier ; même clé et corps différent = HTTP 409.
- Une réservation de sortie active interdit désormais aussi un déplacement d'emplacement de l'unité.
- Test de cinq demandes simultanées avec la même clé, plus test de réutilisation contradictoire.

## Utilisation API
`POST /api/releases` ou `POST /api/transfers` avec `Authorization: Bearer ...` et `Idempotency-Key: <UUID stable pour cette opération>`.
Conserver la même clé pendant les réessais après coupure réseau. Pour une nouvelle opération, utiliser une nouvelle clé.

## Limites importantes
- La protection idempotente est **optionnelle** pour préserver les clients existants ; l'interface navigateur ne génère pas encore systématiquement les clés.
- Les autres opérations critiques (réception physique, remise signée, inventaire, confirmation de transfert) ne sont pas encore toutes couvertes par cette idempotence.
- SQLite reste réservé à une seule instance locale. Aucun mécanisme PostgreSQL multi-instance, synchronisation hors-ligne, ou reprise complète de panne n'est livré.
- Les tests sont automatisés en environnement local et ne constituent pas des tests de charge ni une recette terrain.
