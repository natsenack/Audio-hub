# Changelog

All notable changes to this project will be documented in this file.

This project follows Keep a Changelog and Semantic Versioning.

## [Unreleased]

### Added

- **Routage granulaire par stream (v0.1.1 - NOUVEAU)** :
  - ✅ **Sélection par application** : Pour chaque stream, checkboxes pour choisir ses sinks spécifiques.
  - ✅ **Application intelligente** : Détecte automatiquement les changements et crée/supprime les liens.
  - ✅ **Pré-sélection** : Les sinks actuels sont automatiquement cochés grâce à `get_stream_links()`.
  - ✅ **Feedback granulaire** : Affiche `+2 lien(s), -1 lien(s)` pour chaque changement.
  - ✅ **Interface unifiée** : Implémentation identique pour GTK4/Adwaita et GTK3.
  - Documentation : [docs/STREAM-ROUTING.md](docs/STREAM-ROUTING.md).

- **Améliorations Multi-Sortie (v0.1.x)** :
  - ✅ **Sélection des sinks** : Checkboxes pour choisir quels périphériques dupliquer.
  - ✅ **Affichage des connexions actives** : Visualisation complète des liens créés.
  - ✅ **Suppression individuelle de liens** : Bouton [✕] sur chaque connexion ou "Effacer tous".
  - ✅ **Persistance des préférences** : Mémorisation des derniers sinks sélectionnés.
  - ✅ **Nouveau contrôle audio** : `disconnect_link()` et `get_stream_links()`.
  - ✅ **Meilleur feedback UX** : Icônes statut (✅ ❌ ⚠️ ℹ️), flèches routage.
  - ✅ **Compatibility GTK3 & Adwaita** : Même UI avancée sur les deux frameworks.
  - Documentation complète : [docs/MULTI-OUTPUT-IMPROVEMENTS.md](docs/MULTI-OUTPUT-IMPROVEMENTS.md).

- **Partie 1 complétée (Version 0.1.0)** :
  1. **Interface GNOME** : Fenêtre GTK4/libadwaita avec fallback GTK3.
  2. **Contrôle audio simple** : Volume par app/périphérique, liste des apps actives, mute.
  3. **Routage de base** : Changement rapide de sortie par défaut via interface.
  4. **Multi-sortie avancée** : Sélection sinks, visualisation liens, suppression fine.
  5. **Persistance enrichie** : Sauvegarde sinks préférés + état routage + sink défaut.

### Backend PipeWire (autonome)

- `pw-dump` pour lire l'état des flux et périphériques.
- `wpctl` pour modifier volumes, mute, créer liens, changer sortie par défaut.
- Nouvelles fonctions audio :
  - `get_audio_links()` : liste les connexions audio actuelles.
  - `get_default_sink()` : récupère la sortie par défaut.
  - `set_default_sink()` : change la sortie par défaut.
  - `duplicate_stream_to_sink()` : crée une connexion duplication.
  - `get_active_sink_ids()` : liste les sinks disponibles.
  - **NEW** `disconnect_link()` : supprime une connexion (lien).
  - **NEW** `get_stream_links()` : liste tous les liens d'un flux.

### Configuration (Persistance)

- Nouveau module `src/config.py` pour gérer la sauvegarde/restauration.
- Fichier de config : `~/.config/linux-audio-manager/settings.json`.
- Sauvegarde automatique du dernier sink utilisé et état du routage.
- Restauration au démarrage du sink par défaut précédent.
- **NEW** Persistance des sinks préférés pour multi-sortie :
  - `get_preferred_sinks()` : charge les sinks préférés.
  - `save_preferred_sinks()` : mémorise les choix utilisateur.

### Interface (Adwaita + GTK3)

- **Section "Routage de base"** : Affiche tous les sinks, permet de changer le défaut.
- **Section "Multi-sortie avancée"** :
  - Checkboxes pour sélectionner les sinks désirés.
  - Boutons "Dupliquer sélection" et "Effacer tous les liens".
  - Affichage en temps réel des connexions actives.
  - Suppression individuelle de liens via [✕].
- Statut message avec icônes (✅ ❌ ⚠️ ℹ️) et feedback détaillé.

### Documentation

- Roadmap mise à jour avec v0.1.0 marquée comme complétée.
- Jalons révisés pour v0.2+ (multi-sink avancé, règles auto, EQ).

## [0.1.0] - 2026-05-25

### Added

- Initial project structure and documentation.