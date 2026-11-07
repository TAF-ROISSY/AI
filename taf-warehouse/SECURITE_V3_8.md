# Sécurité V3.8 — pilote local uniquement

- Verrouillage persistant de compte pendant 15 minutes après 5 échecs.
- Limitation supplémentaire par IP locale, journalisation des échecs sans mots de passe.
- Politique de mots de passe renforcée lors des créations, modifications et réinitialisations.
- Révocation des sessions lors du changement de mot de passe, nettoyage des sessions expirées.
- En-têtes HTTP de protection, accès métier par rôle et entrepôt conservés.
- Démarrage refusé si TAF_ENV=production, pour éviter d'exposer par erreur une architecture locale non homologuée.

**Non implémenté :** MFA, authentification fédérée, protection contre les attaques distribuées, chiffrement des données au repos, stockage S3, PostgreSQL, sauvegardes distantes, audit de sécurité externe. Ne pas exposer sur Internet.
