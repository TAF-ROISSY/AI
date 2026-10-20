# Foulée — app Apple Watch

Minuteur Intervalles / EMOM / Tabata / AMRAP / Chrono, avec vibrations, fréquence cardiaque en direct et séance enregistrée dans Santé.

## Installer sur ta montre (Mac + Xcode, gratuit)

Depuis la v7.4, le projet a **deux cibles** : l’app de la montre et une mini-app iPhone « Foulée ⌚ » qui sert de relais pour recevoir les séances guidées envoyées depuis l’appli web. Si tu avais déjà le projet « Watch-only », recrée-le avec le modèle ci-dessous (les records des défis restent sur la montre).

1. **Xcode** (App Store) → *File › New › Project* → onglet **watchOS** → **App** → Suivant.
   - Product Name : `Foulee` · Interface : SwiftUI · Language : Swift
   - **Watch App with New Companion iOS App** (cible iPhone + cible montre).
2. Cible montre (**Foulee Watch App**) : supprime le `ContentView.swift` et le fichier `…App.swift` générés, puis glisse les **6 fichiers `.swift`** de ce dossier (`FouleeWatchApp`, `TimerEngine`, `WorkoutManager`, `Defis`, `Figures`, `GuidedRun`) en cochant uniquement la cible montre et « Copy items if needed ».
3. Cible iPhone (**Foulee**) : supprime ses `ContentView.swift` et `…App.swift` générés, puis glisse `iPhone/FouleeCompanionApp.swift` en cochant uniquement la cible iPhone.
4. Cible **Foulee Watch App** → **Signing & Capabilities** :
   - Team : ton identifiant Apple (compte gratuit possible).
   - **+ Capability › HealthKit**.
   - **+ Capability › Background Modes** → coche **Workout processing** et **Audio** (la voix continue écran baissé).
5. Cible **Foulee Watch App** → onglet **Info**, ajoute :
   - `Privacy - Health Share Usage Description` : *Lire la fréquence cardiaque et la distance pendant la séance.*
   - `Privacy - Health Update Usage Description` : *Enregistrer tes séances dans Santé.*
6. Cible iPhone **Foulee** → **Signing & Capabilities** : même Team. Puis onglet **Info › URL Types › +** : Identifier `com.foulee.watch`, **URL Schemes** `fouleewatch`. C’est ce qui permet à l’appli web d’ouvrir le relais.
7. Branche l’iPhone appairé à la montre, active le **Mode développeur** (iPhone et montre : Réglages › Confidentialité et sécurité), choisis ton iPhone comme destination avec le schéma **Foulee**, puis **▶ Run** : l’app iPhone s’installe, et l’app montre avec elle (sinon, choisis le schéma *Foulee Watch App* et ta montre, puis Run).

Avec un compte Apple gratuit, les apps expirent au bout de 7 jours : relance simplement *Run* depuis Xcode. Avec le programme développeur payant (99 €/an), elles restent un an.

## Course guidée à la voix (v7.4)

1. Dans Foulée (iPhone) : séance de course du plan → **🎧 Guidée** → **⌚ Envoyer à l’Apple Watch**. iOS demande d’ouvrir « Foulée ⌚ » : accepte, l’écran confirme « Envoyée à la montre ✓ ».
2. Sur la montre : **Foulée › 🏃 Trail › Course guidée 🔊** → la séance reçue est en tête de liste (les 10 dernières sont gardées). Sans iPhone, *Footing libre* règle distance et allure à la Digital Crown.
3. **Démarrer** : la montre lance une séance course à pied (GPS de la montre, fréquence cardiaque, enregistrée dans Santé puis Strava) et parle :
   - au début de chaque étape (échauffement, fraction « 400 mètres, vise 4:02 au kilomètre », récupération et fractions restantes, retour au calme) ;
   - à la moitié de chaque fraction ou du footing, avec ton allure et le verdict (« dans la cible », « ralentis de 8 secondes au kilomètre ») ;
   - « Plus que 100 mètres », puis le temps et l’allure de la fraction terminée ;
   - à chaque kilomètre : temps du km, allure moyenne, verdict, distance et temps restants ;
   - si l’allure sort de la cible plus de 45 s (au plus toutes les 2 min), avec une vibration montante ou descendante ;
   - « Prêt, 10 secondes » et 3 tapes avant la fin d’une récupération.
4. Bouton **🔊 Où j’en suis ?** : distance, temps, allure actuelle, verdict et ce qui reste. Option point vocal toutes les 5 ou 10 min.
5. La voix sort par le haut-parleur de la montre, ou par les AirPods s’ils sont connectés **à la montre**. Si Spotify joue sur la montre, la musique baisse pendant l’annonce. Si Spotify joue depuis l’iPhone dans les AirPods, la voix sort par le haut-parleur de la montre.
6. À la fin, **Enregistrer** : la séance part dans Santé, puis Strava, et Foulée la rattache automatiquement à la séance du plan.

