# Roadmap - Linux Audio Manager

**État actuel (25 mai 2026)** : v0.1.0 ✅ **STABLE & GNOME-CONFORME** - Prêt pour Flathub

Cette roadmap est organisee en deux parties: les fonctions de base (v0.1 ✅ COMPLÉTÉE), puis les fonctions poussees et plus specifiques (v0.2+).

## Partie 1 - Fonctions de base (v0.1.0 ✅ COMPLÉTÉE)

**Objectif** : ✅ ATTEINT - Gestionnaire audio GNOME simple, fiable et testé

**Date de sortie** : 25 mai 2026
**Score GNOME conformité** : 9/10 ✅
**Statut** : Stable + Distribution Flathub

### 1. Interface GNOME initiale

- ✅ Fenetre principale GTK4/libadwaita.
- ✅ Lancement via `make`.
- ✅ Structure visuelle claire pour les tests.

### 2. Controle audio simple

- ✅ Volume global du systeme.
- ✅ Liste des logiciels actifs qui utilisent l'audio.
- ✅ Volume par logiciel actif.
- ✅ Sourdine rapide.
- ✅ Liste des peripheriques actifs.

### 3. Routage de base

- ✅ Vue des connexions audio (via `get_audio_links()`).
- ✅ Changement rapide de sortie par défaut.
- ✅ Affichage et gestion via interface Adwaita/GTK3.

### 4. Multi-sortie simple

- ✅ Lecture du meme flux sur plusieurs peripheriques (via `wpctl link`).
- ✅ Duplication avec un bouton "Dupliquer maintenant".
- ✅ Activation manuelle du mode duplication.

### 5. Persistance minimale

- ✅ Sauvegarde d'un profil utilisateur (~/.config/linux-audio-manager/settings.json).
- ✅ Restauration au demarrage du dernier sink par défaut.
- ✅ Etat du dernier routage choisi sauvegardé lors de duplication.

## Partie 2 - Fonctions poussees

**Objectif** : Transformer LAM en outil audio professionnel avec automatisation, diagnostics avancés et productivité.

**Qui ?** Producteurs audio, utilisateurs avancés, administrateurs multimédia.

**Portée** : v0.2 → v1.0+ (6+ mois)

Pour le **plan détaillé d'implémentation**, voir [partie2-plan.md](partie2-plan.md).

---

### 1. Routage intelligent 🎯

**Vision** : Les routages complexes se configurent une fois, s'appliquent automatiquement.

#### 1.1 Règles par application
- **Use case** : VLC → enceintes, Discord → casque USB
- **Fonctionnalité** :
  - Matcher par regex/wildcard/PID
  - Règles multiples avec priorité
  - Activation/désactivation sans suppression
  - Import/export JSON
- **Implémentation** : `src/routing_rules.py` + UI section "Règles d'application"
- **v0.2** ✅

#### 1.2 Profils matériel
- **Use case** : Brancher casque USB → basculer auto tous les flux
- **Fonctionnalité** :
  - Profils par composition de devices
  - Hotplug detection + auto-apply
  - Fallback si device absent
  - Cascade profiles (salon + hotplug = config spécifique)
- **Implémentation** : Monitor udev/dbus, `src/hardware_profiles.py`
- **v0.2** ✅

#### 1.3 Routage dynamique (chaînes)
- **Use case** : Firefox → EQ → Compression → 2x sortie (casque + recording)
- **Fonctionnalité** :
  - Graphe visuel (patchbay-like)
  - Chaînes réutilisables
  - Buses virtuelles dynamiques
  - Support monitoring parallèle
- **Implémentation** : Graphe UI (Tkinter/Qt5), `src/routing_chains.py`
- **v0.4** 

#### 1.4 Conditions de déclenchement
- **Use case** : 18h → activer "fin de journée", 09h en semaine → "travail"
- **Fonctionnalité** :
  - Temps (heure/jour/intervalle)
  - Présence app (regex)
  - Device branchement
  - CPU load, batterie
- **Implémentation** : Event engine, `src/triggers.py`
- **v0.3**

---

### 2. Multi-périphérique avancé 🔊

