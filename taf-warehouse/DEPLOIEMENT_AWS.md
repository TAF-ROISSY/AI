# TAF WAREHOUSE — Déploiement AWS (lot 7)

## État au 7 novembre 2026 : recette en service

| | |
|---|---|
| Adresse | **https://yeclkv6p39.execute-api.eu-west-3.amazonaws.com** |
| Pile CloudFormation | `taf-warehouse-recette` (compte `857689333163`, Paris), protégée contre la suppression |
| Serveur | `i-01d11329cf79785bd` (administration par Session Manager uniquement) |
| Base | `taf-warehouse-recette` (RDS PostgreSQL 16.9, privée) |
| Documents | `taf-warehouse-recette-documents-857689333163` |
| Mot de passe initial du Super Admin `admin` | Console AWS → Secrets Manager → `taf-warehouse/recette/app` → *Récupérer la valeur du secret* → `TAF_ADMIN_PASSWORD` |
| Budgets | `taf-warehouse-recette` à 65 $/mois (étiquette `Application=taf-warehouse`). Budget de compte `taf` relevé de 5 $ à 52 $ (≈ 45 €) à la demande de TAF |

**Réglages de connexion décidés par TAF (8 novembre 2026)**, ajoutés à `/etc/taf-warehouse/app.env` sur le serveur de recette :
```
TAF_MFA_ENABLED=0
TAF_PIN_ROLES=superadmin,admin,manager,exploitation,leader,worker
```
- Connexion **prénom ou e-mail + code PIN à 6 chiffres** pour tous, sans double authentification.
- Protections maintenues : verrouillage 15 minutes après 5 erreurs, limite d'essais par appareil, codes trop simples refusés.
- **Pour réactiver la double authentification,** retirer ces deux lignes puis lancer `sudo taf-warehouse-deploy <version>`.
- Ces réglages ne figurent pas dans le modèle CloudFormation : ils sont à reporter lors de la création de la production.

**Historique :**
- **Première tentative en échec.** API Gateway refuse de réécrire `X-Forwarded-Proto` et `X-Forwarded-For`, qui sont des en-têtes réservés. La base, encore en création, a bloqué l'annulation automatique. Elle a été supprimée, vide et sans instantané, de même que le bucket vide et le secret créés par cette tentative.
- **Corrections :** la version 4.11.1 utilise l'en-tête `X-Taf-Client-Ip`. La seconde création a réussi.

**Mise en service de l'application :** l'image est construite **sur le serveur** à partir d'un commit GitHub précis (`deploy/build-on-server.sh`, lancé par Systems Manager). Aucun identifiant ECR ne transite par le poste de travail. La méthode ECR décrite plus bas reste possible depuis un poste administrateur.
```bash
sudo taf-warehouse-build <sha-commit-complet> <version>   # téléchargement, contrôle de version, construction, contrôle de santé
```

> **Rien n'est déployé.** Ce document et les fichiers `Dockerfile` et `infra/taf-warehouse.yaml` préparent une installation qui crée des **ressources payantes**. Aucune commande ci-dessous ne doit être lancée sans l'**accord écrit de TAF**.

## Principe validé (7 novembre 2026)

- **Même compte AWS que TAF OPS, installation entièrement séparée.** Toutes les ressources portent le nom `taf-warehouse-<environnement>-...` et les étiquettes `Application=taf-warehouse` et `Environment=recette|production`.
- **Aucune ressource TAF OPS n'est lue, référencée ni modifiée** : pile CloudFormation, Amplify, Cognito, DynamoDB, S3 et Lambda de TAF OPS restent hors périmètre.
- **Région Paris** (`eu-west-3`), comme TAF OPS.
- **Un portail statique séparé** (`portal/index.html`) oriente vers TAF OPS ou TAF WAREHOUSE. Chaque application garde sa propre connexion.

## Architecture (`infra/taf-warehouse.yaml`)

