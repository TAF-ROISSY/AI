# TAF WAREHOUSE V3.9 — MFA TOTP (recette locale)

## Fonction ajoutée
- MFA TOTP à six chiffres (RFC 6238, SHA-1, pas de 30 secondes), compatible avec les applications Authenticator courantes.
- Activation volontaire par utilisateur via les endpoints authentifiés `/api/mfa/setup`, `/api/mfa/confirm`, `/api/mfa/status`.
- À la confirmation, toutes les sessions du compte sont révoquées.
- Lors de la connexion, un compte avec MFA actif doit fournir le champ `otp`.
- Codes à usage unique : les compteurs TOTP déjà consommés ne peuvent pas être rejoués.
- Les erreurs de MFA participent au verrouillage de compte.

## Activation pour la recette
1. Connectez-vous normalement sur le serveur local.
2. Ouvrez `/docs`, autorisez-vous avec votre jeton Bearer.
3. Appelez `POST /api/mfa/setup` et saisissez la clé dans votre application Authenticator.
4. Appelez `POST /api/mfa/confirm` avec le code affiché.
5. Reconnectez-vous depuis l'interface avec mot de passe et code temporaire.

## Limites de sécurité importantes
- La clé MFA est actuellement conservée en clair dans SQLite : **ne convient pas à la production**. Il faut chiffrer les secrets au repos avec une gestion de clés dédiée (par ex. AWS KMS).
- Pas de codes de récupération ni de procédure d'assistance administrateur formalisée. La perte de l'appareil Authenticator peut bloquer l'accès.
- L'activation est volontaire et non imposée à tous les comptes ; la politique MFA obligatoire doit être définie avant production.
- Le mode production reste explicitement bloqué ; aucun serveur AWS n'est déployé.
- Un code TOTP valide pour une fenêtre future peut être accepté par la tolérance d'horloge, puis empêcher un code antérieur : comportement attendu de la protection anti-rejeu.
