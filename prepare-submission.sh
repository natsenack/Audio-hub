#!/usr/bin/env bash
set -euo pipefail

# Script de préparation à la soumission Flathub
# Usage: ./prepare-submission.sh

echo "=== Linux Audio Manager - Flathub Submission Preparation ==="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Vérifier les fichiers critiques
echo "📋 Vérification des fichiers critiques..."
critical_files=(
    "LICENSE"
    "pyproject.toml"
    "README.md"
    "FLATHUB_SUBMISSION_PLAN.md"
    "GNOME_CONFORMITY_REPORT.md"
    "data/io.github.linux-audio-manager.desktop"
    "data/io.github.linux-audio-manager.metainfo.xml"
    "io.github.linux-audio-manager.yml"
    "flathub.json"
)

missing=0
for file in "${critical_files[@]}"; do
    if [[ -f "$file" ]]; then
        echo "  ✅ $file"
    else
        echo -e "  ${RED}❌ $file (MANQUANT)${NC}"
        missing=$((missing + 1))
    fi
done

if [[ $missing -gt 0 ]]; then
    echo -e "${RED}❌ $missing fichiers manquants!${NC}"
    exit 1
fi

echo ""

# 2. Vérifier la syntaxe Python
echo "🐍 Vérification syntaxe Python..."
python3 -m py_compile src/__init__.py src/main.py src/window.py src/audio.py src/config.py
if [[ $? -eq 0 ]]; then
    echo -e "  ${GREEN}✅ Syntaxe OK${NC}"
else
    echo -e "  ${RED}❌ Erreurs de syntaxe${NC}"
    exit 1
fi

echo ""

# 3. Vérifier formatage YAML manifest
echo "📄 Vérification manifest Flatpak YAML..."
if command -v yq &> /dev/null; then
    yq eval '.' io.github.linux-audio-manager.yml > /dev/null && echo -e "  ${GREEN}✅ YAML valide${NC}" || exit 1
else
    echo "  ⚠️  yq non installé (optionnel - Flathub validera)"
fi

echo ""

# 4. Vérifier licence et métadonnées
echo "📜 Vérification licence et métadonnées..."
if (grep -q "Version 3" LICENSE || grep -q "GPL-3" LICENSE) && grep -q "GPL-3.0" pyproject.toml; then
    echo -e "  ${GREEN}✅ Licence GPL-3.0 conforme${NC}"
else
    echo -e "  ${RED}❌ Licence non conforme${NC}"
    exit 1
fi

if grep -q 'io.github.linux-audio-manager' data/io.github.linux-audio-manager.desktop && \
   grep -q 'io.github.linux-audio-manager' data/io.github.linux-audio-manager.metainfo.xml; then
    echo -e "  ${GREEN}✅ App ID cohérent${NC}"
else
    echo -e "  ${RED}❌ App ID incohérent${NC}"
    exit 1
fi

echo ""

# 5. Vérifier formatage .desktop
echo "🖥️  Vérification fichier .desktop..."
if command -v desktop-file-validate &> /dev/null; then
    if desktop-file-validate data/io.github.linux-audio-manager.desktop; then
        echo -e "  ${GREEN}✅ .desktop valide${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Avertissements .desktop (non-bloquant)${NC}"
    fi
else
    echo "  ℹ️  desktop-file-validate non installé (optionnel)"
fi

echo ""

# 6. Vérifier AppStream metadata
echo "📦 Vérification AppStream metadata..."
if command -v appstream-util &> /dev/null; then
    if appstream-util validate data/io.github.linux-audio-manager.metainfo.xml > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ AppStream valide${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Avertissements AppStream (non-bloquant)${NC}"
    fi
else
    echo "  ℹ️  appstream-util non installé (optionnel)"
fi

echo ""

# 7. Vérifier git status
echo "🔄 Vérification état Git..."
if [[ -d .git ]]; then
    if git rev-parse --verify v0.1.0 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Tag v0.1.0 existe${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Tag v0.1.0 pas encore créé${NC}"
        echo "     → Créer: git tag -a v0.1.0 -m 'v0.1.0 - Initial stable release'"
        echo "     → Pousser: git push origin v0.1.0"
    fi
else
    echo "  ℹ️  Git non initialisé (vous initialiserez plus tard)"
fi

echo ""

# 8. Summary
echo "=========================================="
echo -e "${GREEN}✅ Préparation réussie!${NC}"
echo "=========================================="
echo ""
echo "📋 Prochaines étapes:"
echo "  1. Créer un repo GitHub (si pas encore fait)"
echo "  2. Pousser le code + tag v0.1.0"
echo "  3. Soumettre issue sur https://github.com/flathub/flathub"
echo "  4. Attendre création repo Flathub"
echo "  5. Pousser manifest.yml vers Flathub"
echo ""
echo "📖 Voir: FLATHUB_SUBMISSION_PLAN.md"
echo ""