À vérifier sur ta montre au premier essai : la voix écran baissé (Apple a eu des soucis de synthèse vocale en arrière-plan sur certaines versions de watchOS ; les vibrations, elles, marchent toujours). L’app ne dessine pas encore la trace GPS dans Strava (distance et allure oui).

## Piloter Foulée depuis la montre

### Sans rien installer : la télécommande « À l’écoute » (v9.9)
Quand une course guidée ou le chrono tourne dans Foulée sur l’iPhone, l’appli s’affiche comme un lecteur audio. Sur la montre, ouvre **À l’écoute** (elle s’ouvre souvent toute seule, sinon : Réglages de la montre › Général › Réveil de l’écran › Ouvrir automatiquement l’app audio) :
- **⏯** : pause / reprise de la séance ;
- **⏭** : étape suivante (chrono : phase suivante) ;
- **⏮** : point vocal « où j’en suis » (chrono : annonce de la phase).
Le titre affiché donne l’étape, la distance, le temps et l’allure. Les mêmes commandes marchent avec les **AirPods** (double toucher = étape suivante, triple = point vocal ; pression sur la tige des AirPods Pro = pause) et sur l’écran verrouillé de l’iPhone. La voix reste celle de l’iPhone.

### Avec l’app montre : commandes vocales et double tap (v9.9)
Pendant une course guidée lancée sur la montre :
- bouton **🎙 Parler** : touche le micro et dis « où j’en suis », « pause », « reprends », « étape suivante », « termine » (confirmation à l’écran) ou « j’ai mal au genou / mollet / tibia… » (consigne de sécurité adaptée à l’intensité de la douleur) ;
- **double tap** (pincer deux fois l’index et le pouce, Apple Watch Series 9, Ultra 2 et plus récentes, watchOS 11) : point vocal « où j’en suis », sans toucher l’écran.
Après mise à jour des fichiers, relance *Run* dans Xcode pour réinstaller l’app.

## Utilisation

- **🏃 Trail** : côtes, VMA, seuil. Ajuste la durée du 400 m à ton allure affichée dans le module Trail › Plan de l’appli.
- **🏋️ Muscu** : défis Sommets + minuteurs renfo (séries, circuit, EMOM, AMRAP, abdos).
- **Minuteur libre** : règle effort, récup, répétitions à la Digital Crown.
- Vibrations : 3 tapes avant chaque changement, vibration longue au départ d’un effort.
- L’écran peut se baisser : la séance continue (session d’entraînement active).

## Défis Sommets

Les **39 défis** de l'appli, classés comme sur l'iPhone : 8 Sommets et les 31 Dieux (Aphrodite, Zeus, Kronos…), 3 niveaux chacun, avec les mêmes répétitions et les mêmes paliers (50-40-30-20-10…). Tape **✓ Tour** à la fin de chaque tour ou palier : la montre vibre et affiche ton avance ▲ ou ton retard ▼ sur ton record. Pour Zeus et Hermes, un **repos de 2 min** se lance tout seul entre les tours, avec une vibration au départ du tour suivant. À la fin, donne ton ressenti : « Trop facile » ou « Parfait » débloque le niveau suivant.

La montre ne connaît pas ton matériel : les tractions s'affichent « Tractions (ou rowing KB) ». Les records sont gardés sur la montre (indépendants de ceux de l'iPhone).

## Si l'installation via Xcode est trop contraignante

Avec un compte Apple gratuit, l'app doit être réinstallée depuis Xcode tous les 7 jours. Alternative sans Mac : lance tes séances depuis l'iPhone (chrono de l'appli Foulée, écran allumé) et enregistre la fréquence cardiaque avec l'app **Exercice** de la montre (« Renforcement musculaire fonctionnel ») : la séance remonte dans Santé puis Strava.

## Lien avec Strava

Les séances sont enregistrées dans **Santé** (course à pied ou renforcement). Dans l’app Strava iPhone : *Paramètres › Applications, services et appareils › Santé* → active la synchronisation. Elles remontent dans Strava, puis dans l’analyse de l’appli Foulée.

Pour une sortie trail avec trace GPS, utilise plutôt l’app **Exercice** native de la montre : cette app ne dessine pas le parcours.

## Figures (callisthénie)

Menu Muscu › **Figures** : les 12 parcours de l’appli, avec l’étape en cours, le chrono de maintien (vibration à l’objectif), le compteur de séries et le repos de 90 s. Les flèches changent d’étape ; l’étape est gardée sur la montre. Note toujours tes séries dans l’appli iPhone pour la validation et le suivi.