**Vision** : Contrôler 3+ appareils comme un seul système cohérent.

#### 2.1 Zones audio
- **Use case** : Salon + Chambre + Bureau = 3 zones indépendantes
- **Fonctionnalité** :
  - Grouper sinks logiquement
  - Volume/mute par zone
  - Balancer flux entre sinks d'une zone
  - Presets volume (petit/moyen/cinéma)
  - Nommage/iconage zones
- **Implémentation** : `src/audio_zones.py` + UI organizer
- **v0.2** ✅

#### 2.2 Synchronisation de latence
- **Use case** : 2 écrans déphasés → rester sync (vidéo en lip-sync)
- **Fonctionnalité** :
  - Outil mesure latence (tone test)
  - Compensation automatique
  - Graphe synchro relative
  - Sauvegarde offsets par paire
- **Implémentation** : `src/latency_sync.py`, diagnostics tab
- **v0.3** 

#### 2.3 Hot-plugging intelligent
- **Use case** : Débrancher casque → crossfade vers enceintes (10ms, inaudible)
- **Fonctionnalité** :
  - Détection events udev/dbus
  - Crossfade sans silence (~100ms)
  - Fallback configurable par device
  - Notification utilisateur + logs
  - Demander/auto/silent modes
- **Implémentation** : Monitor `/dev/snd`, `src/hotplug.py`, notification manager
- **v0.3** ✅

#### 2.4 Groupes de priorité
- **Use case** : Critère (réunion) > Normal (musique) > Faible (notifications)
- **Fonctionnalité** :
  - 3-5 niveaux priorité
  - Limiter ressources par niveau
  - Preemption sur faible priorité
  - Starvation protection
- **Implémentation** : Priority queue dans audio engine
- **v0.4+**

---

### 3. Fonctions audio spécialisées 🎚️

**Vision** : Post-production simple intégrée (pas Audacity, mais utile).

#### 3.1 Égaliseur paramétrique
- **Use case** : Booster basses musique, affaiblir dans Zoom
- **Fonctionnalité** :
  - 5/10/31 bandes sélectionnables
  - Presets : Cinéma, Musique, Voix, Hip-Hop, Classique, Podcast
  - Création presets custom
  - Courbe réponse visualisée
  - A/B comparaison (avant/après)
  - Appliqué global ou par app
- **Implémentation** : `src/equalizer.py`, slider UI
- **v0.3** ✅

#### 3.2 Normalisation dynamique
- **Use case** : Zoom trop bas, Spotify trop fort → niveau constant
- **Fonctionnalité** :
  - Leveling LUFS-based (loudness target)
  - Attack/release ajustables
  - Max gain limit (prévenir clipping)
  - VU-meter temps réel
  - Mode globale ou par flux
- **Implémentation** : `src/normalizer.py`, FFT optional
- **v0.3** ✅

#### 3.3 Compression/Expansion
- **Use case** : Voix d'entrevue variable → compresser (ratio 4:1)
- **Fonctionnalité** :
  - Ratio/threshold/attack/release
  - Makeup gain automatique
  - Gain reduction meter
  - Chaîner avec EQ
  - Presets (voix, drums, bass, gentle)
- **Implémentation** : `src/compressor.py`
- **v0.4**

#### 3.4 Délai et reverb simple
- **Use case** : Effet studio léger, feedback monitoring
- **Fonctionnalité** :
  - Délai ajustable (1-1000ms)
  - Reverb simple (schroeder-like)
  - Wetness % 
  - Feedback control
- **Implémentation** : `src/effects.py` ou plugin wrapper
- **v0.4+**

#### 3.5 Visualisations
- **Latence** : Graph délai end-to-end par route
- **Spectrogramme** : Composition fréquentielle temps réel (matplotlib/gnuplot)
- **Waveform** : Affichage live du signal
- **Spectrum analyzer** : FFT avec zoom
- **Implémentation** : `src/visualization.py`, matplotlib/PIL
- **v0.4+**

---

### 4. Outils de productivité 🚀

**Vision** : Automatiser les workflows audio courants.

