#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_NAME="audio-hub"
VERSION="${VERSION:-${DEB_VERSION:-1.0.0}}"
ARCH="all"
BUILD_DIR="${ROOT_DIR}/build"
STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/audio-hub-deb.XXXXXX")"
DEB_PATH="${BUILD_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
trap 'rm -rf -- "$STAGING_DIR"' EXIT

# Vérifications préalables
if [[ ! -f "${ROOT_DIR}/audio-hub.py" ]]; then
    echo "❌ audio-hub.py introuvable" >&2
    exit 1
fi

if [[ ! -f "${ROOT_DIR}/data/audio-hub.desktop" ]]; then
    echo "❌ Fichier desktop introuvable" >&2
    exit 1
fi

if [[ ! -f "${ROOT_DIR}/data/icons/audio-hub.svg" ]]; then
    echo "❌ Icône introuvable" >&2
    exit 1
fi

# Nettoyage et préparation
rm -f -- "${DEB_PATH}"
mkdir -p "${BUILD_DIR}"

# Préparation de l'arborescence .deb
install -d -m 0755 \
    "${STAGING_DIR}/DEBIAN" \
    "${STAGING_DIR}/usr/bin" \
    "${STAGING_DIR}/usr/share/${PACKAGE_NAME}" \
    "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/audiohub" \
    "${STAGING_DIR}/usr/share/applications" \
    "${STAGING_DIR}/usr/share/metainfo" \
    "${STAGING_DIR}/usr/share/icons/hicolor/scalable/apps" \
    "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps" \
    "${STAGING_DIR}/usr/share/icons/hicolor/128x128/apps" \
    "${STAGING_DIR}/usr/share/icons/hicolor/64x64/apps" \
    "${STAGING_DIR}/usr/share/icons/hicolor/48x48/apps" \
    "${STAGING_DIR}/usr/share/icons/hicolor/32x32/apps"

# Installation des fichiers
echo "==> Copie des fichiers..."
install -m 755 "${ROOT_DIR}/launch.sh" "${STAGING_DIR}/usr/bin/${PACKAGE_NAME}"
install -m 644 "${ROOT_DIR}/audio-hub.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/"
install -m 644 "${ROOT_DIR}/audio_device_classifier.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/"
install -m 644 "${ROOT_DIR}/audiohub/__init__.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/audiohub/"
install -m 644 "${ROOT_DIR}/audiohub/browser_streams.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/audiohub/"
install -m 644 "${ROOT_DIR}/audiohub/gtk_app.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/audiohub/"
install -m 644 "${ROOT_DIR}/audiohub/models.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/audiohub/"
install -m 644 "${ROOT_DIR}/audiohub/paths.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/audiohub/"
install -m 644 "${ROOT_DIR}/audiohub/pipewire.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/audiohub/"
install -m 644 "${ROOT_DIR}/tray_helper.py" "${STAGING_DIR}/usr/share/${PACKAGE_NAME}/"
install -m 644 "${ROOT_DIR}/data/audio-hub.desktop" "${STAGING_DIR}/usr/share/applications/"
install -m 644 "${ROOT_DIR}/data/com.audiohub.audiohub.metainfo.xml" \
    "${STAGING_DIR}/usr/share/metainfo/"
install -m 644 "${ROOT_DIR}/data/icons/audio-hub.svg" \
    "${STAGING_DIR}/usr/share/icons/hicolor/scalable/apps/audio-hub.svg"

# Copier les icônes de différentes tailles
for size in 256x256 128x128 64x64 48x48 32x32; do
    if [[ -f "${ROOT_DIR}/data/icons/hicolor/${size}/apps/audio-hub.svg" ]]; then
        install -m 644 "${ROOT_DIR}/data/icons/hicolor/${size}/apps/audio-hub.svg" \
            "${STAGING_DIR}/usr/share/icons/hicolor/${size}/apps/"
    fi
done

# Fichier de contrôle
cat > "${STAGING_DIR}/DEBIAN/control" <<EOF
Package: ${PACKAGE_NAME}
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: AudioHub <local>
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-4.0, gir1.2-adwaita-1, pipewire, wireplumber
Description: Application AudioHub — Routage PipeWire
 Interface GTK4 complète pour routage audio avancé avec PipeWire.
 .
 Permet de router dynamiquement chaque flux applicatif vers un ou plusieurs
 périphériques audio, de créer des profils de routage persistants et de
 contrôler volumes et sources directement depuis une interface graphique.
EOF

# Script postinst
cat > "${STAGING_DIR}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
# Mettre à jour le cache des applications desktop
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database /usr/share/applications || true
fi
# Mettre à jour le cache des icônes
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
fi
EOF
chmod 755 "${STAGING_DIR}/DEBIAN/postinst"

# Créer le .deb
echo "==> Construction du paquet..."
dpkg-deb --build --root-owner-group "${STAGING_DIR}" "${DEB_PATH}"

echo "✅ Paquet construit : ${DEB_PATH}"
echo ""
echo "Installation :"
echo "  sudo apt install ${DEB_PATH}"
echo ""
echo "Utilisation :"
echo "  audio-hub"
