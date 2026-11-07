# TAF WAREHOUSE — TEST V4.11

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
