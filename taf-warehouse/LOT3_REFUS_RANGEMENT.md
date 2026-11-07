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
- **Après un refus validé,** l'exploitation choisit la suite (voir le lot 4 ci-dessous).
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

---

# V4.8 — Lot 4 : décision de l'exploitation après refus (option C) et nouveau rapport PDF

## Décision après refus validé

Règle TAF : l'exploitation choisit, au cas par cas, entre le **retour** et l'**acceptation sous réserves**.

`POST /api/transfers/{id}/refusal-decision` `{decision, note}` est réservé à l'**exploitation** de l'entrepôt de départ ou d'arrivée, et n'est possible que si le transfert est « Refusé ». Une seule décision est possible par transfert ; une seconde est refusée (409).

| Décision | Effet |
|---|---|
| `return` | Le transfert d'origine passe à « Retourné ». Un **transfert retour** est créé de l'arrivée vers le départ, déjà validé par la décision, et ne peut pas être annulé. Il exige une **nouvelle signature du transporteur** à l'expédition, puis une réception normale à l'entrepôt de départ, qui laisse la marchandise « À ranger ». |
| `accept_with_reserves` | Le transfert passe à « Accepté sous réserves ». Les réserves sont conservées et la marchandise entre dans le stock de l'entrepôt d'arrivée, « À ranger ». |

Dans les deux cas, le blocage de refus **reste en place** jusqu'à une levée autorisée. L'exploitation des deux entrepôts est notifiée.

## Rapport de refus PDF : nouvelle présentation

Module `app/pdf_report.py`, charte réutilisable pour les autres documents :

- bandeau bleu marine TAF avec référence, date d'émission et badge de statut ;
- grille « Transfert concerné » ;
- encadrés « Motif du refus » (rouge) et « Avis du responsable » ;
- cartouches de validation (constaté par / validé par) ;
- photos en grille de deux colonnes avec légende (fichier, date, auteur) ;
- tableau des pièces jointes avec empreinte SHA-256 ;
- dates au format français et pagination « Page x / y ».

Le logo TAF n'a pas encore été fourni : le bandeau affiche le nom « TAF · TRANS AIR FREIGHT » en texte.

## Tests réellement exécutés

- Les 3 nouveaux tests (retour complet avec nouvelle signature puis réception au départ, acceptation sous réserves, décision refusée sans refus validé) étaient **en échec avant développement**.
- Après développement : **52/52 tests réussis**.
- Essai dans Chromium headless : refus, photo, validation par Axel, décision « retour » par l'exploitation Maritime. Le transfert retour apparaît avec le bouton « Expédier » et l'original passe à « Retourné ». Le PDF réel est téléchargé et vérifié visuellement. Aucune erreur JavaScript.
