# TAF WAREHOUSE — V4.26 (recette)

> **V4.26 :** l’e-mail de la fiche validée contient un lien vers le dossier et un lien par document (connexion requise ; `TAF_PUBLIC_URL`).

> **V4.25 :** fiche d’entrée « en attente de complément » tant que dimensions, document de transport et LTA manquent ; dossier de l’entrée modifiable (chaque changement avant → après dans l’historique) ; historique inaltérable (déclencheurs en base : ni modification ni suppression) ; validation définitive → e-mail au service et impression automatique du récapitulatif à agrafer ; étiquettes de traçabilité depuis le dossier ; réouverture motivée par l’exploitation. Impression sans boîte de dialogue : poste Chrome lancé avec `--kiosk-printing`.

> **V4.24 :** nouvelle charte (polices Inter et Space Grotesk intégrées, `web/vendor/fonts`, licence OFL) ; accueil « Aujourd’hui » (attention, chiffres clés, parcours de la marchandise, dernières entrées, magasin en direct) ; poste magasin sur téléphone (« Mon poste », prise en charge, mission pas à pas : aller à l’emplacement, scanner chaque unité, terminer) ; plan des zones cliquable avec contenu et charge.

> **V4.23 :** générateur de zones de stockage (racks AFR-G-2-05, sol AFR-SOL-A-03, étagères AFR-ET1-2-03, coffre AFR-COFFRE) avec panneaux QR à imprimer ; numéro d'entrée unique E-000001 ; « Demander au magasin » depuis l'entrée (préparation ou tâche libre) ; prise en charge par le magasinier (en attente → en cours → terminée) avec alerte sonore sur les postes ; récapitulatif de mission PDF ; historique complet de chaque entrée (écran et fiche PDF). `TAF_DEMO_RACKS=0` : pas de racks de démonstration sur une nouvelle base.

> **V4.22 :** notice transporteur (FR/EN) sur le contrôle d'identité, effacement automatique des pièces d'identité 1 an après le dernier passage, fiche de réception PDF envoyée par e-mail aux destinataires de chaque entrepôt (écran « E-mails des fiches »). Réglages : `TAF_MAIL_BACKEND=ses`, `TAF_MAIL_FROM`, `TAF_MAIL_DEFAULT_TO`, `TAF_MAIL_DELAY_SECONDS` (180), `TAF_IDENTITY_RETENTION_DAYS` (365), `TAF_PRIVACY_CONTACT`.
>
> **État complet, points à valider et limites : `ETAT_V4_21.md`.** V4.21 : bon de transfert, bon de remise unitaire et rapports d'incident, de litige et de mission au style TAF.

> **V4.20 (recherche, chronologie, scanner iPhone, plan des racks)** :
> - **Recherche universelle** en haut de chaque page : unités, réceptions (LTA, dossier, CMR, expéditeur), sorties, transferts, emplacements, clients, chauffeurs, incidents et litiges, limitée aux entrepôts autorisés.
> - **Chronologie complète d'une unité :** réception, étiquettes, rangements, blocages et levées, comptages, demande, préparation, autorisation, sortie avec chauffeur et immatriculation, transferts, incidents.
> - **Scanner QR :** lecture native (Chrome, Android) ou décodeur jsQR intégré (Safari iPhone et iPad, Apache 2.0, voir `web/vendor/`). La lecture ouvre la chronologie de l'unité.
> - **Plan des racks** par entrepôt : niveaux C, B, A, avec l'état de chaque emplacement (libre, occupé, réservé, bloqué, fermé, capacité non validée), l'occupation et la charge.
> - **Correctif :** l'écran « Écarts de réception » appelait une adresse inexistante depuis la V3.4 et restait vide.

> **V4.19 (missions et tableau de bord)** :
> - **Missions :** 8 types, affectation à un collaborateur habilité, priorité, échéance et consignes. Cycle à affecter → affectée → en cours → suspendue → terminée, ou annulée. Motif obligatoire pour suspendre, terminer ou annuler. Historique des événements, retards signalés, réaffectation.
> - **Tableau de bord opérationnel** (`/api/dashboard/ops`, filtrable par entrepôt) : 17 indicateurs réels, une liste « À traiter » (marchandise à ranger depuis plus de 24 h, sorties en attente depuis plus de 48 h, transferts en transit depuis plus de 72 h, incidents sans responsable, écarts, missions en retard ou à affecter), la charge par collaborateur et l'activité du jour.

