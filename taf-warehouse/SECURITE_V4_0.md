# TAF WAREHOUSE V4.0 — Sécurité locale, phase 1

- Les nouvelles clés TOTP sont chiffrées avec Fernet (AES-128-CBC + HMAC-SHA256) avant stockage SQLite.
- Définir `TAF_MFA_ENCRYPTION_KEY` dans l'environnement du serveur (clé Fernet générée avec `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`). **Ne pas régénérer à chaque démarrage** et ne jamais ajouter la clé à Git.
- Pour les comptes MFA V3.9 déjà existants, faire une sauvegarde, arrêter le serveur et exécuter `python MIGRER_SECRETS_MFA.py` avec la clé définie. Une clé incorrecte rendra les comptes MFA chiffrés inaccessibles.
- À la confirmation MFA, 10 codes de secours à usage unique sont remis une seule fois. Les conserver hors ligne, séparément du mot de passe. Leur empreinte SHA-256 est stockée dans la base; ils sont consommés atomiquement.
- L'écran de connexion propose un champ de code de secours. Ne pas renseigner simultanément un code TOTP et un code de secours.
- Cette version reste **TEST LOCAL UNIQUEMENT**. Pas d'AWS, pas de Secrets Manager, pas d'antivirus fichiers, pas d'audit externe, pas d'homologation ni de garantie de conformité.
- Les anciennes clés MFA restent lisibles jusqu'à migration. Les anciens comptes MFA devront régénérer leurs codes de secours (désactivation/réenrôlement sécurisé à développer).
- Si un compte a perdu Authenticator ET ses codes de secours, la récupération doit être traitée par une procédure d'identification hors bande validée par le Super Admin; aucun contournement automatique n'est fourni.
