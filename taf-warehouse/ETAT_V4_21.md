# TAF WAREHOUSE V4.21 — état au 8 novembre 2026

Recette en ligne : https://yeclkv6p39.execute-api.eu-west-3.amazonaws.com. Pile `taf-warehouse-recette`, Paris, séparée de TAF OPS.
Tests automatisés : **SQLite 124 réussis + 2 réservés à PostgreSQL ; PostgreSQL 16 : 126/126.**

## Classement des fonctions

« Fonctionnelle et testée » : tests automatisés et essai réel dans un navigateur (Chromium). Rien n'a encore été validé sur le terrain.

| Module | État | Lot |
|---|---|---|
| Connexion prénom ou e-mail + code PIN, verrouillage, gestion des utilisateurs par le Super Admin | Fonctionnelle et testée | 10, V4.14 à V4.16 |
| Réception complète : colisage par palette ou colis, N lignes générées, totaux, poids volumétrique, incohérences, sûreté | Fonctionnelle et testée | 8, V4.17 |
| Étiquettes 80 × 130 (client, LTA, N/total, QR) et historique d'impression | Fonctionnelle et testée, **imprimante réelle non testée** | 8 |
| Stock, statut « à ranger », blocages multiples et levée habilitée | Fonctionnelle et testée | 1, 3 |
| Plan des racks et capacités | Fonctionnelle et testée, **capacités réelles à saisir** | 12 |
| Ordres de sortie multi-unités : préparation, autorisation, remise partielle, refus de signature, bon de remise | Fonctionnelle et testée | 9 |
| Signature au doigt, à la souris ou au stylet | Fonctionnelle et testée à la souris, **iPhone et iPad réels non testés** | 2 |
| Transferts : signature, écarts, refus avec rapport, retour ou acceptation sous réserves | Fonctionnelle et testée | 2, 3, 4 |
| Inventaires par campagne, recomptage et validation indépendants, rapport | Fonctionnelle et testée | 10 |
| Missions (types, cycle, retards, charge) et tableau de bord opérationnel | Fonctionnelle et testée | 11 |
| Chauffeurs et photo de la pièce d'identité (accès réservé) | Fonctionnelle et testée, **durée de conservation à décider** | V4.17 |
| Recherche des mouvements (filtres, export CSV), recherche universelle, chronologie par unité | Fonctionnelle et testée | V4.17, 12 |
| Scanner QR : natif, et décodeur jsQR pour Safari | Testé sur caméra simulée, **iPhone réel non testé** | 12 |
| Incidents, litiges, documents, notifications internes | Fonctionnelle, couverture de tests partielle | V3.x |
| PDF au style TAF : remise, transfert, refus, inventaire, incident, litige, mission | Fonctionnels | 4, 9, 10, 13 |
| PostgreSQL, S3 privé, Secrets Manager, image Docker, infrastructure AWS | Déployés en recette | 5 à 7 |
| Double authentification | Développée et testée, **désactivée par décision TAF** (réactivable) | 6, V4.16 |

## Points à valider ou à décider

1. **Capacités des emplacements :** saisir la charge et le volume validés (écran Emplacements). Sans cela, aucun rangement en rack n'est possible.
2. ~~Durée de conservation des pièces d'identité~~ : décidée (1 an après le dernier passage), effacement automatique en V4.22.
3. **Essais sur iPhone et iPad réels :** signature, appareil photo, scanner QR. Essais sur l'imprimante thermique réelle.
4. **Test de restauration de la base** avant la production (procédure dans `DEPLOIEMENT_AWS.md`).
5. **Sécurité du compte :**
   - AWS est utilisé avec le compte « root », alors qu'un administrateur nominatif est recommandé ;
   - le dépôt GitHub `taf-roissy/AI` est public ;
   - la double authentification est désactivée.
6. **E-mails** : fiche de réception envoyée par Amazon SES (V4.22). Compte SES en mode « bac à sable » : seules les adresses vérifiées reçoivent. Demander l'accès production avant d'ajouter afrique@ / export@.
7. **Logo TAF** à fournir pour les PDF et l'écran de connexion.

## Limites connues
- Pas de mode hors connexion : une opération ne s'enregistre qu'avec le réseau.
- Un seul serveur, sans redondance. Le redémarrage automatique est assuré par AWS en cas de panne matérielle.
- La signature électronique est une signature simple, non qualifiée.
