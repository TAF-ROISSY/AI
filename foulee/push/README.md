# Foulée — serveur de notifications (gratuit)

Ce petit serveur envoie des **notifications** sur les iPhone de la famille, même quand l'appli est fermée :

- « Lucas part courir » (avec l'heure d'arrivée estimée) ;
- « Lucas a terminé » ;
- « ⚠ Alerte : Lucas » (immobile et sans réponse) ;
- « Lucas est arrivé à la maison » ;
- « Lucas s'éloigne » (plus loin que la distance choisie) ;
- « Lucas a quitté son parcours » ;
- pour toi, chaque soir à 19 h : « Demain : sortie longue — meilleur créneau 7 h – 9 h (12 °C, sec) », et le jeudi le meilleur jour pour la sortie longue du week-end (Foulée › Plus › Le bon créneau).

Il tourne sur **Cloudflare Workers**, en offre gratuite, sans carte bancaire. Toutes les minutes, il lit les liens de suivi des proches, et il ne garde que les abonnements et le dernier état de chaque personne.

## Installer (une fois, 10 minutes, sur ordinateur)

1. **Compte** : crée un compte gratuit sur dash.cloudflare.com.
2. **Stockage** : *Storage & Databases › KV › Create* → nom `FOULEE`.
3. **Worker** : *Workers & Pages › Create › Create Worker* → nom `foulee-push` → *Deploy*, puis *Edit code*. Remplace tout le code par le contenu de `worker.js` (ce dossier), puis *Deploy*.
4. **Réglages du Worker** (*Settings*) :
   - *Bindings › Add › KV namespace* : nom de variable `FOULEE`, espace `FOULEE`.
   - *Variables and Secrets* :
     - `SITE` (texte) : l'adresse de ta Foulée, affichée dans Foulée › Plus › Mes proches en direct › Notifications. Elle se termine par `/foulee/`.
     - `GITHUB_TOKEN` (secret) : sur github.com › Settings › Developer settings › *Fine-grained tokens* › *Generate*, avec **aucune permission** et une expiration d'un an. Sans ce jeton, GitHub limite les lectures à 60 par heure, ce qui ne suffit pas.
     - `SUBJECT` (texte, facultatif) : `mailto:` suivi de ton adresse e-mail.
   - *Triggers › Cron Triggers › Add* : `* * * * *` (toutes les minutes).
5. **Copie l'adresse** du Worker (`https://foulee-push.<toi>.workers.dev`) et colle-la dans Foulée › Plus › Mes proches en direct › Notifications.

## Activer les notifications sur un iPhone

Les notifications web ne marchent que pour une appli **ajoutée à l'écran d'accueil** (iOS 16.4 ou plus récent).

- **Ta femme** : ouvre le lien Foulée Suivi que tu lui envoies (il contient déjà l'adresse du serveur), puis Partager › *Sur l'écran d'accueil*. Elle ouvre l'appli depuis l'icône, touche 🔔 › *Activer les notifications*, puis accepte.
- **Toi** : Foulée › Plus › Mes proches en direct › Notifications › *Recevoir les notifications sur cet iPhone*.
- Le bouton *Envoyer une notification de test* vérifie que tout marche.
- Les zones (maison, distance maximale) se règlent par personne dans Foulée Suivi : ⚙︎ sur la fiche de la personne.

## Vérifier

- L'adresse du Worker affiche `{"app":"Foulée push","ok":true}`.
- `…/run` lance une vérification tout de suite et affiche le nombre d'abonnements, de personnes suivies, de messages envoyés et de notifications de créneau.
- Tests locaux (Node 20 ou plus) : `cp worker.js worker.mjs && node test_worker.mjs && node test_cheer.mjs && node test_slot.mjs`.

## Agenda (.ics)

Les agendas iCloud, Google ou Outlook ne se lisent pas directement depuis une page web. Le serveur sert de relais (`/ics?u=…`) pour Foulée › Plus › Ton agenda décide : il récupère le fichier, vérifie que c’est bien un agenda, et le renvoie sans rien garder.

## Limites

- Comptes gratuits : Cloudflare autorise 100 000 requêtes par jour, 100 000 lectures et 1 000 écritures dans le stockage. Le serveur n'écrit que quand un état change, ce qui laisse une large marge pour une famille.
- Une notification arrive en 1 à 2 minutes : c'est le délai de publication de la position, plus la vérification toutes les minutes.
- iOS peut regrouper ou retarder les notifications en mode Concentration : autorise « Foulée Suivi » dans le mode Concentration si besoin.
