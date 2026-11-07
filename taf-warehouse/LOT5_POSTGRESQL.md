# TAF WAREHOUSE V4.9 — Lot 5 : PostgreSQL

Préparation de l'hébergement AWS validée par TAF le 7 novembre 2026 : même compte AWS que TAF OPS, mais **installation entièrement séparée** (serveur, base, stockage et utilisateurs propres, préfixe `taf-warehouse-`), avec un portail d'accueil vers les deux applications. **Aucune ressource ni aucun code de TAF OPS n'est modifié.**

Rien n'a encore été déployé sur AWS.

## Ce qui change

- **Le même code fonctionne sur deux moteurs :**
  - SQLite reste le moteur par défaut (poste local, démarrage Windows/Mac, tests) ;
  - PostgreSQL est activé par `TAF_DATABASE_URL=postgresql://utilisateur:motdepasse@hôte:5432/base`.
- **Concurrence identique :** sous PostgreSQL, chaque transaction d'écriture prend un verrou transactionnel unique (`pg_advisory_xact_lock`). C'est l'équivalent exact de `BEGIN IMMEDIATE` sous SQLite. Les protections contre la double réservation, la double sortie ou les opérations simultanées sont donc conservées telles quelles. À l'échelle de TAF (quatre entrepôts, quelques dizaines d'utilisateurs), ce choix privilégie la sûreté plutôt que le parallélisme.
- **SQL standard :** tous les littéraux entre guillemets doubles (`status="available"`), propres à SQLite, sont convertis en guillemets simples. `INSERT OR IGNORE` et `INSERT OR REPLACE` sont remplacés par `ON CONFLICT`.
- **Types adaptés sous PostgreSQL :** `REAL` devient `DOUBLE PRECISION`, pour éviter que 0,1 m³ soit arrondi ; `INTEGER` devient `BIGINT`, pour les horodatages.
- **Résultats numériques :** les agrégats PostgreSQL sont rendus en nombres JSON ordinaires.
- **Diagnostic :** `/api/health` indique le moteur utilisé (`engine`).

## Migration des données existantes : `python -m app.migrate_pg`

```bash
python SAUVEGARDE_LOCALE.py                       # 1. sauvegarde
TAF_DATABASE_URL=postgresql://... python -m app.migrate_pg data/warehouse.sqlite3
```

- Lit la base SQLite en **lecture seule**.
- Crée le schéma PostgreSQL et **refuse une cible non vide**.
- Copie toutes les tables en une seule transaction : tout ou rien.
- Contrôle ensuite, table par table, le **nombre de lignes et une empreinte SHA-256** du contenu.
- Les sessions ne sont pas copiées : tout le monde se reconnecte. Les mots de passe, la double authentification, les blocages, l'audit, les documents et les signatures sont conservés.
- Les fichiers de `data/uploads` (photos, PDF) **ne sont pas dans la base** : ils seront transférés vers S3 au lot suivant.

## Tests réellement exécutés

- **SQLite :** 55 réussis. 1 test ignoré volontairement : la migration, qui nécessite PostgreSQL.
- **PostgreSQL 16 :** **56/56 réussis**. Chaque test tourne dans un schéma neuf, supprimé ensuite. C'est toute la suite existante (V4.4 et lots 1 à 4), plus le lot 5 :
  - vérification du moteur actif ;
  - types des résultats ;
  - absence de SQL propre à SQLite ;
  - migration complète d'une base remplie, avec redémarrage de l'application sur PostgreSQL et données identiques.
- Les tests de concurrence (6 réservations simultanées d'une même unité, rejeu avec la même clé anti-doublon) passent aussi sous PostgreSQL.
- **Essai de l'outil en ligne de commande** sur la base issue de l'essai navigateur des lots 3 et 4 (7 utilisateurs, transferts, refus, documents, 27 lignes d'audit) : migration terminée, contrôles conformes.

Pour lancer la suite sur PostgreSQL :

```bash
TAF_TEST_DATABASE_URL=postgresql://... PYTHONPATH=. python -m pytest -q
```

## Limites

- Une connexion par requête. Un pool de connexions sera ajouté si la charge le justifie.
- Testé sur PostgreSQL 16 local, **pas encore sur une base AWS RDS**.
