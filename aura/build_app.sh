#!/bin/bash
# Compile Aura et fabrique build/Aura.app (+ build/Aura.zip).
# Variables optionnelles :
#   VERSION=2.2.0        numéro affiché dans l'app (sinon lu dans le fichier VERSION)
#   ARCHS="arm64 x86_64" architectures (sinon celle du Mac)
set -euo pipefail
cd "$(dirname "$0")"

VERSION="${VERSION:-$(cat VERSION 2>/dev/null || echo 0.0.0)}"
ARCHS="${ARCHS:-$(uname -m)}"
BUILD_NUMBER="${BUILD_NUMBER:-$(date +%Y%m%d%H%M)}"
APP="build/Aura.app"
SDK="$(xcrun --show-sdk-path --sdk macosx)"

FICHIERS=()
while IFS= read -r -d '' f; do FICHIERS+=("$f"); done < <(find Sources -name '*.swift' -print0)

mkdir -p build
BINS=()
for A in $ARCHS; do
    echo "▶︎ Compilation $A (version $VERSION)…"
    xcrun swiftc -O -parse-as-library -swift-version 5 -suppress-warnings \
        -target "$A-apple-macosx14.0" -sdk "$SDK" -module-name Aura \
        "${FICHIERS[@]}" -o "build/Aura-$A" || { echo "ECHEC_SWIFTC arch=$A code=$?"; exit 1; }
    BINS+=("build/Aura-$A")
done

echo "▶︎ Assemblage de ${APP}…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
if [ "${#BINS[@]}" -gt 1 ]; then
    lipo -create "${BINS[@]}" -output "$APP/Contents/MacOS/Aura"
else
    cp "${BINS[0]}" "$APP/Contents/MacOS/Aura"
fi
iconutil -c icns Resources/AppIcon.iconset -o "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Aura</string>
  <key>CFBundleDisplayName</key><string>Aura</string>
  <key>CFBundleIdentifier</key><string>fr.christophe.aura</string>
  <key>CFBundleExecutable</key><string>Aura</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$BUILD_NUMBER</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.utilities</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppleEventsUsageDescription</key>
  <string>Aura en a besoin pour gérer les apps ouvertes au démarrage et lancer les tâches de maintenance.</string>
</dict>
</plist>
PLIST

echo "▶︎ Signature locale…"
codesign --force --deep --sign - "$APP"

echo "▶︎ Archive de distribution…"
rm -f build/Aura.zip
ditto -c -k --keepParent "$APP" build/Aura.zip

echo "✅ $APP ($VERSION, $ARCHS) et build/Aura.zip prêts"
