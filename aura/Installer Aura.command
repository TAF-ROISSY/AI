#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  Installeur tout-en-un d'Aura
#  Double-clique sur ce fichier : il s'occupe de tout.
# ─────────────────────────────────────────────────────────────
cd "$(dirname "$0")" || exit 1
LOG="$HOME/Desktop/Aura-erreurs.txt"
rm -f "$HOME/Desktop/Aura-erreurs.txt"

violet=$'\e[35m'; vert=$'\e[32m'; rouge=$'\e[31m'; gras=$'\e[1m'; fin=$'\e[0m'
etape() { echo; echo "${violet}${gras}▶︎ $1${fin}"; }
ok()    { echo "${vert}  ✔ $1${fin}"; }
erreur() {
    echo; echo "${rouge}${gras}✖ $1${fin}"
    osascript -e "display dialog \"$1\" buttons {\"OK\"} default button 1 with title \"Installation d'Aura\" with icon stop" >/dev/null 2>&1
    echo; read -n 1 -s -r -p "Appuie sur une touche pour fermer…"
    exit 1
}

clear
echo "${violet}${gras}"
echo "      ✦  A U R A  ✦"
echo "   Installation automatique"
echo "   (compilation directe, compatible outils Apple récents)"
echo "${fin}"

# 1. Version de macOS
etape "Vérification de macOS"
VERSION=$(sw_vers -productVersion)
MAJEUR=${VERSION%%.*}
[ "$MAJEUR" -ge 14 ] || erreur "Aura demande macOS 14 Sonoma ou plus récent (tu as $VERSION)."
ok "macOS $VERSION"

# 2. Outils de développement Apple
etape "Outils de compilation Apple"
if ! xcode-select -p >/dev/null 2>&1 || ! xcrun --find swiftc >/dev/null 2>&1; then
    echo "  Les outils ne sont pas installés : une fenêtre Apple va s'ouvrir."
    echo "  👉 Clique sur « Installer », puis patiente (environ 10 minutes)."
    xcode-select --install >/dev/null 2>&1
    until xcode-select -p >/dev/null 2>&1 && xcrun --find swiftc >/dev/null 2>&1; do
        sleep 10; printf "."
    done
    echo
fi
ok "Outils présents ($(swift --version 2>/dev/null | head -1 | sed 's/.*Swift version/Swift/' | cut -d' ' -f1-2))"

# 3. Compilation et fabrication de l'application (script partagé avec GitHub)
etape "Compilation d'Aura (2 à 5 minutes la première fois)"
chmod +x build_app.sh
./build_app.sh > "$LOG" 2>&1 &
PID=$!
while kill -0 "$PID" 2>/dev/null; do printf "."; sleep 3; done
wait "$PID"; STATUT=$?
echo
APP="build/Aura.app"
if [ "$STATUT" -ne 0 ] || [ ! -x "$APP/Contents/MacOS/Aura" ]; then
    open "$LOG"
    erreur "La compilation a échoué. Le détail est dans le fichier Aura-erreurs.txt sur ton Bureau : envoie-le à Claude pour correction."
fi
ok "Aura $(cat VERSION) compilée"

# 5. Installation dans Applications
etape "Installation dans Applications"
pkill -x Aura 2>/dev/null; sleep 1
DEST="/Applications/Aura.app"
if ! { rm -rf "$DEST" && ditto "$APP" "$DEST"; } 2>/dev/null; then
    echo "  Mot de passe administrateur demandé pour écrire dans Applications…"
    sudo rm -rf "$DEST" && sudo ditto "$APP" "$DEST" || erreur "Impossible de copier Aura dans Applications."
fi
xattr -dr com.apple.quarantine "$DEST" 2>/dev/null
ok "Aura installée dans Applications"

# 6. Accès complet au disque + lancement
etape "Dernière étape : l'Accès complet au disque"
open "$DEST"
sleep 2
open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
osascript <<'OSA' >/dev/null 2>&1
display dialog "Aura est installée ✨

Pour qu'elle puisse tout nettoyer, il reste une chose :

1. Dans la fenêtre Réglages qui vient de s'ouvrir, clique sur « + »
2. Choisis Aura dans le dossier Applications
3. Active l'interrupteur à côté d'Aura
4. Quitte et relance Aura

Tu peux ensuite jeter le dossier d'installation." buttons {"C'est fait !"} default button 1 with title "Installation d'Aura" with icon note
OSA

echo
echo "${vert}${gras}✅ Installation terminée. Bon nettoyage !${fin}"
rm -f "$LOG"
echo
read -n 1 -s -r -p "Appuie sur une touche pour fermer cette fenêtre…"
