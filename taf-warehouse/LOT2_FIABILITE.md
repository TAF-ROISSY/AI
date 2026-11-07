# TAF WAREHOUSE V4.6 — Lot 2 : fiabilité des opérations

Version de recette locale. Pas de déploiement AWS. Pas homologuée pour la production.

## Règles métier validées par TAF (7 novembre 2026)

- Un blocage d'incident **peut être levé alors que l'incident est encore ouvert**. Lever le blocage ne clôt pas l'incident.
- Les choix du lot 1 sont confirmés :
  - le Super Admin ne lève les blocages qu'après s'être accordé le droit ;
  - la remise signée est faite par le magasin ;
  - le volume est conservé lors d'une sortie partielle.

## Corrections

| Sujet | Avant (V4.5) | Après (V4.6) |
|---|---|---|
| Transactions | Réceptions, clients, utilisateurs, mots de passe, transporteurs, missions, tâches, incidents (mise à jour), litiges, planification et déconnexion étaient enregistrés instruction par instruction : une panne en cours de route laissait des données partielles. | Ces opérations sont validées en bloc par le nouvel utilitaire `tx()` : tout ou rien. |
| Documents | Le fichier était écrit avant l'enregistrement en base, ce qui pouvait laisser un fichier orphelin. | La ligne en base et le fichier sont créés ensemble. En cas d'échec, la ligne est annulée et le fichier supprimé. |
| Réceptions | Un double appui créait deux réceptions. | Anti-doublon (`Idempotency-Key`), envoyé automatiquement par l'interface. |
| Signatures | `GET /api/releases` et `GET /api/transfers` renvoyaient toutes les images de signature. | Les listes ne renvoient plus que `has_signature`. Les signatures restent dans les bons PDF. |
| Réception de transfert | Toujours « conforme », sans contrôle. | Le réceptionnaire saisit les colis reçus et l'état : conforme, manquant, excédent, avarie ou erreur d'identification. Tout écart entraîne le statut `discrepancy`, un blocage `ecart_transfert` et une notification. **Le stock reste à la quantité expédiée** tant qu'aucune décision n'est prise. |
| Décision sur écart de transfert | Inexistante. | `POST /api/transfers/{id}/discrepancy-review` est réservé à l'exploitation, au responsable ou à l'admin de l'entrepôt d'arrivée, et la personne doit être différente du réceptionnaire. Elle retient soit la quantité constatée (stock et poids corrigés, mouvement `transfer_adjustment`, journal avant/après), soit la quantité expédiée. Le transfert passe à `received`. **Le blocage reste en place** jusqu'à une levée autorisée. |
| Inventaire | Une correction de quantité laissait le poids inchangé. | Le poids est recalculé au prorata, avec une trace dans le journal. |

Compatibilité : `POST /api/transfers/{id}/receive` sans corps reste accepté et vaut une réception conforme et complète, comme en V4.5.

## Migration

Elle est additive et automatique au démarrage : 6 colonnes sont ajoutées à `transfers` et rien n'est supprimé. Faites une sauvegarde avant la mise à jour : `python SAUVEGARDE_LOCALE.py` et une copie de `data/uploads`.

## Tests réellement exécutés

- Les 14 cas nouveaux de `tests/test_lot2_fiabilite.py`, lancés d'abord sur la V4.5 : **12 échecs** pour les raisons attendues (écritures partielles conservées, signatures exposées, aucun contrôle d'écart, poids inchangé, réception en double). Les 2 cas restants passaient déjà : la règle de levée d'un blocage d'incident ouvert et la compatibilité de réception sans corps.
- Après correction : **42/42 tests réussis** (Python 3.13).
- Essai dans Chromium headless avec deux comptes Maritime distincts :
  - le magasinier réceptionne 3 colis sur 4, avec l'état « manquant » ;
  - l'exploitation retient la quantité constatée ;
  - résultat : unité à 3 colis et 300 kg, toujours bloquée ; aucune erreur JavaScript.
- **Non testé :** Safari iPhone/iPad, imprimantes, plusieurs postes réels.

## Restant à traiter

- **Refus de réception d'un transfert :** retour de la marchandise à l'entrepôt de départ. La règle est à définir avec TAF.
- **Transferts partiels :** une partie d'une palette seulement.
- **Unité « disponible sans emplacement » après transfert :** il faudrait un statut « en attente de rangement ».
- **Requêtes SQL à rendre compatibles PostgreSQL :** chaînes entre guillemets doubles.
