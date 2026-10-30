#!/bin/bash
# Installe (ou réinstalle) la dernière version publiée d'Aura.
# Usage : curl -fsSL https://raw.githubusercontent.com/TAF-ROISSY/AI/main/aura/install.sh | bash
set -e
echo "✦ Recherche de la dernière version d'Aura…"
URL=$(curl -fsSL "https://api.github.com/repos/TAF-ROISSY/AI/releases?per_page=40" \
  | /usr/bin/python3 -c '
import json, sys
def v(t): return [int(x) for x in t[len("aura-v"):].split(".") if x.isdigit()]
rels = [r for r in json.load(sys.stdin) if r["tag_name"].startswith("aura-v") and not r["draft"] and r["assets"]]
r = max(rels, key=lambda r: v(r["tag_name"]))
print(r["assets"][0]["browser_download_url"])')
echo "✦ Téléchargement : $URL"
curl -fL --progress-bar -o /tmp/Aura.zip "$URL"
pkill -x Aura 2>/dev/null && sleep 1 || true
# Une ancienne installation peut appartenir au compte système : on passe alors par sudo
if ! rm -rf /Applications/Aura.app 2>/dev/null || [ -e /Applications/Aura.app ]; then
  echo "✦ Mot de passe du Mac demandé pour remplacer l'ancienne version :"
  sudo rm -rf /Applications/Aura.app < /dev/tty
fi
ditto -x -k /tmp/Aura.zip /Applications 2>/dev/null || sudo ditto -x -k /tmp/Aura.zip /Applications < /dev/tty
# L'app doit t'appartenir pour que les mises à jour intégrées marchent sans mot de passe
[ -O /Applications/Aura.app ] || sudo chown -R "$(whoami)" /Applications/Aura.app < /dev/tty
xattr -dr com.apple.quarantine /Applications/Aura.app 2>/dev/null || true
echo "✅ Aura installée : $(defaults read /Applications/Aura.app/Contents/Info CFBundleShortVersionString)"
open /Applications/Aura.app
