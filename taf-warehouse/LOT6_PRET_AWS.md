# TAF WAREHOUSE V4.10 — Lot 6 : prêt pour AWS (sans déploiement)

Rien n'a été créé sur AWS. S3 et Secrets Manager sont **simulés localement** dans les tests (bibliothèque `moto`).

## Stockage des documents

| Variable | Rôle |
|---|---|
| `TAF_STORAGE=s3` | Active le stockage S3. Par défaut, `local` (`data/uploads`). |
| `TAF_S3_BUCKET` | Bucket privé dédié `taf-warehouse-...`. |
| `TAF_S3_PREFIX` | Préfixe des objets. Par défaut, `documents/`. |

- **Objets chiffrés (SSE-S3).** Le serveur n'écrit plus aucun fichier sur son disque.
- **Atomicité :** si l'enregistrement en base échoue, l'objet S3 est supprimé.
- **Téléchargement :** il passe toujours par l'API, qui contrôle les habilitations. Il n'y a ni lien public, ni URL S3 exposée. Chaque téléchargement est **tracé dans le journal d'audit** (`download`).
- **Rapport de refus :** les photos stockées sur S3 sont intégrées au PDF.
- **Type MIME :** il est déterminé par le contenu réel du fichier, et non par la déclaration du navigateur.

**Transfert de l'existant :** `TAF_STORAGE=s3 TAF_S3_BUCKET=... python -m app.migrate_files`
- l'empreinte SHA-256 de chaque fichier est vérifiée avant l'envoi, avec arrêt en cas d'altération ;
- chaque fichier est relu et revérifié après l'envoi ;
- l'outil peut être relancé sans risque ;
- les fichiers locaux sont conservés.

## Secrets

- `TAF_SECRETS_ARN` : secret JSON de l'application. Clés acceptées : `TAF_MFA_ENCRYPTION_KEY`, `TAF_ADMIN_PASSWORD`, `TAF_DATABASE_URL`.
- `TAF_DB_SECRET_ARN` : secret géré par RDS (`username`/`password`), avec `TAF_DB_HOST`, `TAF_DB_PORT` et `TAF_DB_NAME`. L'adresse de connexion est construite avec `sslmode=require`.
- Une variable déjà définie n'est jamais écrasée.
- En production, aucun fichier de mot de passe initial n'est écrit sur le disque.

## Mode production (`TAF_ENV=production`)

Le serveur **refuse de démarrer** tant qu'il manque l'un de ces éléments, et il indique lequel :
- PostgreSQL ;
- le stockage S3 ;
- la clé de chiffrement MFA ;
- la liste des rôles soumis à la double authentification.

En production, la documentation interactive de l'API (`/docs`, `/openapi.json`) est désactivée.

## Double authentification obligatoire

- `TAF_MFA_REQUIRED_ROLES` vaut par défaut en production `superadmin,admin,exploitation,manager`. Hors production, la liste est vide.
- **Sans double authentification active, un compte concerné ne peut qu'activer celle-ci.** Toutes les autres routes répondent 403.
- **Nouvel écran d'activation dans l'interface :** QR code, code de vérification, puis affichage unique des 10 codes de secours. Il est imposé aux rôles concernés et proposé aux autres (« 🔐 Activer la double authentification »).
- La déconnexion révoque maintenant aussi la session côté serveur.

## Tests réellement exécutés

- **SQLite :** 64 réussis. 2 tests sont ignorés volontairement car ils nécessitent PostgreSQL : le démarrage complet en production et la migration de base.
- **PostgreSQL 16 :** **66/66 réussis.**
- Les nouveaux tests couvrent : objets S3 chiffrés sans fichier local, audit des téléchargements, nettoyage S3 en cas d'échec, photo S3 intégrée au rapport PDF, migration des fichiers (rejouable, détection d'un fichier altéré), lecture des secrets, construction de l'adresse de base, refus d'une production incomplète, démarrage en production complète sans `/docs`, double authentification obligatoire de bout en bout.
- Un test ancien (`test_production_fail_closed`) a été adapté au nouveau message de refus. Le comportement est inchangé : la production refuse de démarrer tant qu'elle est incomplète.
- **Essai dans Chromium :**
  - écran imposé au Super Admin ;
  - QR code affiché ;
  - code validé ;
  - 10 codes de secours ;
  - reconnexion avec un code de secours ;
  - aucune erreur JavaScript.
- **Non testé :** une application d'authentification sur un vrai téléphone, et un vrai bucket S3.
