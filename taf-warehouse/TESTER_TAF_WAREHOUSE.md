# TAF WAREHOUSE — Test intégré V2.2

## Démarrer
- Windows : double-cliquer `DEMARRAGE_WINDOWS.bat` (Python 3.11+ requis).
- Mac : lancer `DEMARRAGE_MAC.command` dans le Terminal (Python 3.11+ requis).
- Sinon : `python -m pip install -r requirements.txt` puis `python -m uvicorn app.server:app --host 127.0.0.1 --port 8765`.
- Ouvrir http://127.0.0.1:8765
- Identifiant initial : `admin`. Mot de passe : fichier `data/INITIAL_ADMIN_PASSWORD.txt` créé au premier lancement.

## Scénario de recette conseillé
1. Se connecter et examiner les quatre entrepôts.
2. Créer une réception et ses unités physiques.
3. Examiner les emplacements : les capacités doivent être vérifiées avant les mouvements vers racks.
4. Tester une mission, un inventaire et un transfert.
5. Créer un chauffeur, préparer une sortie, faire autoriser la sortie par l'exploitation.
6. Faire signer le transporteur dans l'écran tactile puis générer le PDF signé.
7. Ouvrir un incident puis un litige et joindre les justificatifs.
8. Vérifier l'historique d'audit et les rapports.

## Limitations
Application de TEST locale, pas de déploiement AWS ni de synchronisation cloud. Certaines procédures restent simplifiées : scanner caméra, contrôles réglementaires, notifications, sécurité production, gestion de la preuve et recette métier exhaustive. Ne pas utiliser pour du fret réel. Aucun envoi externe automatique.
