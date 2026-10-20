# Foulée — fiche de reprise

Version en ligne : **v8.9** (19 octobre 2026). À lire en premier dans toute nouvelle session.

## Ce qu'est Foulée

Application personnelle de Christophe pour le trail et le renforcement (kettlebell, poids du corps, callisthénie), avec un module pont « Cross-training » et un coach IA (Claude, clé API de l'utilisateur). PWA en **un seul fichier `index.html`** (HTML/CSS/JS vanilla, sans framework ni build), installée sur iPhone et iPad, plus une app Apple Watch en SwiftUI.

- Spécification complète, à jour en v8.9 : le doc « Foulée — prompt complet de l'application » sur claude.ai
  (https://claude.ai/code/artifact/31b0c1a1-6a0d-4757-8b4c-fa00e16f9ad2).
- Préférences de travail : réponses en **français**, tutoiement ; **modifications directes** plutôt que des instructions ; tester puis publier sans demander à chaque étape.

## Fichiers (dossier `foulee/` du dépôt `TAF-ROISSY/AI`)

| Fichier | Rôle |
| --- | --- |
| `index.html` | Toute l'app. Constante `APP_VER`. |
| `sw.js` | Service worker. `CACHE = 'foulee-vX.Y'` à incrémenter à chaque version. |
| `manifest.webmanifest`, `icon-*.png` | Installation PWA. |
| `watch/*.swift` + `README.md` | App Apple Watch (6 fichiers) ; `watch/iPhone/FouleeCompanionApp.swift` = app iPhone relais (lien `fouleewatch://`, WatchConnectivity). |
| `tests/` | Suite Playwright (voir plus bas). |
| `REPRISE.md` | Cette fiche. |

## Publier une version (important)

GitHub Pages sert la branche **`codex/market-monitor`**, pas `main`, et l'utilisateur n'a pas accès aux réglages Pages. À chaque version :

1. Incrémenter `APP_VER` dans `index.html` et `CACHE` dans `sw.js`.
2. Lancer les tests (`python3 tests/run.py`), zéro erreur JavaScript attendue.
3. Commiter `foulee/…` sur **`main` ET `codex/market-monitor`** (auteur : Christophe `<christophe.taf@gmail.com>`).
4. Attendre que l'action GitHub Pages de `codex/market-monitor` soit `completed success`
   (`gh api repos/TAF-ROISSY/ai/actions/runs`), puis annoncer la version.
5. Sur l'iPhone : fermer et rouvrir l'app pour charger la nouvelle version.

L'adresse publique est celle de GitHub Pages pour le dossier `foulee/` (celle déjà installée sur l'iPhone).

## Tests

```
pip install playwright icalendar tree-sitter tree-sitter-swift   # Chromium est déjà présent dans l'environnement cloud
python3 tests/run.py          # toute la suite ; ou : python3 tests/run.py t16 t17
```

Les tests chargent la démo, simulent Strava, Anthropic, GitHub Gist, Open-Meteo et les tuiles de carte, puis vérifient chaque fonction. Captures d'écran dans `tests/out/`. `tests/shots.py <préfixe>` photographie les 11 écrans pour une revue visuelle. Ne jamais lancer `pkill` sur le serveur : les tests démarrent et arrêtent eux-mêmes `http.server` sur le port 8765.

| Test | Couvre |
| --- | --- |
| t4 | Adaptation des séances muscu (bruit, douleurs, matériel) |
| t5 | Coach IA (chat, séance, bilan) |
| t8 | Historique, carte du tracé, programme d'après l'année |
| t9 | Défis « Gods » et chrono de défi |
| t10 | Visuels d'exercices |
| t11 | Analyse de l'année et parcours similaires |
| t12 | Analyse corporelle par photos |
| t13 | Synchro chiffrée, carnet de charges, objectif course GPX, vidéo technique |
| t14 | Figures (callisthénie) |
| t15 | Placement, qualité, vidéo de figure, album, chaleur, récupération cardiaque, carte musculaire, partage |
| t16 | Fatigue croisée, affûtage, routines, import GPX/FIT, score de polyvalence |
| t17 | Sauvegarde/restauration, stockage, réinitialisation, export .FIT/.TCX, autres sports, zones FC |
| t18 | KB 8–24 kg et paire, exercices libres, guidage vocal, historique du coach |
| t29 | Export du plan complet dans le calendrier (.ics journée entière, UID par séance, filtres course / muscu / cycle) |
| t30 | Apparence : thèmes crépuscule / nuit / clair / auto, palettes, polices, persistance par appareil, appliquée dans le head |
| t31 | Traces de trail : Overpass (relations route hiking/foot/running), chaînage des tronçons, boucle/aller simple, % nature, D+ Open-Meteo et cache, filtres, carte, fiche, GPX, favoris + tombstone, erreur serveur |
| t32 | v8 : 5 sections + sous-sections, Aujourd’hui, Plus, mémoire de sous-section, compat setMod/showTab, iPhone / iPad 1194 / Mac 1512 (barre latérale, colonnes, coach en panneau, pas de débordement) |
| t33 | Autres sports : choix des sports, semaine type, Aujourd’hui / Semaine / calendrier, coche = saisie, rattachement Strava, stats, tombstones, import filtré par sports choisis |
| t34 | Design system pro : défaut Nuit pro / Sport / Inter et migration, anneaux, dernière activité (Strava / fichier), infobulle tactile, écran partagé de l’analyse sur iPad, thème clair |
| t35 | Analyse avancée : GAP, découplage, efficacité, montées / descentes, meilleurs efforts, régularité, records, analyse groupée, fichier importé |
| t36 | Test VMA guidé (GPS simulé, annonces, recalcul des allures) et saisi ; coach pro (réajustement IA appliqué, annulation, plan d’origine, auto du dimanche, calage sur la course) ; description Strava (scope, PUT, file d’attente) |
| t37 | Nutrition (calculs par durée / chaleur, prises, sac, ravitos, rappels vocaux en sortie guidée) ; chaleur (météo auto, journal, acclimatation 14 j) |
| t38 | Check-up (FC réveil vs référence, courbatures, énergie, douleurs → forme, séances 🩹, zones muscu, journal, suppression) ; chaussures (Strava gear, paires saisies, usage, alerte, retrait) |
| t39 | Cartes hors ligne (tuiles CORS en cache, pas de double téléchargement, suppression) ; bilan de la semaine en image ; défis entre amis (gist secret, lien #ami=, classement, retrait, lien illisible) |
| t40 | Apple Santé (analyse des formats, presse-papiers, lien #sante=, VFC vs normale, sommeil / FC reportés) ; mobilité guidée (routines, recommandation, chrono) |
| t41 | Suivi de trace (montée / sommet / descente / ravito / km / hors trace / retour) ; jour J (semaine de course, checklist, passages), récupération appliquée au plan, résultat |
| t28 | Voix iPhone : déblocage au premier toucher, parole synchrone dans un toucher, session audio « playback », bips de secours, diagnostic « Tester la voix » (son / silencieux) |
| t27 | Envoi d’une séance guidée à l’Apple Watch (URL `fouleewatch://plan?d=` en base64url, format compatible GuidedRun.swift, accents) + analyse syntaxique tree-sitter de tous les fichiers Swift |
| t26 | Voix du coach (choix de la voix, débit), chrono (moitié, efforts restants, 10 s), course guidée GPS simulée (km, cible, fractions de 400 m, récup, point à la demande, enregistrement), rattachement Strava (type, ±1 jour, détacher) |
| t25 | Séances avec matériel ou au poids du corps : programme STRBW sans KB, bascule par séance et défaut, barre ou table, adaptations (genou, silencieux), contexte du coach |
| t24 | Calendrier famille : fichier .ics validé avec `icalendar` (fuseau Europe/Paris, rappel, UID, SEQUENCE, lignes ≤ 75 octets), journée entière, Google Agenda, envoi, tout le planning, état à mettre à jour, ouverture sur iPhone |
| t23 | Calendrier v7 : périmètres, types, D+, distances, 30 jours, Autour de moi (rayon, tri secondaire), carte à marqueurs, événements terminés, fiche épreuve (profil, liens, objectif), météo Open-Meteo, cache IndexedDB et migration |
| t22 | Adeorun dans le calendrier ; GPX d'une course du planning : récupéré par web_fetch, lien direct (CORS), fichier coupé, mauvaise distance, liens seuls, import manuel, recherche auto à la saisie du format |
| t21 | Onglet Courses : planning (statut, priorité, objectif du plan, écarts), calendrier Oise (filtres, tri près de moi, carte), recherche en ligne par le coach (web search, pause_turn) |
| t20 | Sommeil (saisie, forme, Coach du jour, suppression synchronisée), projection du ratio 7 j / 28 j, étoiles de la semaine et badges de bloc |
| t19 | Coach du jour : moments (matin, après-midi, après séance, soir), ressenti, conseil IA manuel et automatique, carte repliée |

Le fichier .FIT d'export se valide avec le SDK Garmin officiel : `pip install garmin-fit-sdk`.

## Méthode de modification

Le fichier fait environ 430 Ko. Méthode éprouvée : un script Python de remplacements exacts (`rep(ancien, nouveau, nombre)` qui s'arrête si l'ancrage n'est pas trouvé exactement), une sauvegarde de `index.html` avant chaque patch, puis les tests. Les pages sont des `<section class="page" data-page="…">` rendues par `renderX()` ; `renderAll()` les appelle toutes ; état global `S` dans `localStorage` (`foulee_v1`).

## Historique des versions récentes

| Version | Contenu |
| --- | --- |
| 7.5 | Export du plan d’entraînement (course + muscu, 12 semaines) dans le calendrier : bandeau dans Plan, .ics journée entière, détail de la séance en note, réexport sans doublon (UID par séance, SEQUENCE croissante). Strava n’a pas d’API pour les séances prévues |
| 7.6 | Réglages › 🎨 Apparence : 4 thèmes (Crépuscule, Nuit OLED, Clair, Auto qui suit l’iPhone), 6 palettes (Crépuscule alpin, Forêt, Océan, Volcan, Lavande, Monochrome), 5 polices (Sport, Moderne, Très lisible, Arrondie, Système). Stocké par appareil dans `localStorage.foulee_look` (non synchronisé), appliqué par un script dans le `<head>` (`lookApply`). Couleurs passées en variables CSS (`--ink`, `--tx2`, `--hdr`, `--navb`, `--sheet`, `--hero1/2`, palettes `--pT/--pM/--pC`) ; en clair les accents sont assombris par `color-mix` |
| 7.7 | Voix en mode silencieux : `navigator.audioSession.type='playback'` (iOS 17+) et lecture d’un son muet en média (`vPrime`, boucle pendant chrono et course guidée via `vKeep`) pour que la synthèse vocale ne soit plus coupée par le bouton silencieux. Bips de secours lus en média (`tone`) si la voix ne démarre pas (réglage `voiceBeep`). « Tester la voix » joue un double bip puis la voix et explique quoi faire selon ce qu’on a entendu |
| 7.8 | Courses › 🧭 Traces de trail : itinéraires balisés OpenStreetMap partout (Overpass, 2 serveurs), autour de moi ou d’un lieu (Nominatim), rayon 5–50 km. Filtres : texte, distance, D+, profil (m/km), boucle / aller simple, % nature (tags highway/surface des chemins), balisage GR / GRP / PR / trail. Tri : proximité, longueur, D+, pente. D+ calculé sur 100 points d’altitude Open-Meteo (cache `localStorage.foulee_trc`). Fiche avec carte, profil, temps estimé, GPX (ODbL), favoris `S.trFav` synchronisés (tombstone `trfav`) |
| 8.0 | Refonte de la navigation : 5 sections en bas (Aujourd’hui, Plan, Courses, Analyse, Plus) au lieu de 3 modules × 5 onglets. `SECT` décrit sections et sous-sections (Plan : Course / Muscu / Semaine ; Analyse : Sorties / Analyse / Forme / Progrès ; Plus : hub + Figures, Défis, Chrono, Bilans), affichées dans `#modSeg`. Nouvelle page Aujourd’hui (`renderToday` : forme, séances trail + muscu du jour, semaine en pastilles, coach du jour, course, sommeil, chaleur, séance sur mesure) et page Plus (`renderPlus`, tuiles). `setMod(m,tab)` conservé pour compatibilité ; onglet restauré au lancement (`localStorage.foulee_tab`). iPad / Mac ≥ 1024 px : barre latérale, contenu en 2 colonnes (3 au-delà de 1500 px), réglages en fenêtre centrée, coach en panneau à droite |
| 8.1 | Autres sports : catalogue de 18 sports (`XTYPES` : icône, nom, coefficient de charge, types Strava, unité km / m), choix « Mes sports » (`S.settings.sports`, défaut vélo, VTT, rando, natation, ski de rando) qui filtre aussi l’import Strava. Plan › Autres sports (`renderSports`) : semaine type récurrente `S.xplan` [{id,type,day,min,int e/t/i,km,note,name}] → séances `x<sem>_<id>` dans `daySessions` (kind `x`), Aujourd’hui (pastilles bleues), Semaine, charge prévue, export calendrier (`PCD.x`), contexte du coach. Cocher crée une saisie `p<clé>` à ajuster ; une activité Strava du même sport (ou de la même famille vélo / marche) le même jour coche et lie la séance (`linkX`, appelé par `linkPlan`). Stats 4 semaines (durée, distance, vitesse km/h ou /100 m). Tombstones `xplan` et `xact` |
| 8.2 | Design system « pro » (bloc CSS commenté en 7 parties à la fin du `<style>`) : jetons (`--ease`, `--t`, `--r-*`, `--edge`, `--hl`, `--shadow`, `--glow`), nouveau défaut Nuit pro (noir mat #0A0C0F) + palette Sport (corail #FF5F2E, ambre #FFB224, turquoise #2FD3C7) + police Inter, l’ancien défaut est migré (`LOOK_DEF`, `v:2`) et « Crépuscule » reste au choix. Cartes en dégradé avec liseré clair, bordure lumineuse (`.lum`, `.hero::after`), boutons en dégradé avec halo, barre et en-tête vitrés, transitions de page et de feuille, anneaux animés, `prefers-reduced-motion` respecté. Infobulles `[data-tip]` (survol et toucher) sur les graphiques semaine, charge, sommeil et profils. Aujourd’hui : anneaux de la semaine (`weekRings`) et dernière activité Strava ou fichier GPX/FIT (`lastActCard`, tracé miniature `routeSvg`). Analyse d’une sortie en écran partagé (carte à gauche, données à droite) dès 1024 px. Couleurs des cartes Leaflet tirées de la palette (`cssv`) |
| 8.3 | Analyse ultra-précise (`anaRun`) sur chaque sortie Strava et fichier importé : allure ajustée à la pente (Minetti, `gradeMult`), découplage cardiaque 1re / 2e moitié (allure ajustée ÷ FC), indice d’efficacité, irrégularité (écart-type par 500 m) avec graphique, montées et descentes détectées (hystérésis 10 m, ≥ 25 m, ≥ 3 %) avec VAM et FC, meilleurs efforts 400 m → semi. Résumés gardés dans `S.eff` (synchronisé, 250 sorties) → carte Records & tendances dans Analyse (records cliquables, courbe d’efficacité, tendance) et « Analyser mes 20 dernières sorties » (`anaBatch`). Courbe d’allure ajustée ajoutée au profil |
| 8.4 | Test VMA guidé dans la course guidée (demi-Cooper 6 min ou Cooper 12 min : échauffement, test avec minutes restantes annoncées, VMA = distance ÷ 100 ou ÷ 200) ou saisi (`S.vma`) ; un test de moins de 150 jours remplace l’estimation des allures (10 km à 90 % de VMA, allure VMA = 3600 / VMA) ; carte Test VMA avec zones en % de VMA (Plan › Course). Coach pro (carte en tête de Plan › Course) : frise de périodisation des 12 semaines (Force, Vitesse, Seuil, Affûtage) avec la course, bouton « Caler le plan sur la course » (semaine 12 = semaine de course) ; réajustement IA des 7 prochains jours (`adjWeek`, outil `reajuster_semaine` : alléger / remplacer / annuler) stocké dans `S.adj` et appliqué par `adjO` dans `daySessions` (↓, 🔁, ⏸ ; annulées hors charge, calendrier et rattachement Strava), retour au plan d’origine, automatique le dimanche soir (`S.settings.coachWeekly`, `adjAuto`). Séance prévue écrite dans la description de la sortie Strava (`S.settings.stravaWrite`, scope `activity:write`, file `S.descQ`, `stravaDescFlush` après synchro), renommage optionnel des sorties au nom par défaut |
| 8.5 | Plan nutrition & hydratation (`openFuel`, `fuelCalc`) : depuis la course objectif (durée estimée, ravitos de la stratégie, température) ou Plus ; glucides 0 / 30 / 45 / 60 / 70 g/h selon la durée, eau 400 à 900 ml/h selon chaleur et poids, sodium 300 à 700 mg/h, prises toutes les 20 min alignées sur les ravitos, contenu du sac, repas de la veille et petit-déjeuner ; rappels vocaux boire / gel toutes les 20 min dans les sorties guidées de plus d’1 h 15 (`S.settings.fuelVoice`). Mode chaleur & voyage : journal météo `S.heatLog` (60 j), acclimatation = séances de 30 min et plus par jour chaud (≥ 25 °C ou ralentissement ≥ 2 %) sur 14 jours, objectif 10 (`acclim`, `acclimBlock` dans la carte Chaleur), météo automatique à l’ouverture là où tu es (`S.settings.heatAuto`, `heatAutoRun`) |
| 8.6 | Check-up du matin (`openCheck`, `S.check[date]` = FC réveil, courbatures 0-3, énergie 0-3, douleurs par zone 1-3) : effet sur la forme (`checkEffect` : FC +5 / +8 bpm sur la médiane des 30 derniers jours ou la FC de repos, courbatures, moral, douleur), séances de course du jour et du lendemain adaptées si douleur ≥ 2 au bas du corps (`chkO` dans `daySessions`, 🩹 ; forte = pas de course), genou / hanche / dos / épaule ajoutés aux zones de la muscu ; carte dans Aujourd’hui et Forme, journal du corps sur 28 jours (zones + courbe FC réveil). Chaussures (`openShoes`) : paires Strava (`S.gearStrava` lu sur /athlete à la synchro, NOSYNC, `gear_id` sur les sorties) + paires saisies (`S.shoes` : km de départ, paire par défaut), km, usage par type de sortie, durée de vie (700 km par défaut), alerte à 90 % dans Aujourd’hui, retrait |
| 8.7 | Cartes hors ligne : tuiles relief d’une trace ou du GPX de la course (zoom 10 à 16, réduit pour rester ≤ 350 tuiles) téléchargées en CORS dans le cache `foulee-tiles` (les réponses opaques font exploser le quota), servies par le service worker en priorité, liste et suppression dans Plus (`localStorage.foulee_off`). Bilan de la semaine en image 1080×1350 (`shareWeek` : anneaux, km, séances, durée, D+, meilleure sortie) via le partage de l’iPhone ; bandeau le dimanche après-midi / lundi matin et bouton 📸 dans « Ta semaine ». Défis entre amis : totaux du mois (km, D+, heures, séances) et pseudo publiés dans un gist secret (`S.defiMe`, mis à jour après chaque synchro), lien `#ami=<id>` qui ajoute l’ami (`S.friends`, tombstone `friends`, aussi sur `hashchange`), classement par indicateur (`openDefis`) |
| 8.8 | Apple Santé par un raccourci iPhone : le raccourci lit VFC, FC au repos et sommeil dans Santé et copie `FOULEE{"hrv":…,"rhr":…,"sleep":…}` ; bouton Importer (presse-papiers) ou collage manuel, ou lien `#sante=` (texte ou base64url, utile avec la synchro car Safari et l’app installée n’ont pas la même mémoire). `S.health[date]` (120 j) ; sommeil et FC repos reportés dans `S.sleep` et `S.check` s’ils manquent ; effet VFC sur la forme (`hrvEffect` : z-score du log de la VFC sur les 28 jours, −14 / −7 / +4) ; carte Apple Santé (Aujourd’hui si activée, Forme avec courbe 30 j et bande normale), guide pas à pas du raccourci (`openHealthHelp`). Mobilité guidée : 5 routines (`PREV.mob_*` : après course, hanches, pieds-chevilles-mollets, dos, échauffement dynamique ; 12 positions ajoutées à `CUE`) au chrono avec la voix ; « Mobilité du jour » dans Aujourd’hui selon la douleur du check-up, une séance dure faite ou une séance de qualité à venir (`mobReco`) |
| 8.9 | Suivi de trace à la voix : `routeOpen(id)` (GPX de la course, traces trouvées, fichiers importés) lance la course guidée sur la trace ; `routeBuild` calcule distance cumulée et montées / descentes (altitude lissée, points tournants à 12 m, extrémités plates rognées, ≥ 25 m, ≥ 200 m, ≥ 3,5 %) ; `routeTick` à chaque position : point le plus proche, alerte hors trace (> 60 m pendant 12 s) et retour, annonce 250 m avant chaque montée / descente, sommet, ravito à 1 km, kilomètre de trace avec avance / retard sur la stratégie de course ; mini-profil avec position dans l’écran guidé. Mode jour J (`openRaceDay`) : compte à rebours, checklist matériel (`S.rdKit`, gels / flasques du plan nutrition, frontale si départ avant 7 h), temps de passage aux sommets, ravitos et arrivée avec l’heure réelle, conseils J-7 à J+7 ; carte « Semaine de course » puis « Récupération » dans Aujourd’hui ; après une course, `recO` adapte les séances (J+1 à J+3 repos, qualité remplacée par du facile jusqu’à 1 jour par 10 km) ; résultat de course (`openRaceResult` → `S.races[].res` en secondes, place, note) |
| 7.4.1 | Voix iPhone fiabilisée : déblocage de la synthèse au premier toucher, plus de cancel() suivi d’un speak() différé pendant un toucher, énoncés gardés en mémoire, resume(), langue alignée sur la voix choisie, alerte « pas de voix ? » et diagnostic dans Réglages › Voix du coach |
| 7.4 | Apple Watch : course guidée vocale écran verrouillé (GuidedRun.swift : AVSpeechSynthesizer fr-FR, distance HealthKit, mêmes annonces que l’iPhone, vibrations), app iPhone compagnon relais, bouton « ⌚ Envoyer à l’Apple Watch » dans Foulée |
| 7.3 | Course guidée GPS avec voix (annonces de départ, moitié, fin, fractions restantes, km et allure cible, « Où j’en suis ? »), chrono enrichi, rattachement automatique des sorties Strava aux séances du plan (`S.links`, détacher), voix du coach réglable et lecture des conseils |
| 7.2 | Muscu : choix « Avec matériel » / « Poids du corps (callisthénie) » par défaut (carte dans Séances) et par séance (bascule sur chaque carte A/B/C) ; programme STRBW de 12 semaines sans kettlebell (11 nouveaux exercices : dips, pompes archer, pistol sur chaise, nordic curl, L-sit, front lever groupé…) |
| 7.1 | Partage des courses du planning vers le calendrier famille : .ics (heure de départ du format, fin estimée, rappel la veille, UID stable et SEQUENCE pour les mises à jour), Google Agenda, envoi par Messages ; proposé au passage en « Inscrit » |
| 7.0 | Calendrier des épreuves : 92 épreuves (Oise + Somme, Aisne, Val-d'Oise, Seine-et-Marne), filtres périmètre / distance / D+ / type / période, « Autour de moi » avec rayon 5–50 km, carte à marqueurs par type, événements terminés, fiche épreuve (profil théorique, liens site et inscription, « Définir comme objectif »), météo prévisionnelle à J-14 appliquée à la stratégie, cache IndexedDB `events` (base v3) des actualisations en ligne |
| 6.9 | Adeorun ajouté comme source (19 liens de courses, dates confirmées) ; tracé GPX trouvé automatiquement quand le format (km) d'une course est saisi : `web_search` + `web_fetch`, GPX lu dans la réponse, contrôle ±20 % de la distance, sinon lien + import manuel |
| 6.8 | Onglet Courses dans Trail : planning des courses (`S.races`), calendrier intégré de 46 trails de l'Oise (`OISE_TRAILS`, relevé du 19/10/2026, à rafraîchir), recherche en ligne par le coach (outil web_search de l'API) |
| 6.7 | Sommeil noté le matin (`S.sleep` par date) qui règle la forme du jour et allège la séance dure ; « Semaine prévue » : ratio 7 j / 28 j projeté jusqu'à dimanche ; étoiles de la semaine (régularité, charge, sommeil) et badges de bloc |
| 6.6 | Coach du jour : carte en tête des accueils Trail, Muscu et Cross qui change selon le moment (matin, après-midi, après séance, soir) ; conseils calculés hors ligne + « ✨ Conseil du coach » (option automatique, ~3 appels/jour) ; heure de chaque séance cochée (`S.doneAt`) ; chemins des tests t4–t11 rendus relatifs |
| 6.5.1 | Textes affichés en entier, niveaux de défi lisibles, tests autonomes (Leaflet inclus) |
| 6.5 | Mise en ordre de l'interface : accueil Muscu recentré, actions de séance sur une ligne, cartes repliables, figures et défis compacts, chrono dans l'en-tête, textes d'aide repliés, icônes de titres |
| 6.4 | Sauvegarde JSON, stockage, réinitialisation ; export de séance .FIT/.TCX ; autres sports d'endurance ; zones FC Karvonen ; KB 8–24 kg + paire ; exercices libres ; guidage vocal ; historique du coach |
| 6.3 | Fatigue croisée D−/D+, affûtage, routines Pied & Cheville / Descente blindée / Core & Posture, import GPX/FIT + diagnostic de pente, score de polyvalence, curseurs de ressenti, zone TFL |
| 6.2 | Placement, décharge, radar, anneaux/parallettes, vidéo des figures + album, chaleur, récupération cardiaque, carte musculaire, cartes de partage, figures sur la montre |
| 6.1 | Onglet Figures (12 parcours de callisthénie) |
| 6.0 | Synchro chiffrée iPhone/iPad, carnet de charges, objectif course et stratégie d'allure, analyse vidéo de la technique |

## Points non vérifiés en conditions réelles

- Import d'un vrai fichier FIT de montre (seuls des fichiers générés ont été testés).
- Fichier .FIT de séance chargé sur une vraie montre Garmin ou Coros.
- Guidage vocal sur iPhone (testé avec une voix simulée).
- Compilation de l'app Watch et de l'app iPhone compagnon dans Xcode (syntaxe Swift vérifiée avec tree-sitter seulement) ; voix de la montre écran baissé ; passage du lien `fouleewatch://` depuis la PWA installée.
- Météo Open-Meteo et partage natif depuis l'iPhone.
- Course guidée sur iPhone : GPS et voix tant que l’écran reste allumé et Foulée au premier plan ; mélange de la voix avec Spotify.
- Ajout du .ics au calendrier « Famille » depuis la PWA installée (ouverture d'une URL data:text/calendar).
- Recherche du GPX avec une vraie clé : support de `web_fetch` pour un fichier `.gpx` (type de contenu non documenté) et coût réel par course.

## Données à rafraîchir

- `OISE_TRAILS` / `OISE_GEO` et `EXTRA_TRAILS` / `EXTRA_GEO` (hors Oise, relevé Go Trail et Miles Republic) dans `index.html` : calendrier des trails de l'Oise relevé le 19/10/2026 (Adeorun, Miles Republic, Go Trail, Ahotu ; liste Adeorun : calendrier.adeorun.com). Mettre à jour `OISE_UPD` et les dates « AAAA-MM » quand les dates 2027 sont publiées. Coordonnées des communes : geo.api.gouv.fr.

## Idées en attente

- Vérifier que les tuiles OpenTopoMap acceptent le téléchargement en CORS (cartes hors ligne) sur un vrai iPhone.
- Trace GPS des courses guidées de la montre dans Santé/Strava (HKWorkoutRouteBuilder + CoreLocation).

- Journal alimentaire (une question restait ouverte dans le document d'analyse : chaleur ou journal alimentaire en priorité ; la chaleur a été faite en v6.2).
- Synchro des étapes de figures entre l'iPhone et la montre (impossible depuis une PWA sans app iOS native).
