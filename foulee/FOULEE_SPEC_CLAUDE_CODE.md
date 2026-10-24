# FOULÉE — Spécification de développement (Claude Code)
Version 2.2 — 24 octobre 2026 · Remplace la partie « développement » du Master Prompt du 21/10/2026.
À lire avec `REPRISE.md` (fiche technique, publication, tests) et `FOULEE_SYSTEM_PROMPT_AI.md` (comportement de l'IA).

---

## 0. Règles absolues

1. **Le produit s'appelle FOULÉE et ne change jamais de nom.** Ne jamais renommer l'application, son titre, le dossier `foulee`, ni les URLs, identifiants ou clés de stockage existants (`foulee_v1`, `foulee_api`, `foulee_look`…).
2. « Personal Sports Intelligence » est un **positionnement**, jamais un nom.
3. **Ne rien casser.** Avant toute évolution : lire `REPRISE.md` et le code concerné, lister ce qui sera touché, préserver les données déjà stockées (migration explicite si le schéma change).
4. **Aucune donnée inventée.** Si une fonctionnalité dépend d'un signal non disponible (§2), elle est désactivée ou marquée « données insuffisantes ». On ne simule jamais un signal absent.
5. **Ce document est la spec dev.** Le comportement de l'IA embarquée est décrit dans `FOULEE_SYSTEM_PROMPT_AI.md`.

---

## 1. Rôles

| Acteur | Rôle |
|---|---|
| **Claude Code** | Construit Foulée : analyse le code, propose, implémente, teste, publie. |
| **Foulée AI** (Claude via API, au runtime) | Intelligence embarquée : analyse, explique, recommande, apprend. |

Claude Code construit le cerveau. Foulée AI est le cerveau.

---

## 2. Sources de données réelles

| Source | Données | Statut |
|---|---|---|
| **Strava API** (activités + streams) | date, type, distance, durée, D+/D−, allure, FC, altitude, cadence (si capteur), GPS, chaussures | En place |
| **Fichiers GPX / FIT importés** | trace, altitude, FC | En place |
| **Check-up du matin** (`S.check[date]`) | FC au réveil, courbatures 0–3, énergie 0–3, **stress de vie 0–3**, **motivation 0–3** (v12.1), douleurs par zone 1–3 | En place |
| **Sommeil** (`S.sleep[date]`) | heures, qualité 1–4 | En place |
| **Apple Santé** via un raccourci iOS (`#sante=`, presse-papiers) | VFC, FC repos, sommeil (`S.health[date]`) | En place (l'utilisateur doit lancer le raccourci) |
| **Ressenti de séance** (`S.fb`), journal vocal | difficulté, énergie, douleurs, texte | En place |
| **Météo** Open-Meteo | température, vent, humidité, pluie | En place |
| **Matériel** | paires Strava + saisies, km | En place |
| **Débrief à chaud** (`S.deb[clé]`) | émotion dominante (8), victoires déclarées, texte / voix | En place (v12.2) |

**Signaux NON disponibles** (ne pas les simuler) : asymétrie de foulée, temps de contact au sol, oscillation verticale, puissance de course (sauf capteur), lactate.

Conséquences : Pre-Injury Radar limité à charge, douleurs déclarées, km chaussures ; Terrain Feel DNA et Allure inconsciente toujours libellés « estimation » / « hypothèse ».

---

## 3. Architecture (existant)

- **Un seul fichier `index.html`** (HTML/CSS/JS vanilla, sans build), PWA iPhone/iPad, + `sw.js`, + app Apple Watch SwiftUI (`watch/`), + serveur de notifications Cloudflare (`push/`).
- État global `S` dans `localStorage.foulee_v1`, **synchro chiffrée** iPhone/iPad par gist (`syncPayload`, `vmerge`, tombstones `S.del[kind]` + `applyTomb`). Les clés listées dans `NOSYNC` restent locales.
- Navigation en 5 sections (Aujourd'hui, Plan, Courses, Analyse, Plus/Ton espace). Les entrées de Ton espace sont dans `PLUSI` et rangées par `SPACE`.
- Modules **Trail** et **Musculation** séparés, reliés par **Cross-training**. Ne pas les fusionner.
- Méthode de modification : script Python de remplacements exacts + sauvegarde avant patch + tests (voir `REPRISE.md`). Les nouveautés d'une version vont dans un bloc `/* ============ vX.Y` placé avant `planStart();viewWeek=…` et une couche CSS `/* ===== vX.Y` en fin du premier `<style>`.

### 3.1 Appel à Foulée AI — DÉCIDÉ : clé stockée sur l'appareil
- Clé API saisie dans **Réglages › Coach**, stockée dans `localStorage.foulee_api` (jamais synchronisée, jamais exportée, jamais dans le code).
- Une seule fonction d'appel : `claude({system, messages, tools, max})` (appel direct navigateur avec `anthropic-dangerous-direct-browser-access`), erreurs traduites (clé invalide, quota, réseau, surcharge).
- Modèle choisi dans les réglages (`MODELS`, défaut Sonnet 5.5).
- Sans clé : l'app reste utilisable (stats, check-up, mémoire, Bourse d'Énergie calculée localement).
- Évolution prévue : proxy léger (Cloudflare Worker, déjà utilisé pour les notifications) si l'app est partagée plus largement ; seule `claude()` est à modifier.

### 3.2 Multi-utilisateur
- Prénom / pseudo en variable (`S.settings.pseudo`, `defiPseudo()`), aucun prénom codé en dur (« Minimum Effective {prénom} »).
- Chaque proche a son propre appareil, son stockage, son compte Strava (lien d'invitation `#invite=`) et sa propre clé API.

---

## 4. Mémoire Foulée (v12.1)

Stockée dans **`S.mem`** (tableau, synchronisé ; suppression = tombstone `S.del.mem`). Choisi plutôt qu'IndexedDB pour profiter de la synchro chiffrée existante. 300 entrées max.

```json
{
  "id": "m…",
  "type": "episodic | semantic | decision | hypothesis | sensation | lesson",
  "ep": "known | inferred | envisaged",
  "c": "texte court, une idée par entrée (280 car. max)",
  "src": "user | ai | checkin | strava | debrief",
  "conf": 0.0,
  "st": "active | confirmed | refuted | archived",
  "tags": [],
  "at": 0, "up": 0
}
```

Règles :
- `known` = observé/enregistré, `inferred` = déduit, `envisaged` = hypothèse.
- Une proposition de l'IA marquée `known` pour autre chose qu'un moment (`episodic`) est rétrogradée en `inferred`.
- Rien n'entre en mémoire sans l'accord de l'utilisateur : l'IA **propose** (bloc `<memoire>`), l'utilisateur **retient** ou **ignore**.
- Hypothèse confirmée par l'utilisateur → `st: confirmed`, `ep: inferred` ; réfutée → `st: refuted`, gardée (mémoire décisionnelle), jamais supprimée automatiquement.
- Écran **« Ce que Foulée sait de moi »** (`openMem`) : groupes Sait / Déduit / Envisage, filtres par type, corriger, confirmer, réfuter, supprimer, ajouter, export JSON (sans clé API).
- Les 40 entrées les plus récentes sont envoyées au coach (`memoire_foulee` dans `coachContext`).

---

## 5. Identité visuelle & splash « Precision Pulse » (v12.1)

- Fond `#0D0D0E` → `#141416`, halo radial `#E06A3B` / `#D9531E`.
- Profil altimétrique qui **monte vers un sommet**, trait en dégradé `#D9531E` → `#E06A3B` → `#F6A36F`, remplissage dégradé.
- 0–0,8 s tracé ; 0,8–1,2 s la bille blanche file jusqu'au sommet puis pulse (halo) ; 1,2–1,5 s « FOULÉE » (É `#E06A3B`) et « PERSONAL SPORTS INTELLIGENCE » en fondu montant ; retrait à 1,5 s (`splashOff`), toucher pour passer.
- `prefers-reduced-motion` : image fixe, retrait à 0,3 s. Appli installée (`#splash.pre`) : trace déjà dessinée.
- À faire : régénérer les 18 écrans de lancement iOS (`splash/launch-*.png`) avec le nouveau tracé.

---

## 6. Phasage

### PHASE 1 — Intelligence Foundation — **livrée en v12.1**

| Livrable | Implémentation |
|---|---|
| Splash Precision Pulse | §5 |
| Check-in quotidien | Check-up du matin existant + stress de vie et motivation (chips 0–3, < 15 s) |
| Mémoire v1 | §4 |
| Savoir / Déduire / Envisager | Le coach préfixe ses affirmations par `[SAVOIR]`, `[DÉDUIRE]`, `[ENVISAGER]` ; `md()` les rend en badges (plein sauge / contour orange / pointillé gris) ; retirés à la lecture vocale. Mêmes badges dans la mémoire et les fiches « Pourquoi ? ». |
| « Pourquoi ? » | Coach : bouton sous la dernière réponse → demande structurée (faits, contexte de vie, hypothèse + confiance, contre-exemples, raisonnement). Brief du matin et Bourse d'Énergie : fiche locale sans IA (`openWhy`). |
| Bourse d'Énergie v1 | Ci-dessous. |
| Appel Foulée AI | §3.1 (existant) ; règles « Intelligence Foulée » ajoutées au prompt du chat (`FOULEE_SYS`). |

**Bourse d'Énergie v1** (`enData`, carte en tête de « Ta journée », fiche `openEnergy`, entrée Ton espace)
- Calculée seulement s'il y a un check-up du jour.
- Score = 70 + points (constante `EN_W`, modifiable) :
  - nuit : < 6 h −15, < 7 h −7, ≥ 8 h +5 ; qualité 1 → −8, 2 → −3, 4 → +3 ;
  - stress de vie : calme +5, normal 0, chargé −10, sous pression −20 (non renseigné = normal, marqué « envisagé ») ;
  - énergie : épuisé −15, bof −6, bien +2, en forme +8 ;
  - courbatures marquées −4, fortes −8 ;
  - charge 7 j / moyenne 28 j : < 0,8 +5, > 1,3 −10, > 1,5 −20 ; séance exigeante la veille −5.
- Niveaux : ≥ 65 « Marge », ≥ 40 « Équilibre », sinon « Tendu ». Barre « Vie / Sport » = part des points perdus de chaque côté. Une phrase de conseil selon le niveau et le côté qui pèse le plus. Libellé « estimation ».
- Envoyée au coach (`bourse_energie`) avec le check-up du jour (`checkup_du_jour`).

### PHASE 2 — Learning & Emotion — **livrée en v12.2**

| Livrable | Implémentation |
|---|---|
| Débrief à chaud | Carte sur Aujourd'hui pendant 6 h après une séance cochée, une course guidée ou une sortie Strava non rattachée. Fiche : émotion (Libérateur, Flow, Fier, Serein, Lourd, Usant, Doute, Frustré), victoires déclarées, quelques mots (dictée), « Retenir ce moment » → mémoire `sensation` (SAVOIR). |
| Mémoire des sensations | Les débriefs alimentent la chronique, les victoires et le contexte du coach (`debriefs_recents`). |
| Narrative Engine | Chronique de la semaine : version locale toujours disponible + rédaction par Foulée (120–170 mots, n'invente rien, peut proposer une leçon à retenir). Carte du dimanche 15 h au mardi, archives semaine par semaine, lecture vocale. |
| Boussole Ego vs Body | Corps (énergie, courbatures, douleur, nuit, FC au réveil, charge) face à l'envie (motivation du check-up). Ego → séance Flow proposée (sortie au feeling 30–40 min ou circuit express 15 min) ; Body → allègement proposé ; Pourquoi ? détaillé. |
| Victoires invisibles | Détection locale : y aller malgré une envie au plus bas, facile vraiment facile, chaleur / froid, séance laissée de côté ou allégée, jour tendu respecté, 7 check-ups d'affilée, 5 nuits ≥ 7 h, victoires déclarées au débrief. Une notification au plus par jour. |

### PHASE 3 — Prediction & Adaptation
Digital Twin (capacités estimées avec intervalle de confiance), inertie d'adaptation (fourchette, pas « jour exact »), What If, adaptation météo, Terrain Feel DNA (estimation), détecteur d'opportunités.

### PHASE 4 — Coaching & Regulation
Mission du jour, coach qui négocie (base : `openNego`), Rewrite My Week, allure inconsciente (hypothèse), Ghost Trajectory, Pre-Injury Radar (base : `riskData`, signaux §2).

### PHASE 5 — Personal Intelligence
Discovery / Surprends-moi, Sports Detective, Athlete Genome, Year in Foulée (base : `openWrapped`), méta-intelligence.

Chaque phase reçoit ses critères d'acceptation **avant** développement.

---

## 7. Savoir se taire
- Maximum 1 message proactif par jour, jamais pendant une activité en cours, rien entre 22 h et 7 h.
- Proactif seulement si : charge anormale, hypothèse confirmée/réfutée, victoire invisible, course à J−7/J−1.
- Le coach ne propose de mémoire que si c'est nouveau ; pas de bloc sinon.

## 8. Garde-fous santé
- Douleur forte au check-up → courses du jour et du lendemain remplacées (existant, `chkO`).
- Aucun diagnostic ; prédictions en tendances et fourchettes ; nutrition : déficit modéré uniquement.

## 9. Méthode de travail Claude Code
1. Lire `REPRISE.md`, puis l'existant ; résumer ce qui sera modifié.
2. Patch Python par remplacements exacts, petites étapes.
3. Tests Playwright (`python3 tests/run.py`, zéro erreur JS), nouveau test pour chaque version.
4. Vérifier qu'aucun nom/identifiant Foulée n'a changé et qu'aucune donnée n'est perdue.
5. Publier selon `REPRISE.md` (main + `codex/market-monitor`), mettre à jour `REPRISE.md` et ce document.

**FOULÉE RESTE FOULÉE.**