> **V4.18 (campagnes d'inventaire)** :
> - **Création :** le responsable crée une campagne par emplacement, par rack ou sur l'entrepôt entier, et l'affecte à un collaborateur habilité. Le périmètre est figé à la création, et une unité ne peut appartenir qu'à une seule campagne ouverte.
> - **Comptage :** le compteur affecté saisit le comptage de chaque unité. Un comptage **conforme** est enregistré et validé, sans mouvement de stock. Un **écart** crée un comptage en attente, qui suit le circuit recomptage indépendant puis validation par une troisième personne, et une notification est envoyée. Le stock ne change qu'après cette validation.
> - **Clôture :** impossible tant qu'il reste une unité non comptée ou un écart non traité. Rapport PDF au style TAF (écarts surlignés, décisions).

> **V4.17** :
> - **Réception :** le nombre de palettes ou de colis crée autant de lignes de colisage, numérotées N/total. Ce nombre est prérempli avec les colis constatés, et les dimensions de la première ligne peuvent être recopiées sur toutes.
> - **Chauffeurs :** type et numéro de pièce d'identité, avec photo prise par l'appareil photo de l'iPhone. Cette donnée personnelle n'est visible que par l'exploitation, les responsables et les administrateurs ; le magasin peut la déposer.
> - **Recherche des mouvements** (`GET /api/movements/search`) : filtres dates, entrepôt, type, chauffeur, client, utilisateur et texte libre (LTA, unité, plaque, nom), pagination, export CSV pour Excel. Chaque recherche est tracée dans le journal d'audit.

> **V4.16** : décision TAF du 8/11/2026 : connexion prénom ou e-mail + code PIN pour tous (`TAF_PIN_ROLES`), double authentification désactivée (`TAF_MFA_ENABLED=0`, réactivable). Chacun peut passer son compte au code PIN.

> **V4.15** : connexion des magasiniers et chefs d'équipe par **prénom + code PIN à 6 chiffres** (codes trop simples refusés, verrouillage après 5 erreurs, attribution et réinitialisation par le Super Admin, changement par l'utilisateur). Les comptes de bureau gardent mot de passe et double authentification ; le code de double authentification n'est demandé qu'aux comptes qui l'ont activé. Identifiants insensibles à la casse (4.14.1).

> **V4.14** : nouvelle page de connexion ; gestion complète des utilisateurs par le Super Admin (création multi-entrepôts, modification du rôle et des entrepôts, suppression par archivage qui conserve l'historique d'audit).

> **V4.13 (lot 9, ordres de sortie multi-unités)** : voir `LOT9_ORDRES_SORTIE.md`.

> **V4.12 (lot 8, réception complète et étiquettes)** : voir `LOT8_RECEPTION.md`. Recette en ligne : voir `DEPLOIEMENT_AWS.md`.

> **V4.11 (lot 7, image Docker, infrastructure AWS, portail)** : voir `DEPLOIEMENT_AWS.md`. Rien n'est déployé.

> **V4.10 (lot 6, prêt pour AWS : S3, secrets, production, double authentification)** : voir `LOT6_PRET_AWS.md`.

> **V4.9 (lot 5, PostgreSQL)** : voir `LOT5_POSTGRESQL.md`.

> **V4.8 (lot 4, décision après refus et rapport PDF)** : voir la fin de `LOT3_REFUS_RANGEMENT.md`.

> **V4.7 (lot 3, refus de transfert et attente de rangement)** : voir `LOT3_REFUS_RANGEMENT.md`.

> **V4.6 (lot 2, fiabilité)** : voir `LOT2_FIABILITE.md`.

> **V4.5 (lot 1, intégrité du stock)** : voir `LOT1_INTEGRITE_STOCK.md`. Version de recette locale, non homologuée pour la production.

Application de test locale avec **API FastAPI, base SQLite persistante, interface web, étiquettes QR PDF, rapports PDF, rôles, journal d'audit et contrôles transactionnels**.

## Installation

Python 3.11+ :

```bash
cd taf-warehouse-fullstack
./start.sh
```

Sur Windows : `py -m pip install -r requirements.txt` puis `py -m uvicorn app.server:app --host 127.0.0.1 --port 8765`.

Ouvrir **http://127.0.0.1:8765**. Identifiant `admin`. Mot de passe initial généré automatiquement dans `data/INITIAL_ADMIN_PASSWORD.txt` (ou définir la variable d'environnement `TAF_ADMIN_PASSWORD` **avant** le premier lancement). Changer immédiatement le mot de passe dans le module Utilisateurs.

## Fonctionnement et limitations