```
Internet ──HTTPS──► API Gateway  https://<id>.execute-api.eu-west-3.amazonaws.com
                    (adresse et certificat fournis par AWS, comme pour TAF OPS ; aucun nom de domaine à acheter)
                        │ lien privé (VPC Link), réseau interne AWS
                        ▼
                    EC2 (Amazon Linux 2023) — aucun port ouvert sur Internet
                        └─ conteneur TAF WAREHOUSE (utilisateur non privilégié)
                               ├──TLS──► RDS PostgreSQL 16 (sous-réseaux privés, sans accès Internet)
                               ├──────► S3 privé chiffré et versionné (documents, photos, PDF)
                               └──────► Secrets Manager (mot de passe initial, clé MFA, accès base)
CloudWatch : journaux 90 jours, alarmes serveur et base → e-mail · AWS Budgets : alerte à 80 % et prévision à 100 %
```

| Élément | Choix et raison |
|---|---|
| Réseau | VPC dédié `10.42.0.0/16`. La base est dans deux sous-réseaux privés, sans route Internet. Le pare-feu de la base n'accepte que le serveur applicatif. |
| Accès HTTPS | **API Gateway (HTTP API)** : adresse `execute-api` et certificat gérés par AWS, sans nom de domaine. Le lien privé (VPC Link + Cloud Map) mène au serveur. L'adresse IP réelle du client est transmise dans l'en-tête `X-Taf-Client-Ip`, que la passerelle réécrit toujours : elle ne peut donc pas être falsifiée. `X-Forwarded-For` et `X-Forwarded-Proto` sont réservés par API Gateway et ne peuvent pas être modifiés. Limitation à 50 requêtes/s (pointes à 100). Journal d'accès de 90 jours. Requêtes limitées à 10 Mo par AWS, d'où une limite de 9 Mo par fichier dans l'application. |
| Serveur | `t3.small` (modifiable). **Aucun port ouvert sur Internet** : seul le lien privé de la passerelle atteint l'application. Disque chiffré, IMDSv2 obligatoire. Pas de SSH : l'administration passe par AWS Systems Manager. Redémarrage automatique en cas de panne matérielle. |
| Base | RDS PostgreSQL 16.9, `db.t4g.micro`. Chiffrée, TLS imposé (`rds.force_ssl`). Mot de passe géré et renouvelé par RDS. Sauvegardes automatiques 14 jours avec restauration à un instant précis. Protection contre la suppression ; instantané conservé si la pile est supprimée. |
| Documents | Bucket S3 privé : accès public bloqué, chiffrement, versionnage, HTTPS obligatoire. Conservé même si la pile est supprimée. |
| Images | Dépôt ECR privé. Versions non modifiables, analyse de vulnérabilités à l'envoi, 15 dernières versions conservées. |
| Droits | Rôle du serveur limité au préfixe `documents/` du bucket, aux deux secrets, au dépôt ECR et au groupe de journaux. |

## Coûts — tarifs officiels AWS, région Paris (API de tarification, 7 novembre 2026)

Base : 730 heures par mois, prix **hors taxes**, en dollars, comme les facture AWS.

| Poste | Hypothèse | Prix unitaire | $/mois |
|---|---|---|---|
| Serveur EC2 `t3.small` (crédits CPU plafonnés) | permanent | 0,0236 $/h | 17,23 |
| Disque serveur gp3 | 20 Go | 0,0928 $/Go-mois | 1,86 |
| Adresse IPv4 publique (sortie du serveur) | 1 | 0,005 $/h | 3,65 |
| Base RDS PostgreSQL `db.t4g.micro` (une seule zone) | permanente | 0,018 $/h | 13,14 |
| Stockage base gp3 | 20 Go | 0,133 $/Go-mois | 2,66 |
| Sauvegardes base (14 jours) | inférieures à la taille de la base | gratuites jusqu'à 20 Go | 0,00 |
| API Gateway (HTTP API) | ≈ 2,5 millions de requêtes (20 utilisateurs actifs) | 1,17 $/million | 2,93 |
| Cloud Map | 1 ressource + jusqu'à 2,5 M d'appels | 0,10 $ + 1 $/million | 2,60 |
| Secrets Manager | 2 secrets | 0,40 $/secret | 0,80 |
| S3 documents | 10 Go | 0,024 $/Go-mois | 0,24 |
| Journaux CloudWatch | ≈ 1 Go ingéré | 0,5985 $/Go | 0,60 |
| Alarmes CloudWatch | 4 | 0,10 $/alarme | 0,40 |
| ECR (images) | ≈ 2 Go | 0,10 $/Go-mois | 0,20 |
| Transfert sortant, notifications e-mail | faible volume | inclus dans la gratuité AWS | 0,00 |
| **Total estimé, un environnement** | | | **≈ 46 $/mois (≈ 1,5 $/jour)** |

