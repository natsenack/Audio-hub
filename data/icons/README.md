# AudioHub - Icons & Logos

Cet dossier contient tous les assets visuels de l'application AudioHub.

## Fichiers d'icônes

### Icônes circulaires (principales)
- **audio-hub.svg** (256x256) - Icône par défaut pour les applications
- **audio-hub-128.svg** (128x128) - Icônes pour les gestionnaires de fichiers haute résolution
- **audio-hub-64.svg** (64x64) - Icônes pour les barres de tâches et panneaux
- **audio-hub-48.svg** (48x48) - Petites icônes pour les applications
- **audio-hub-32.svg** (32x32) - Icônes minimales pour les menus et barres

### Logos
- **audio-hub-logo.svg** - Logo horizontal avec texte (pour en-têtes, présentations)
- **audio-hub-full.svg** - Icône complète avec dégradé (pour les écrans de démarrage)

## Design & Couleurs

### Palette de couleurs
- **Fond**: #1e1e1e (noir très sombre)
- **Accent primaire**: #00d4ff (cyan brillant)
- **Accent secondaire**: #00b8ff (cyan plus sombre)
- **Accent accentué**: #ff6b35 (orange coral)
- **Bordure**: #3584e4 (bleu GNOME)

### Style
- Ondes audio stylisées (représentant le routage PipeWire)
- Haut-parleur minimaliste au centre
- Deux ensembles d'ondes: cyan (flux principal) et orange (flux secondaire)
- Design épuré et moderne inspiré des design systems GNOME

## Utilisation

### Linux (GTK/GNOME)
```bash
# Installation système (copier en système)
cp audio-hub.svg /usr/share/icons/hicolor/scalable/apps/

# Ou pour l'utilisateur
mkdir -p ~/.local/share/icons/hicolor/scalable/apps/
cp audio-hub.svg ~/.local/share/icons/hicolor/scalable/apps/
```

### Variables d'environnement (GTK4)
```python
icon_directory = Path(__file__).resolve().parent / "icons"
Gtk.IconTheme.get_default().append_search_path(str(icon_directory))
```

## Formats supportés

Tous les fichiers sont en **SVG** (scalable vector graphics) pour:
- ✓ Netteté à n'importe quelle résolution
- ✓ Petits fichiers
- ✓ Facilement modifiables

## Licence

Tous les assets sont inclus dans AudioHub sous la même licence que l'application.

## Notes de design

Les ondes audio répresentent:
- **Cyan**: Le flux audio principal (PRIMARY)
- **Orange**: Les flux miroir ou secondaires (MIRROR)
- **Haut-parleur**: Le nœud de sortie PipeWire (sink)

Ce design symbolise l'essence d'AudioHub: le routage intelligente des flux audio vers plusieurs sorties.