- Données persistantes : `data/warehouse.sqlite3`. Sauvegarder à froid le dossier `data` pour conserver documents et base.
- Gestion des utilisateurs : seul Super Admin crée des comptes. Les comptes sont habilités par entrepôt.
- Les emplacements sont **non vérifiés par défaut**. Aucun mouvement vers un rack sans validation technique documentée, capacité de charge et volume utiles.
- Réceptions, unités, stocks, mouvements transactionnels, transferts en transit, inventaires avec validation indépendante, sorties avec autorisation exploitation et attestation chauffeur, missions/tâches, incidents et litiges, fichiers privés et PDF sont implémentés.
- **Limites importantes :** ce n'est PAS une version de production ni une validation réglementaire. Scanner caméra QR, signature manuscrite vérifiée, contrôle antivirus, workflow de levée des blocages douaniers/sûreté, autorisations de transfert selon régime douanier, gestion physique des capacités par niveau/rack, réserves juridiquement opposables, notifications automatiques, stockage AWS, chiffrement au repos, reprise multi-instance, durcissement HTTP/HTTPS, rétention RGPD et tests métier exhaustifs restent à réaliser.
- Ne pas exposer le serveur directement sur Internet. L'API et les mots de passe sont prévus pour un test **sur une machine locale** uniquement.
- Aucun email externe automatique. Aucune modification TAF OPS/AWS.

## Tests

`python -m pytest -q`

## API

Documentation interactive à `http://127.0.0.1:8765/docs`.

## V2.1 — Signature manuscrite du transporteur

Dans **Sorties**, après autorisation exploitation, cliquez sur **Faire signer le chauffeur**. Sélectionnez le chauffeur enregistré, renseignez le nom du signataire, faites signer sur la zone tactile (souris, doigt ou stylet), cochez la confirmation de remise physique, puis validez. La sortie ne peut pas être clôturée sans une signature PNG valide. Une fois terminée, **Bon signé PDF** produit un justificatif contenant le nom, l'immatriculation si renseignée, l'horodatage UTC, la quantité et la signature.

Le champ `signature_data` existait déjà mais acceptait du texte libre : il exige maintenant une image PNG encodée en base64 et `signature_consent=true`. Les anciennes intégrations doivent être adaptées. Ce mécanisme constitue une **signature électronique simple**, sans vérification d'identité forte, certification qualifiée ni garantie juridique d'opposabilité. Utilisation TEST uniquement jusqu'à recette métier, politique de conservation et sécurité validées.

## V2.3 — améliorations intégrées
- Lecture QR par caméra via BarcodeDetector si pris en charge par le navigateur, sinon saisie manuelle.
- Notifications internes persistantes pour incidents, litiges, autorisations et remises de sorties, avec lecture par utilisateur et filtrage par entrepôt.
- Tests automatiques des notifications et des restrictions d'accès.
- Caméra sur mobile : HTTPS ou localhost requis. Aucun accès direct à la caméra depuis une page distante non sécurisée.
- Pas d'envoi d'emails externes ni de déploiement AWS.

## V3.0 TEST — règles de transfert renforcées
- Transfert : demande → validation par un autre compte habilité → confirmation de départ physique avec note → réception par un autre compte que celui du départ.
- Blocage des mouvements, inventaires et sorties contradictoires sur une unité engagée dans un transfert.
- Les unités entièrement sorties passent au statut `exited`.
- Les nouvelles bases de test créent deux racks A/B/C et huit positions par niveau dans chacun des quatre entrepôts. Les capacités restent NON vérifiées par défaut.
- Les installations existantes bénéficient d'une migration additive des colonnes de transfert ; le nouveau plan de racks n'est créé que sur une nouvelle base.
- Test : `PYTHONPATH=. pytest -q` (3 scénarios automatisés).

Attention : la V3.0 reste une version de recette locale, non déployée AWS, non certifiée production. Le processus de transfert n'intègre pas encore une signature transporteur spécifique au transfert, ni des justificatifs immuables ou une preuve de livraison juridiquement qualifiée.

### V3.1 — annulations sécurisées (recette)
- Annulation d'une sortie demandée/autorisée avec libération de la quantité réservée, audit et notification. Une sortie signée ne peut pas être annulée.
- Annulation d'un transfert uniquement avant expédition physique, audit et notification. Un transfert en transit ne peut pas être annulé par cette route.
- Inventaire approuvé à quantité zéro : statut `depleted`, empêchant une unité vide d'être traitée comme disponible.
- Nouveaux boutons Annuler dans les écrans Sorties et Transferts.
- Tests de non-régression supplémentaires.

ATTENTION : V3.1 reste une version de recette locale, pas un système AWS de production. Les signatures des transferts, les habilitations détaillées, la sécurité et les tests matériels restent à finaliser.