- **Budget TAF : 2 € par jour en moyenne (≈ 60 €/mois). Un environnement tient dans ce budget, deux non.** La recette devient donc la plateforme de démarrage. Au passage en production, l'environnement de production est créé, puis la recette est supprimée après bascule. Pendant quelques jours seulement, les deux environnements coexistent.
- **Postes variables :** requêtes API, journaux et stockage S3 suivent l'activité réelle. Les montants fixes (serveur, base, IP) représentent environ 38 $/mois.
- **Économie possible :** un serveur `t3.micro` (1 Go de mémoire) économiserait environ 8,60 $/mois. Ce choix est à valider après mesure de la mémoire en recette.
- **Alertes :** le budget AWS `taf-warehouse-recette` (65 $) prévient à 80 % de consommation réelle et à 100 % de la prévision. Le filtre par étiquette exige d'activer l'étiquette de répartition des coûts `Application`. Elle existe dans le compte mais est **inactive** au 7 novembre 2026.

## Procédure (recette d'abord, production ensuite)

### 0. Prérequis
- L'accord écrit de TAF, avec le budget validé.
- Une adresse e-mail pour les alertes. Aucun nom de domaine n'est nécessaire.
- Un poste avec AWS CLI v2 et Docker, connecté au compte avec un utilisateur nominatif (MFA).

### 1. Créer l'infrastructure
```bash
aws cloudformation deploy --region eu-west-3 \
  --stack-name taf-warehouse-recette \
  --template-file infra/taf-warehouse.yaml \
  --capabilities CAPABILITY_IAM \
  --tags Application=taf-warehouse Environment=recette \
  --parameter-overrides EnvironmentName=recette AlertEmail=<email> MonthlyBudgetUSD=65
aws cloudformation describe-stacks --region eu-west-3 --stack-name taf-warehouse-recette --query 'Stacks[0].Outputs'
```
- Confirmer l'abonnement SNS reçu par e-mail.
- Noter la sortie **`Url`** : c'est l'adresse de TAF WAREHOUSE, à mettre dans le portail.

### 2. Compléter le secret de l'application (une seule fois)
Le modèle génère `TAF_ADMIN_PASSWORD`. Il faut y ajouter la clé de chiffrement MFA, qui doit rester **stable et sauvegardée** :
```bash
ARN=<AppSecretArn>
KEY=$(python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
CUR=$(aws secretsmanager get-secret-value --region eu-west-3 --secret-id "$ARN" --query SecretString --output text)
NEW=$(python3 -c "import json,sys;d=json.loads(sys.argv[1]);d['TAF_MFA_ENCRYPTION_KEY']=sys.argv[2];print(json.dumps(d))" "$CUR" "$KEY")
aws secretsmanager put-secret-value --region eu-west-3 --secret-id "$ARN" --secret-string "$NEW"
unset KEY CUR NEW
```

### 3. Construire et publier l'image
```bash
VERSION=4.11.1; REPO=<RepositoryUri>
docker build -t "$REPO:$VERSION" .
aws ecr get-login-password --region eu-west-3 | docker login --username AWS --password-stdin "${REPO%%/*}"
docker push "$REPO:$VERSION"
```
Derrière un proxy d'entreprise, ajouter `--secret id=ca,src=<certificat.pem>` à `docker build`.

