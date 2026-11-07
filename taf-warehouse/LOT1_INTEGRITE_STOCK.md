# TAF WAREHOUSE V4.5 — Lot 1 : intégrité du stock

Version de recette locale. Pas de déploiement AWS. Pas homologuée pour la production.

## Règles métier validées par TAF (7 novembre 2026)

1. Une unité est soit une **palette** (quantité = nombre de colis), soit un **colis** (quantité = 1).
2. Un blocage est levé par **l'exploitation** ou par un utilisateur **explicitement habilité par le Super Admin** (droit « lever les blocages », écran Utilisateurs). Le Super Admin n'a pas ce droit par défaut : il doit se l'accorder, et cette action est tracée.
3. Le demandeur d'une sortie **peut** aussi l'autoriser.

## Corrections

| Anomalie V4.4 | Correction |
|---|---|
| A. Une unité pouvait être créée deux fois (double appui, reprise réseau) | `POST /api/units` est protégé contre les doublons (`Idempotency-Key`) et s'exécute dans une seule transaction. L'interface envoie la clé automatiquement. |
| A. Aucun contrôle entre les unités et les colis reçus | Le total des colis enregistrés ne peut pas dépasser les colis reçus (409, avec une invitation à signaler un écart). Le calcul part des quantités initiales, donc les sorties ultérieures ne le faussent pas. |
| B. Unités non bloquées sur une réception en écart | Toute unité créée sur une réception en écart (attendu ≠ reçu, ou écart déclaré) est bloquée dès sa création. |
| C. Blocage = un seul champ texte, écrasé par le suivant | Nouvelle table `unit_holds` : les blocages se cumulent et chacun conserve sa nature, sa référence, son auteur, sa date, la personne qui l'a levé, la date et la justification. `units.hold` reste le résumé des blocages actifs, donc tous les contrôles existants continuent de s'appliquer. |
| D. Sorties sans contrôle de rôle | Demande : exploitation, responsable, admin. Remise signée : magasinier, chef d'équipe, responsable, admin. |
| E. Poids inchangé après une sortie partielle | Le poids restant est recalculé au prorata des colis restants et l'opération est tracée dans le journal. Le volume est conservé : c'est une estimation prudente. |
| Interface : poids et volume décimaux refusés (ex. 0,1 m³) | Les champs numériques des formulaires acceptent les décimales. |

## Nouvelles routes API

- `GET /api/units/{id}/holds` : historique des blocages d'une unité.
- `POST /api/holds/{id}/lift` `{reason}` : levée d'un blocage précis, avec justification obligatoire (3 caractères minimum).
- `POST /api/users/{id}/permissions` `{can_lift_holds}` : réservée au Super Admin.
- `POST /api/units/{id}/hold` : avec un motif, ajoute un blocage manuel. Avec un motif vide (comportement V4.4), lève le blocage seulement s'il est le seul actif ; sinon répond 409.

## Migration

Elle est additive et automatique au démarrage : nouvelles colonnes `units.unit_type` (par défaut `palette`) et `users.can_lift_holds` (par défaut 0), nouvelle table `unit_holds`. Chaque blocage texte existant est repris tel quel comme blocage de nature `legacy`. La reprise est rejouable sans créer de doublon, et aucune donnée n'est supprimée.

**Avant la mise à jour d'une base existante :** exécuter `python SAUVEGARDE_LOCALE.py` et copier `data/uploads`.

## Changements de comportement à connaître

- Un responsable (manager) ou un admin **ne lève plus** les blocages sans l'habilitation explicite.
- Un magasinier ne peut plus **demander** une sortie, et l'exploitation ne peut plus **effectuer** la remise signée.
- `tests/test_discrepancy_recount.py` a été adapté à ces règles. Le circuit écart, recomptage et validation qu'il vérifie est inchangé.

## Tests réellement exécutés

- Les 10 nouveaux tests (`tests/test_lot1_integrite_stock.py`) ont été lancés d'abord sur la V4.4 d'origine : **10 échecs**, pour les raisons attendues (unité dupliquée, dépassement accepté, absence de blocage, magasinier autorisé à demander une sortie, poids resté à 400 kg).
- Après correction : **28/28 tests réussis** (Python 3.13). Ce total comprend 1 test de reprise des anciens blocages ajouté ensuite.
- Essai dans Chromium headless : création d'une unité « colis » depuis l'interface, blocage automatique, liste des blocages, refus de levée sans habilitation, écran Utilisateurs. Aucune erreur JavaScript.
- **Non testé :** Safari iPhone/iPad, imprimantes, plusieurs postes réels.

## Restant à traiter (lots suivants)

- Transactions manquantes sur les réceptions, documents, incidents, litiges et missions.
- Signatures exclues des listes API.
- Écarts à l'arrivée des transferts.
- Poids après correction d'inventaire.
- Levée d'un blocage d'incident tant que l'incident est ouvert : règle à décider.
