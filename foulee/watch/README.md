# Foulée — app Apple Watch

Minuteur Intervalles / EMOM / Tabata / AMRAP / Chrono, avec vibrations, fréquence cardiaque en direct et séance enregistrée dans Santé.

## Installer sur ta montre (Mac + Xcode, gratuit)

1. **Xcode** (App Store) → *File › New › Project* → onglet **watchOS** → **App** → Suivant.
   - Product Name : `Foulee` · Interface : SwiftUI · Language : Swift
   - Watch-only App (pas besoin d’app iPhone compagnon).
2. Supprime le `ContentView.swift` et le `FouleeApp.swift` générés, puis glisse les 4 fichiers `.swift` de ce dossier dans le projet (coche « Copy items if needed »).
3. Cible **Foulee Watch App** → onglet **Signing & Capabilities** :
   - Team : ton identifiant Apple (compte gratuit possible).
   - **+ Capability › HealthKit**.
   - **+ Capability › Background Modes** → coche **Workout processing**.
4. Onglet **Info**, ajoute deux clés :
   - `Privacy - Health Share Usage Description` : *Lire la fréquence cardiaque pendant la séance.*
   - `Privacy - Health Update Usage Description` : *Enregistrer tes séances dans Santé.*
5. Branche l’iPhone appairé à la montre, active le **Mode développeur** (montre : Réglages › Confidentialité et sécurité), choisis ta montre comme destination, puis **▶ Run**.

Avec un compte Apple gratuit, l’app expire au bout de 7 jours : relance simplement *Run* depuis Xcode. Avec le programme développeur payant (99 €/an), elle reste un an.

## Utilisation

- **🏃 Trail** : côtes, VMA, seuil. Ajuste la durée du 400 m à ton allure affichée dans le module Trail › Plan de l’appli.
- **🏋️ Muscu** : défis Sommets + minuteurs renfo (séries, circuit, EMOM, AMRAP, abdos).
- **Minuteur libre** : règle effort, récup, répétitions à la Digital Crown.
- Vibrations : 3 tapes avant chaque changement, vibration longue au départ d’un effort.
- L’écran peut se baisser : la séance continue (session d’entraînement active).

## Défis Sommets

Les 6 défis de l'appli (Ventoux → Kilimandjaro), 3 niveaux chacun. Tape **✓ Tour** à la fin de chaque tour : la montre vibre et affiche ton avance ▲ ou ton retard ▼ sur ton record. À la fin, donne ton ressenti : « Trop facile » ou « Parfait » débloque le niveau suivant. Les records sont gardés sur la montre (indépendants de ceux de l'iPhone).

## Lien avec Strava

Les séances sont enregistrées dans **Santé** (course à pied ou renforcement). Dans l’app Strava iPhone : *Paramètres › Applications, services et appareils › Santé* → active la synchronisation. Elles remontent dans Strava, puis dans l’analyse de l’appli Foulée.

Pour une sortie trail avec trace GPS, utilise plutôt l’app **Exercice** native de la montre : cette app ne dessine pas le parcours.