### 4. Démarrer l'application
Dans la console EC2, ouvrir le serveur `taf-warehouse-recette` puis **Se connecter → Session Manager** :
```bash
sudo taf-warehouse-deploy 4.11.1
```
Le script attend que l'application soit saine et s'arrête en erreur si ce n'est pas le cas. L'application est ensuite accessible à l'adresse `Url`.

### 5. Première connexion
- Le mot de passe du Super Admin se trouve dans le secret de l'application (console Secrets Manager).
- La **double authentification est imposée** dès la connexion. Activez-la, conservez les codes de secours, puis **changez le mot de passe**.

### 6. Reprise des données de la recette locale (facultatif)
Depuis le serveur, en Session Manager, **avant toute saisie en ligne** :
```bash
python -m app.migrate_pg warehouse.sqlite3   # base vide obligatoire ; contrôle lignes et SHA-256
python -m app.migrate_files                  # data/uploads vers S3 ; SHA-256 vérifié avant et après
```
Il faut copier la base et le dossier `uploads` sur le serveur, puis les lancer dans un conteneur de la même version, avec `--env-file /etc/taf-warehouse/app.env`.

## Mise à jour et retour arrière
- **Mise à jour :** `sudo taf-warehouse-deploy <nouvelle-version>`. La version en service est notée dans `/etc/taf-warehouse/current-version`.
- **Retour arrière :** `sudo taf-warehouse-deploy <version-précédente>`. Les versions sont non modifiables dans ECR.
- Les migrations de schéma sont **additives** : une version antérieure fonctionne sur une base migrée, puisque les colonnes ajoutées sont ignorées. Une évolution non additive devra fournir sa propre procédure de retour.

## Sauvegarde et restauration — à tester avant la production
1. **Base :** restauration à un instant précis.
   - Console RDS → `taf-warehouse-recette` → *Restaurer à un instant donné*, vers une **nouvelle** instance `taf-warehouse-restore-test`.
   - Lancer un conteneur de test pointant sur cette instance et vérifier les volumes de lignes et quelques dossiers.
   - **Supprimer ensuite l'instance de test**, qui est facturée.
2. **Documents :** le versionnage S3 permet de récupérer une version supprimée ou écrasée.
3. **Consigner** la date, la durée et le résultat du test dans le cahier de recette.

## Portail TAF
`portal/index.html` est une page statique autonome : aucune dépendance, politique de sécurité stricte, mode sombre, mobile.
- Générer la page avec les deux adresses : `python portal/configurer.py https://<adresse-taf-ops> https://<adresse-warehouse>`. Le script produit `portal/dist/index.html` et met à jour l'empreinte de sécurité (CSP).
- Hébergement recommandé : une **nouvelle application Amplify dédiée** (`taf-portail`), déployée par glisser-déposer. Cela n'ajoute ni ne modifie rien dans l'application Amplify de TAF OPS.

## Vérifications réalisées sans AWS

| Vérification | Résultat |
|---|---|
| Construction de l'image Docker (base `public.ecr.aws`, utilisateur 10001) | Réussie, 388 Mo |
| Conteneur en **mode production** avec PostgreSQL 16, et S3 + Secrets Manager simulés (serveur moto) | Démarrage sain ; secrets lus ; `/docs` en 404 ; double authentification imposée ; aucun fichier local |
| Proxy HTTPS devant le conteneur (essai local avec Caddy, remplacé sur AWS par API Gateway) | En-têtes de sécurité présents ; IP client transmise à l'application |
| `cfn-lint` sur le modèle (région `eu-west-3`) | 0 erreur, 0 avertissement |
| Portail (Chromium, ordinateur clair et mobile sombre) | Rendu correct, script autorisé par la CSP, aucune erreur |

**Non vérifié** : un déploiement CloudFormation réel, l'API Gateway et le lien privé réels (impossibles à simuler localement), ainsi que RDS, IAM et Budgets réels.

## Nom de domaine (facultatif, plus tard)
Une adresse plus lisible, par exemple `warehouse.<domaine-taf>`, pourra être ajoutée sans réinstallation : domaine personnalisé sur API Gateway, avec un certificat AWS gratuit. L'adresse `execute-api` restera valable.
