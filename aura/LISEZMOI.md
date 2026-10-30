# Aura — l'entretien complet du Mac

Application native SwiftUI pour macOS 14 Sonoma ou plus récent : sombre, animée, en français, avec 18 modules.

## Les modules

**Analyse intelligente** — Nettoyage, protection, vitesse et mises à jour en un clic. Score de santé et assistant de recommandations personnalisées.

**Déchets système** — Caches, journaux, navigateurs, Xcode, caches de développement, **déchets IA** (Ollama, LM Studio, Hugging Face, Whisper, Cursor…), Photos et montage, mises à jour iOS, pièces jointes Mail, sauvegardes iPhone, installeurs, vieux téléchargements, Corbeilles (Mac + supports externes).

**Protection**
- *Sécurité* : analyse rapide / équilibrée / approfondie des logiciels publicitaires et indésirables connus, lancements automatiques suspects (programmes cachés, dans /tmp, non signés), extensions de navigateur à risque, profils de configuration, tâches cron, signature des apps. État de SIP, Gatekeeper, FileVault, coupe-feu, XProtect et mises à jour, avec boutons « Corriger ».
- *Confidentialité* : historique, cookies, sessions et données de sites pour Safari, Chrome, Edge, Brave, Vivaldi, Arc, Firefox (favoris et mots de passe jamais touchés). Éléments récents, Terminal, Coup d'œil, Spotlight, caches de messageries, réseaux Wi-Fi mémorisés.
- *Autorisations des apps* : caméra, micro, écran, accessibilité, accès disque, clavier, contacts, photos… avec retrait en un clic.

**Performances**
- *Surveillance* : CPU global et par cœur, mémoire détaillée, swap, disque, réseau, batterie (cycles, santé), **températures** (CPU, GPU, SSD, batterie), processus gourmands avec bouton Quitter.
- *Maintenance* : libérer la RAM, cache DNS, scripts de maintenance, Launch Services, Spotlight, accélérer Mail, Coup d'œil, polices, instantanés Time Machine, autorisations du dossier personnel, vérification du disque, relance du Dock/Finder. Tâches recommandées automatiquement.
- *Démarrage et arrière-plan* : apps ouvertes à la connexion, agents et démons, activation/désactivation réversible.

**Applications**
- *Désinstalleur* : suppression complète ou **réinitialisation** (l'app reste, ses réglages repartent à zéro), apps inutilisées et lourdes, restes d'apps déjà supprimées.
- *Mises à jour* : apps des éditeurs (Sparkle), App Store, Homebrew (apps et outils), macOS.
- *Extensions* : navigateurs, Safari, extensions Finder/partage (activables), volets de réglages, Spotlight, Coup d'œil, modules Internet, économiseurs, pilotes audio.

**Fichiers**
- *Gros et vieux fichiers* : par taille, type et ancienneté.
- *Doublons* : plusieurs dossiers et supports à la fois, comparaison SHA-256, 5 règles de sélection automatique.
- *Images similaires* : comparaison visuelle (rafales, captures, versions redimensionnées), réglage de la ressemblance.
- *Carte de l'espace* : treemap cliquable du disque, d'un dossier ou d'un support.
- *Supports amovibles* : clés USB, disques externes, cartes SD — fichiers parasites (.DS_Store, « ._ », Thumbs.db, corbeille du support, index Spotlight), dot_clean, protection, éjection, blocage des .DS_Store.
- *Nettoyage du cloud* : iCloud Drive, Google Drive, OneDrive, Dropbox, Box — libère l'espace local sans rien supprimer en ligne.
- *Broyeur* : destruction sécurisée par glisser-déposer (1, 3 ou 7 passes).

**Partout** — Icône de barre des menus (jauges, réseau, température, appareils connectés avec éjection, nettoyage express), alertes de santé et notifications (disque plein, surchauffe, RAM saturée, app qui monopolise le CPU, batterie usée), nettoyage automatique planifié, lancement à l'ouverture de session, dossiers exclus, raccourcis ⌘1 à ⌘5.

## Sécurité
- Ce qui se recrée tout seul (caches, journaux, Corbeille) est supprimé définitivement ; tout le reste va **à la Corbeille**.
- Chaque action destructive demande confirmation ; les doublons et images similaires gardent toujours au moins une copie.
- Aura ne modifie jamais la photothèque Photos, ni les fichiers des apps (pas de suppression de langues ni d'architectures, qui casseraient leur signature).

## Mises à jour
Aura vérifie toute seule les nouvelles versions (au démarrage puis toutes les 6 h) et s'installe en un clic, ou automatiquement si tu l'actives dans Réglages › Mises à jour.
Côté code : à chaque envoi dans `aura/`, GitHub compile Aura ; quand le numéro du fichier `aura/VERSION` change, une version « aura-vX.Y.Z » est publiée automatiquement (notes tirées de `CHANGELOG.md`).

## Installation (tout-en-un, la première fois seulement)
1. Dézippe Aura.zip.
2. Ouvre le dossier Aura, fais un **clic droit sur « Installer Aura.command » › Ouvrir**, puis confirme « Ouvrir » (macOS demande cette confirmation pour tout script téléchargé).
3. Laisse faire : l'installeur vérifie macOS, installe les outils Apple si besoin, compile, place Aura dans Applications, la lance et ouvre le réglage « Accès complet au disque ».
4. Dans ce réglage : « + » › Aura › active l'interrupteur, puis relance Aura.

En cas d'erreur de compilation, un fichier **Aura-erreurs.txt** apparaît sur le Bureau : envoie-le à Claude.


## Hors périmètre (volontairement)
- Nettoyage d'e-mails en ligne et gestion des onglets Chrome : demandent une connexion à ton compte ou une extension de navigateur.
- Antivirus à signatures : Aura s'appuie sur XProtect (l'antivirus d'Apple) et sur une détection comportementale des menaces Mac courantes.
