#!/usr/bin/env bash
set -euo pipefail

# Script complet de soumission Flathub
# Exécute étapes 2-4 semi-automatiquement

echo "╔════════════════════════════════════════════════════════════════════════╗"
echo "║                                                                        ║"
echo "║     LINUX AUDIO MANAGER - FLATHUB SUBMISSION AUTOMATION (Part 2-4)    ║"
echo "║                                                                        ║"
echo "╚════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_USER="${GITHUB_USER:-threeaxe}"
GITHUB_REPO="linux-audio-manager"

echo -e "${BLUE}📋 Configuration${NC}"
echo "════════════════════════════════════════════════════════════════════════"
echo "Username GitHub: $GITHUB_USER"
echo "Repo: $GITHUB_REPO"
echo "App ID: io.github.linux-audio-manager"
echo ""

# ============================================================================
# ÉTAPE 2 : Pousser vers GitHub
# ============================================================================

echo -e "${BLUE}📋 ÉTAPE 2 : Pousser vers GitHub${NC}"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "✓ Repo local créé avec tag v0.1.0"
echo ""

echo "⚠️  MANUEL : Créer le repo sur GitHub d'abord"
echo ""
echo "  1. Aller sur: https://github.com/new"
echo "  2. Créer repo 'linux-audio-manager'"
echo "  3. NE PAS initialiser avec README"
echo "  4. Cliquer 'Create repository'"
echo ""

read -p "📌 Repo GitHub créé ? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "⏸️  Création du repo GitHub requise avant de continuer"
    exit 1
fi

echo ""
echo "🚀 Pushing to GitHub..."
cd "$PROJECT_DIR"

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$GITHUB_USER/$GITHUB_REPO.git"
git branch -M main
git push -u origin main --force
git push origin v0.1.0

echo -e "${GREEN}✅ Poussé vers GitHub!${NC}"
echo "   URL: https://github.com/$GITHUB_USER/$GITHUB_REPO"
echo ""

# ============================================================================
# ÉTAPE 3 : Configurer GitHub repo
# ============================================================================

echo -e "${BLUE}📋 ÉTAPE 3 : Configurer le repo GitHub${NC}"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "✓ Code poussé vers GitHub"
echo ""

echo "⚠️  MANUEL : Configurer les metadonnées GitHub"
echo ""
echo "  1. Aller sur: https://github.com/$GITHUB_USER/$GITHUB_REPO/settings"
echo "  2. Section 'About' :"
echo "     - Description: 'A modern audio management application for Linux combining simple volume control with advanced PipeWire routing'"
echo "     - Topics: audio, pipewire, gtk, gnome, linux, volume-control"
echo "  3. License: GPL-3.0"
echo "  4. Cliquer 'Save'"
echo ""

read -p "📌 Repo GitHub configuré ? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "⏸️  Configuration du repo GitHub requise avant de continuer"
    exit 1
fi

echo ""

# ============================================================================
# ÉTAPE 4 : Créer issue Flathub
# ============================================================================

echo -e "${BLUE}📋 ÉTAPE 4 : Créer issue Flathub${NC}"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "✓ Repo GitHub configuré"
echo ""

echo "🔗 URL Flathub : https://github.com/flathub/flathub/issues/new"
echo ""

echo "⚠️  MANUEL : Créer issue Flathub"
echo ""
echo "  1. Aller sur: https://github.com/flathub/flathub/issues/new"
echo "  2. Choisir template: 'New application'"
echo "  3. Remplir le formulaire:"
echo ""
echo "     App name: Linux Audio Manager"
echo "     App ID: io.github.linux-audio-manager"
echo "     Source location: https://github.com/$GITHUB_USER/$GITHUB_REPO.git"
echo "     Does it come with scripts/binaries: No"
echo "     Maintainer: @$GITHUB_USER"
echo "     License: GNU General Public License v3.0 or later"
echo "     Link: https://github.com/$GITHUB_USER/$GITHUB_REPO"
echo ""
echo "  4. Cliquer 'Submit new issue'"
echo ""

read -p "📌 Issue Flathub créée ? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "⏸️  Création de l'issue Flathub requise avant de continuer"
    exit 1
fi

echo ""

# ============================================================================
# ÉTAPE 5 : Attendre et pousser manifest
# ============================================================================

echo -e "${BLUE}📋 ÉTAPE 5 : Attendre validation Flathub${NC}"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "⏱️  Timeline Flathub:"
echo "   - Bot crée repo auto (quelques heures)"
echo "   - Vous recevez notification"
echo "   - Repo créé à: https://github.com/flathub/io.github.linux-audio-manager"
echo ""

echo "📌 Une fois le repo créé, exécuter:"
echo ""
cat << 'MANIFEST_PUSH'
cd /tmp
git clone https://github.com/flathub/io.github.linux-audio-manager.git flathub-repo
cd flathub-repo
cp /mnt/wwn-0x5000000000002733-part2/1.*audio*/io.github.linux-audio-manager.yml .
git add io.github.linux-audio-manager.yml
git commit -m "Add Flatpak manifest for v0.1.0"
git push origin main
MANIFEST_PUSH

echo ""

# ============================================================================
# RÉSUMÉ FINAL
# ============================================================================

echo ""
echo "════════════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ SOUMISSION EN COURS!${NC}"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

echo "📊 Statut:"
echo "   ✅ Repo Git local + tag v0.1.0"
echo "   ✅ Code poussé vers GitHub"
echo "   ✅ Repo GitHub configuré"
echo "   ✅ Issue Flathub créée"
echo "   ⏳ En attente : Flathub crée repo (24h)"
echo "   ⏳ Prochaine: Pousser manifest.yml"
echo ""

echo "📚 Documentation:"
echo "   - FLATHUB_SUBMISSION_READY.md"
echo "   - GNOME_CONFORMITY_REPORT.md"
echo "   - SUBMISSION_SUMMARY.md"
echo ""

echo "🔗 Ressources:"
echo "   - GitHub: https://github.com/$GITHUB_USER/$GITHUB_REPO"
echo "   - Flathub: https://docs.flathub.org/"
echo "   - GNOME: https://developer.gnome.org/"
echo ""

echo -e "${GREEN}Merci d'avoir soumis Linux Audio Manager à Flathub!${NC}"
echo ""
