#!/bin/bash
# Build script for Flathub submission
# Requires: flatpak, org.flatpak.Builder installed

set -euo pipefail

MANIFEST="io.github.linux-audio-manager.json"
APP_ID="io.github.linux-audio-manager"
BUILD_DIR="build-flatpak"

echo "Building Flatpak for ${APP_ID}..."

# Install org.flatpak.Builder if needed
if ! flatpak list --app | grep -q org.flatpak.Builder; then
    echo "Installing org.flatpak.Builder..."
    flatpak install -y flathub org.flatpak.Builder
fi

# Build the application
mkdir -p "${BUILD_DIR}"
flatpak run --command=flathub-build org.flatpak.Builder \
    --install \
    "${MANIFEST}"

echo "✓ Flatpak build complete"
echo ""
echo "To run locally:"
echo "  flatpak run ${APP_ID}"
echo ""
echo "To run linter:"
echo "  flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest ${MANIFEST}"
echo "  flatpak run --command=flatpak-builder-lint org.flatpak.Builder repo ${BUILD_DIR}"