#### 4.1 Presets et scénarios
- **Use case** : "Réunion Zoom" = casque + mute Spotify + EQ voix + normalize
- **Fonctionnalité** :
  - Scénarios multi-étapes
  - Activation 1 clic
  - Déclenchement auto (heure, app, événement)
  - Rollback au profil précédent
  - Export/import JSON/YAML
  - Partage entre machines
- **Implémentation** : `src/scenarios.py` + UI builder
- **v0.3** ✅

#### 4.2 Raccourcis clavier globaux
- **Use case** : Ctrl+Alt+M = mute Zoom, Win+1 = profil "Travail"
- **Fonctionnalité** :
  - Binding clavier global (X11/Wayland)
  - Actions : mute app, switch scenario, toggle zone, etc.
  - Toast notification retour
  - Éditeur graphique (appuyez pour capturer combo)
  - Conflits detection
- **Implémentation** : `src/hotkeys.py` + python-xlib (X11) ou fallback simple
- **v0.3** ✅

#### 4.3 Macros enchaînées
- **Use case** : "Fin de journée" = augmenter musique → mute Zoom → notification
- **Fonctionnalité** :
  - Étapes avec délais
  - Triggers : heure, app, clavier, événement
  - Logs/debug trace
  - Dry-run avant activation
  - Sauvegarde comme modèle
  - Conditionnel (if/else)
- **Implémentation** : `src/macros.py`, simple DSL ou YAML
- **v0.4** 

#### 4.4 Intégration D-Bus
- **Use case** : Gestionnaire de fenêtres demande mute quand focus perdu
- **Fonctionnalité** :
  - Expose méthodes D-Bus (SetVolume, Mute, etc.)
  - Listen to system signals (device hotplug, power)
  - Multi-client concurrence safe
  - Secrets integration optionnel
- **Implémentation** : `src/dbus_service.py`, GDBus
- **v1.0+**

---

### 5. Fiabilité et supervision 🛡️

**Vision** : Tracer, diagnostiquer, récupérer automatiquement.

#### 5.1 Historique complet et audit
- **Use case** : "Qui a changé le volume ?" "Quand le casque s'est déconnecté ?"
- **Fonctionnalité** :
  - Journal événements (timestamp, acteur, type)
  - Filtrage par type/date/app
  - Export CSV/JSON
  - Rétention configurable (24h par défaut)
  - Graphes statistiques (changements/jour, topapps)
  - Search/grep rapide
- **Implémentation** : SQLite `~/.config/linux-audio-manager/audit.db`, `src/audit_log.py`
- **v0.2** ✅

#### 5.2 Undo/Redo
- **Use case** : "Oups, j'ai mute tout" → Ctrl+Z
- **Fonctionnalité** :
  - Stack 50 actions
  - Undo/redo via Ctrl+Z/Y + UI buttons
  - Timeline au hover
  - Sûr après nouvelle action (redo invalide)
- **Implémentation** : `src/undo_redo.py`, stack manager
- **v0.2** ✅

#### 5.3 Diagnostics et recovery
- **Use case** : Détecterbruit blanc/latence élevée/Xruns
- **Fonctionnalité** :
  - Auto-check santé (60s)
  - Détection Xruns (audio dropouts)
  - Analyse goulots (CPU/RAM/IO)
  - Test microphone (record → playback)
  - Suggestions optimisation
  - "Réparer" bouton pour fixes courants (restart daemon, etc.)
- **Implémentation** : `src/diagnostics.py`, monitoring background
- **v0.2** ✅

#### 5.4 Sauvegarde automatique et recovery
- **Use case** : Crash → relancer app, récupère état précédent
- **Fonctionnalité** :
  - Snapshot tous les 30s (ou changement majeur)
  - Auto-restore au boot si crash
  - Historique 10 derniers snapshots
  - Ask/auto/manual restore modes
  - Diff preview avant restore
- **Implémentation** : `src/state_manager.py`, snapshot files
- **v0.2** ✅

