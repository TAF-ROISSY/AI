#!/usr/bin/env bash
# Construit les exécutables Windows de TAF WAREHOUSE (depuis Linux ou macOS, Go ≥ 1.22 et Python 3 requis).
#   dist/TAF-WAREHOUSE-Windows.zip        : lanceur de l'application en ligne + variante « poste quai »
#   dist/TAF-WAREHOUSE-Local-Windows.zip  : version locale autonome (Python embarqué, base SQLite sur le PC)
set -euo pipefail
cd "$(dirname "$0")"
ROOT=$(cd .. && pwd)
DIST=${DIST:-$PWD/dist}
PYVER=${PYVER:-3.12.10}
PIP=${PIP:-python3 -m pip}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$DIST"

# 1. Icône et ressources Windows
python3 - "$ROOT/web/icon-512.png" "$WORK/taf.ico" <<'PY'
import sys
from PIL import Image
Image.open(sys.argv[1]).convert('RGBA').save(sys.argv[2], sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
PY
command -v rsrc >/dev/null || go install github.com/akavel/rsrc@v0.10.2
RSRC=$(command -v rsrc || echo "$(go env GOPATH)/bin/rsrc")
"$RSRC" -ico "$WORK/taf.ico" -arch amd64 -o launcher/rsrc_windows_amd64.syso

build() { (cd launcher && GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-H windowsgui -s -w -X main.mode=$1" -o "$2"); }

# 2. Lanceur de l'application en ligne
ONLINE="$WORK/TAF-WAREHOUSE"
mkdir -p "$ONLINE"
build online "$ONLINE/TAF WAREHOUSE.exe"
build quai "$ONLINE/TAF WAREHOUSE - Poste quai.exe"
cp LISEZ-MOI-EN-LIGNE.txt "$ONLINE/LISEZ-MOI.txt"
(cd "$WORK" && rm -f "$DIST/TAF-WAREHOUSE-Windows.zip" && zip -qr "$DIST/TAF-WAREHOUSE-Windows.zip" TAF-WAREHOUSE)

# 3. Version locale autonome
LOCAL="$WORK/TAF-WAREHOUSE-Local"
mkdir -p "$LOCAL/python"
curl -fsSL -o "$WORK/python.nupkg" "https://api.nuget.org/v3-flatcontainer/python/$PYVER/python.$PYVER.nupkg"
(cd "$WORK" && unzip -q python.nupkg 'tools/*' -d pyext)
cp -r "$WORK/pyext/tools/." "$LOCAL/python/"
rm -rf "$LOCAL/python/Lib/test" "$LOCAL/python/Lib/idlelib" "$LOCAL/python/Lib/tkinter" "$LOCAL/python/Lib/turtledemo" "$LOCAL/python/include" "$LOCAL/python/libs"
$PIP install --quiet --no-compile --target "$LOCAL/python/Lib/site-packages" --platform win_amd64 --python-version "${PYVER%.*}" \
    --implementation cp --abi "cp$(echo "${PYVER%.*}" | tr -d .)" --only-binary=:all: -r requirements-windows.txt
(cd "$ROOT" && git archive HEAD app web | tar -x -C "$LOCAL")
build local "$LOCAL/TAF WAREHOUSE Local.exe"
cp LISEZ-MOI-LOCAL.txt "$LOCAL/LISEZ-MOI.txt"
(cd "$WORK" && rm -f "$DIST/TAF-WAREHOUSE-Local-Windows.zip" && zip -qr -9 "$DIST/TAF-WAREHOUSE-Local-Windows.zip" TAF-WAREHOUSE-Local)
ls -la "$DIST"