## V3.2 — signature lors des transferts
- L'expédition d'un transfert approuvé nécessite un chauffeur enregistré, une signature tactile PNG et la confirmation de remise physique.
- La signature, le nom du signataire et la date UTC sont conservés dans le transfert.
- Le bon de transfert signé est téléchargeable en PDF depuis la liste des transferts.
- Les installations de test V3.1 sont migrées automatiquement par ajout de colonnes.
- Les preuves de signature sont des signatures électroniques simples ; le niveau probatoire et la politique de conservation restent à valider avant production.

## V3.3 — Écarts de réception et recomptage indépendant (recette)

- `POST /api/receipts/{id}/discrepancy` : signalement d'écart (manquant, excédent, avarie, document, autre), blocage conservatoire des unités déjà enregistrées et notification.
- `GET /api/receipt-discrepancies` : consultation par entrepôt habilité.
- `POST /api/receipt-discrepancies/{id}/review` : décision par une personne différente de celle qui a déclaré l'écart. **La décision ne lève pas automatiquement le blocage.**
- `POST /api/counts/{id}/recount` : deuxième comptage indépendant, une seule saisie par cycle.
- `GET /api/recounts` : historique des recomptages par entrepôt.
- Correction d'inventaire avec écart : premier comptage, deuxième comptage identique par un autre utilisateur, puis validation par un troisième utilisateur habilité. En cas de divergence, rejeter et recommencer le cycle.

Ces fonctionnalités sont disponibles par l'API interactive `/docs`. Les écrans dédiés à ces nouveaux circuits restent à intégrer. **Pas de déploiement AWS, pas de conformité production revendiquée.**

### V3.4 — Interfaces de recette
- Écran « Écarts de réception » : déclaration, consultation et décision indépendante.
- Réceptions : bouton de signalement d'écart.
- Inventaires : recomptage indépendant et historique des recomptages directement dans l'interface.
- Les contrôles côté serveur introduits en V3.3 restent obligatoires.
- Environnement de recette uniquement : ne pas utiliser pour du fret réel.

## V3.5 — Quatre modules renforcés (recette)
- Missions : priorité, échéance, consignes, affectation à un utilisateur habilité, démarrage, suivi et clôture.
- Litiges : actions tracées, demande de preuves, vérification d'au moins une pièce, décision motivée et clôture contrôlée.
- Racks : limites par unité, nombre maximal d'unités et catégories autorisées/interdites, après validation technique de l'emplacement.
- Utilisateurs : désactivation/réactivation et réinitialisation du mot de passe réservées au Super Admin, avec invalidation des sessions.
- API et boutons accessibles dans les écrans concernés ; 6 tests automatisés (dont 1 nouveau scénario multi-modules).

**Limites :** version locale de recette uniquement. Les capacités des racks sont des données à renseigner depuis les justificatifs réels ; aucune valeur fictive n'est certifiée. Le contrôle d'incompatibilité repose sur les catégories déclarées et ne remplace pas une étude HSE. Les workflows nécessitent encore une validation terrain, et la sécurité de production / AWS restent hors périmètre de cette version.

## V3.6 — sécurité et recette (7 novembre 2026)
- En-têtes HTTP de protection, désactivation de cache des réponses API, CSP restrictive pour le pilote local.
- Limitation des échecs de connexion (10 tentatives/5 minutes/par adresse IP, mémoire du processus uniquement).
- Déconnexion révoquant effectivement le jeton de session ; diagnostic authentifié `/api/health`.
- Test automatisé du cycle connexion, limitation, diagnostic et déconnexion.
- `python SAUVEGARDE_LOCALE.py` : copie cohérente SQLite avec vérification d'intégrité et somme SHA-256. **Les fichiers du dossier `data/uploads` doivent aussi être sauvegardés**.
- **Non prêt production** : MFA/SSO, reverse proxy TLS, stockage centralisé, sauvegardes distantes automatisées, supervision, tests matériel iOS/Android, tests charge, audit externe, procédures métier TAF restent à faire. La limitation de débit mémoire n'est pas adaptée à plusieurs processus/serveurs.

## V3.7 — isolation du journal et concurrence
- Les événements du journal d'audit sont filtrés par entrepôt pour les responsables non Super Admin. Les événements de sécurité globaux restent visibles au seul Super Admin.
- L'enregistrement d'un transporteur exige un nom non vide.
- Tests de non-régression : séparation Afrique/Maritime, droits d'accès au journal, six réservations simultanées d'une unité unique.
- **Limites :** ce test de concurrence couvre le serveur SQLite local, pas un déploiement distribué. La recette sur appareils et AWS restent à réaliser.

## V3.9 — Authentification multifacteur TOTP
Le code MFA et ses tests sont ajoutés. Voir `SECURITE_V3_9.md` pour l'activation et les limites. **Toujours en recette locale, pas homologué pour la production.**
