#!/bin/bash
# TAF WAREHOUSE — construit l'image SUR le serveur à partir d'un commit GitHub précis, puis la met en service.
# Usage (root, via AWS Systems Manager) : build-on-server.sh <sha-commit-complet> <version>
# Aucun identifiant n'est nécessaire : le dépôt est téléchargé en lecture publique.
# La mise en service et le contrôle de santé sont ceux de taf-warehouse-deploy.
set -euo pipefail
SHA="$1"; VERSION="$2"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "SHA de commit complet (40 caractères) attendu"; exit 2; }
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Version x.y.z attendue"; exit 2; }
REPO=$(grep -oE 'REPO="[^"]+"' /usr/local/bin/taf-warehouse-deploy | cut -d'"' -f2)
SRC=/opt/taf-warehouse/src/$SHA
if [ ! -d "$SRC" ]; then
  mkdir -p "$SRC"
  curl -fsSL "https://codeload.github.com/taf-roissy/AI/tar.gz/$SHA" | tar -xz --strip-components=2 -C "$SRC" "AI-$SHA/taf-warehouse"
fi
grep -q "version='$VERSION'" "$SRC/app/server.py" || { echo "La version $VERSION ne correspond pas au commit $SHA"; exit 3; }
# Sans BuildKit (Docker d'Amazon Linux), l'option de certificat de proxy, inutile sur AWS, est retirée.
DOCKERFILE="$SRC/Dockerfile"
if ! docker buildx version >/dev/null 2>&1; then
  sed -e 's/^RUN --mount=type=secret.*$/RUN \\/' -e 's/^    if \[ -f \/run\/secrets\/ca \].*$/    true; \\/' "$SRC/Dockerfile" > "$SRC/Dockerfile.server"
  DOCKERFILE="$SRC/Dockerfile.server"
fi
docker build -f "$DOCKERFILE" -t "$REPO:$VERSION" --label "org.opencontainers.image.revision=$SHA" "$SRC"
# Une image construite localement est utilisée telle quelle ; sinon, elle est tirée d'ECR.
sed -i 's|^docker pull "\$REPO:\$TAG"$|docker image inspect "$REPO:$TAG" >/dev/null 2>\&1 \|\| docker pull "$REPO:$TAG"|' /usr/local/bin/taf-warehouse-deploy
/usr/local/bin/taf-warehouse-deploy "$VERSION"
