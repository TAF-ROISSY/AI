# TAF WAREHOUSE V4.12 — Lot 8 : réception complète et étiquettes

## Réception
- **Nouveaux champs :** expéditeur, transporteur, référence transport (CMR…), référence dossier, nature de la marchandise.
- **État apparent :** conforme, endommagé ou à vérifier.
- **Statut sûreté :** sécurisé, à contrôler ou non sécurisé.
- **Colisage :** une ligne par palette ou par colis, avec longueur, largeur, hauteur (cm), poids (kg), nombre de colis et observations. La réception crée **automatiquement une unité par ligne**, numérotée **1/N, 2/N…**, avec ses dimensions, son volume et son poids. Les unités sont « À ranger ».
- **Totaux calculés par le serveur :** unités, colis, poids, volume et **poids volumétrique** (convention fret aérien IATA 1:6000, soit 166,67 kg/m³).
- **Incohérences détectées :**
  - colis décrits ≠ colis reçus ;
  - poids pesé ≠ poids déclaré (écart de plus de 5 %, avec un minimum de 1 kg) ;
  - colis reçus ≠ colis attendus.

  Dans ces cas, la réception passe **en écart**, toutes ses unités sont **bloquées** et l'exploitation est notifiée.
- **Blocages automatiques :**
  - sûreté « à contrôler » ou « non sécurisé » : blocage `surete` ;
  - état « endommagé » : blocage `avarie` ;
  - état « à vérifier » : blocage `controle`.

  Ces blocages se lèvent selon les règles du lot 1 (exploitation ou utilisateur habilité).
- **Protection anti-doublon :** un double envoi ne crée ni une deuxième réception ni des unités en double.
- **Compatibilité :** une réception sans colisage fonctionne comme avant, et les unités peuvent toujours être ajoutées une par une.
- **Interface :** un tableau de colisage permet d'ajouter ou de supprimer des lignes, avec totaux et alertes affichés pendant la saisie. Après l'enregistrement, l'interface propose d'**imprimer aussitôt les étiquettes**.

## Étiquettes 80 × 130 mm
- **Contenu :**
  - bandeau TAF ;
  - client et LTA ;
  - numéro **N/total** en grand, avec le type palette ou colis ;
  - QR code, qui ne contient que l'identifiant de l'unité ;
  - identifiant de l'unité, référence de réception, poids et nombre de colis, entrepôt, emplacement (« À RANGER » si aucun).
- **Historique des impressions** (`GET /api/labels/{id}/history`) : qui a imprimé, quand, première impression ou réimpression, lot d'impression groupée. Une réimpression ne crée jamais d'unité.

## Tests réellement exécutés
- **Avant développement :** les 11 nouveaux tests (`tests/test_lot8_reception.py`) donnaient 10 échecs. Le seul test qui passait vérifie la compatibilité des anciennes réceptions. Trois autres tests passaient d'abord « à vide », sans aucune unité à contrôler : je les ai renforcés pour exiger la présence des unités.
- **Après développement :**
  - SQLite : **77 réussis**, plus 2 réservés à PostgreSQL ;
  - PostgreSQL 16 : **79/79**.
  - L'outil de migration a refusé la nouvelle table `label_prints` tant qu'elle n'était pas déclarée : c'est sa protection prévue. Elle est maintenant déclarée.
- **Essai dans Chromium :** saisie de la réception sur un écran de téléphone, avec 2 palettes. Totaux affichés : 5 colis, 550 kg, 2,4 m³, poids volumétrique 400 kg. Unités créées « 1/2 » et « 2/2 », PDF de 2 étiquettes téléchargé et vérifié visuellement, aucune erreur JavaScript.
- **Défaut corrigé pendant l'essai :** sur mobile, le tableau de colisage élargissait toute la page. Désormais, seul le tableau défile.
- **Non testé :** impression sur l'imprimante thermique réelle de TAF.
