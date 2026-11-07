# TAF WAREHOUSE V4.7 — Lot 3 : refus de transfert et attente de rangement

Version de recette locale. Pas de déploiement AWS. Pas homologuée pour la production.

## Règles métier validées par TAF (7 novembre 2026)

1. **Refus à l'arrivée d'un transfert :**
   - le magasinier de l'entrepôt d'arrivée rédige un petit rapport et joint photo(s) et documents ;
   - le **responsable magasin** (Axel, rôle `manager`) le valide ;
   - le rapport est ensuite transmis à l'exploitation.
2. **En attente de rangement :** toute marchandise sans emplacement (nouvelle réception ou transfert reçu) est « À ranger ». Elle ne peut être ni sortie ni transférée tant qu'elle n'est pas rangée.

## Circuit de refus

| Étape | Qui | Effet |
|---|---|---|
| `POST /api/transfers/{id}/refuse` `{reason}` (10 caractères min.) | Magasinier, chef d'équipe, responsable ou admin de l'entrepôt d'arrivée, autre que l'expéditeur | Rapport `pending`, transfert « Refus à valider », blocage `refus_transfert`, notification à l'entrepôt d'arrivée |
| `POST /api/documents/transfer/{id}` | Utilisateurs des entrepôts de départ ou d'arrivée | Photos et documents (PDF, JPG, PNG, 10 Mo max.) |
| `POST /api/transfer-refusals/{id}/review` `{approve, note}` | Responsable magasin ou admin de l'arrivée, **autre que l'auteur du rapport** | **Validé** : au moins une photo est exigée ; un PDF « Rapport de refus » est généré (fiche, photos intégrées, empreintes SHA-256 des pièces) et rangé dans les documents du transfert ; le transfert passe à « Refusé » ; l'exploitation **des deux entrepôts** est notifiée. **Non validé** : retour « En transit », réception normale possible. |
| `GET /api/transfer-refusals` | Entrepôts concernés | Liste des rapports |

La transmission se fait par **notification interne**. Il n'y a aucun envoi d'email automatique, conformément aux règles du projet. Le blocage n'est jamais levé automatiquement, que le rapport soit validé ou non.

## Points d'attention

- **Racks non validés = rien ne peut sortir.** Avec la nouvelle règle, une marchandise doit être rangée avant toute sortie ou tout transfert. Or tous les emplacements sont créés « capacité non vérifiée ». **Avant la recette, il faut valider au minimum la zone temporaire de chaque entrepôt** (écran Emplacements : charge, volume, et la mention « plaque » ou « validation » avec la référence du contrôle). Sans cela, aucun rangement n'est possible.
- **Après un refus validé,** la marchandise reste en transit et bloquée, en attente d'une instruction de l'exploitation. Il n'existe pas encore de retour automatique vers l'entrepôt de départ : c'est à décider.
- **Bases existantes :** au démarrage, toute unité « disponible » sans emplacement passe automatiquement à « À ranger ». Faites une sauvegarde avant la mise à jour.

## Interface

- Unités : colonne Statut en français ; bouton « Ranger » pour les unités à ranger.
- Transferts :
  - « Refuser » pour un transfert en transit ;
  - « 📷 Photo / document » et « Valider le rapport (responsable) » pour un refus à valider ;
  - « Rapport de refus PDF » pour un transfert refusé.

## Tests réellement exécutés

- Les 7 nouveaux tests (`tests/test_lot3_refus_rangement.py`), lancés d'abord sur la V4.6 : **7 échecs**, puisque les fonctions n'existaient pas encore.
- Après correction : **49/49 tests réussis**. Huit anciens tests ont été adaptés : ils faisaient sortir ou transférer de la marchandise jamais rangée, ce que la nouvelle règle interdit. Ils sont donc complétés par une étape de rangement explicite, et deux vérifications de statut après transfert attendent désormais « À ranger ».
- Essai dans Chromium headless avec trois comptes (magasinier Maritime, Axel, exploitation) :
  - refus, ajout d'une photo et validation ;
  - transfert « Refusé », PDF de 2 pages téléchargé avec la photo intégrée ;
  - notification visible par l'exploitation ; aucune erreur JavaScript.
- **Non testé :** prise de photo par l'appareil photo d'un iPhone ou iPad réel.
