#!/usr/bin/env bash
# Commandes rapides pour soumission Flathub
# Copier-coller les étapes numérotées

echo "=== QUICK COMMANDS FOR FLATHUB SUBMISSION ==="
echo ""
echo "📋 ÉTAPE 1 : Préparer GitHub repo"
echo "==========================================="
cat << 'EOF'

# Depuis la racine du projet
cd "/mnt/wwn-0x5000000000002733-part2/1. projet vscode/linux audio manager"

# Initialiser git
git init
git add .
git commit -m "Initial commit: Linux Audio Manager v0.1.0"

# Créer tag
git tag -a v0.1.0 -m "v0.1.0 - Initial stable release"

# Pousser vers GitHub (remplacer yourusername)
git remote add origin https://github.com/yourusername/linux-audio-manager.git
git branch -M main
git push -u origin main
git push origin v0.1.0

EOF

echo ""
echo "✅ Vérification avant soumission"
echo "================================="
cat << 'EOF'

# Lancer la vérification complète
./prepare-submission.sh

# Vérifier que TOUS les ✅ s'affichent

EOF

echo ""
echo "📋 ÉTAPE 2 : Soumettre issue Flathub"
echo "====================================="
cat << 'EOF'

# URL pour créer l'issue :
https://github.com/flathub/flathub/issues/new

# Template : "New application"
# App name: Linux Audio Manager
# App ID: io.github.linux-audio-manager
# Repository: https://github.com/yourusername/linux-audio-manager.git
# Maintainer: @yourusername
# License: GPL-3.0-or-later

EOF

echo ""
echo "📋 ÉTAPE 3 : Après création repo Flathub"
echo "=========================================="
cat << 'EOF'

# Attendre que Flathub crée le repo (24h)
# Puis cloner et pousser le manifest :

cd /tmp
git clone https://github.com/flathub/io.github.linux-audio-manager.git flathub-repo
cd flathub-repo

# Copier le manifest
cp /mnt/wwn-0x5000000000002733-part2/1.*audio*/io.github.linux-audio-manager.yml .

# Pousser
git add io.github.linux-audio-manager.yml
git commit -m "Add Flatpak manifest for v0.1.0"
git push origin main

EOF

echo ""
echo "✅ App publiée (attendre ~2h après approbation Flathub)"
echo "========================================================"
cat << 'EOF'

# Installation par utilisateurs :
flatpak install flathub io.github.linux-audio-manager

# Lancer l'app :
flatpak run io.github.linux-audio-manager

EOF

echo ""
echo "📖 Documentation"
echo "==============="
cat << 'EOF'

Fichiers importants à lire :
- FLATHUB_SUBMISSION_READY.md ⭐ (instructions détaillées)
- GNOME_CONFORMITY_REPORT.md (audit complet)
- SUBMISSION_SUMMARY.md (résumé de tout)
- README.md (pour utilisateurs)

EOF

echo ""
echo "✅ Prêt à soumettre!"
echo ""