#### 5.5 Notifications desktop
- **Use case** : "Casque USB débranché !" "Latence élevée : 450ms"
- **Fonctionnalité** :
  - Events critiques (device, latence, Xruns, règle failed)
  - Actions dans notification (Retry, Ignore, Config)
  - Système d'alerte configurable
  - Sons d'alerte optionnels
- **Implémentation** : `src/notifications.py`, D-Bus org.freedesktop.Notifications
- **v0.3** ✅

---Statut | Features clés | Timeline |
|---------|--------|-----------------|----------|
| **0.1** | ✅ **COMPLÉTÉE** | Interface GNOME GTK4/libadwaita, PipeWire, routage basique, persistance, GNOME conforme | **25 mai 2026** ✅ |
| **0.2** | ⏳ **En préparation** | Règles/profils, zones audio, historique, undo/redo, diagnostics, hot-plugging | **Juillet 2026** |
| **0.3** | ⏳ **Planifié** | EQ, normalisation, scénarios, raccourcis globaux, latency sync | **Septembre 2026** |
| **0.4** | ⏳ **Planifié** | Compression, routage graphique, macros, visualisations | **Décembre 2026** |
| **1.0** | ⏳ **Stable pro** | D-Bus complet, LV2 plugins, stabilisation, doc, couverture tests | **2027+**-2026 |
| **0.2** | Règles + Fondations | Règles/profils, zones audio, historique, undo/redo, diagnostics | +1-2 mois |
| **0.3** | Audio avancé | EQ, normalisation, hot-plugging, scénarios, raccourcis | +2-3 mois |
| **0.4** | Expert pro | Compression, routage graphique, macros, latency sync | +3+ mois |
| **1.0** | Stable pro | D-Bus intégration, stabilisation, doc complète, tests couverture | +6+ mois |

---

## Matrice de dépendances & Progression

```
v0.1.0 (25 mai 2026) ✅ COMPLÉTÉE
├── ✅ Fenêtre principale GNOME GTK4/libadwaita
├── ✅ Contrôle PipeWire temps réel (pw-cli monitor)
├── ✅ Master + par-application volume/mute
├── ✅ Routage multi-sortie (wpctl)
├── ✅ Persistance (~/.config/linux-audio-manager/settings.json)
├── ✅ i18n (FR+EN)
├── ✅ GNOME conforme (9/10)
├── ✅ Paquet Flatpak
├── ✅ Paquet DEB
└── ✅ Distributions (GitHub, Flathub)

v0.2 (juillet-août 2026) ⏳ EN PRÉPARATION
├── Règles application → Triggers v0.3
├── Profils matériel (hotplug)
├── Zones audio groupées
├── Historique/Audit
├── Undo/Redo
├── Diagnostics (Xruns, latence)
└── Hot-plugging simple

v0.3 (septembre-octobre 2026) ⏳
├── EQ 5 bandes (+ v0.4: 31 bandes)
├── Normalisation dynamique (LUFS)
├── Scénarios (1 clic, multi-étapes)
├── Raccourcis globaux (Ctrl+Alt+M, etc.)
├── Hot-plugging robuste (crossfade)
└── Latency sync (mesure + compensation)

v0.4+ (Q4 2026+)
├── Compression/expansion paramétrique
├── Routage graphique (patchbay visuelle)
├── Macros enchaînées (DSL simple)
├── Visualisations (spectro, waveform, VU-meter)
└── Effects chains (delai, reverb)

v1.0 (2027+)
├── D-Bus complet (service system)
├── Plugins LV2/LADSPA
├── Export profiles Ardour/PulseEffects
├── Stabilisation robustesse
├── Documentation complète
└── Couverture tests (>80%)
```

---

## Décisions d'architecture pending

1. **UI graphique pour routage** : Tkinter ↔ PyQt5 ↔ GTK4 native ?
2. **Base données** : SQLite ↔ JSON files ↔ Hybrid ?
3. **EQ engine** : Custom ↔ ALSA dssi ↔ JACK LV2 ?
4. **Langage macros** : Simple DSL ↔ Python embedded ↔ Lua ?
5. **System integration** : D-Bus ↔ Sockets ↔ Config files ?
6. **Persistance profiles** : JSON ↔ YAML ↔ Toml ?