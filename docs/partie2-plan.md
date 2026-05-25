# Partie 2 : Plan d'implémentation détaillé

## Vue d'ensemble

La Partie 2 transforme Linux Audio Manager en outil expert avec :
- **Automatisation intelligente** des routages complexes
- **Supervision fine** de l'audio avec diagnostics avancés
- **Productivité** pour utilisateurs professionnels audio

---

## 1. Routage intelligent (Priorité 🔴 Élevée)

### 1.1 Règles par application

**Problématique** : Un utilisateur veut que VLC utilise les enceintes, tandis que Discord utilise le casque USB.

**Implémentation** :
```python
# src/routing_rules.py
Rule = {
    "id": "rule_vlc_speakers",
    "app_pattern": "vlc",  # regex ou wildcard
    "target_sink": "Haut-parleurs stéréo",
    "enabled": true,
    "priority": 100,
    "conditions": [...]  # optionnel
}
```

**Fonctionnalités** :
- Correspondance flexible (regex, wildcard, PID exact)
- Activation/désactivation par clic
- Import/export JSON des règles
- Gestion des conflits par priorité

**Interface** :
- Nouvelle section "Règles d'application"
- Ajouter/éditer/supprimer des règles
- Test rapide d'une règle sur une app active

### 1.2 Règles selon le matériel

**Problématique** : Quand je branche mon casque USB, je veux que tout bascule vers le casque automatiquement.

**Implémentation** :
```python
HardwareProfile = {
    "name": "Avec casque USB",
    "conditions": {
        "required_devices": ["USB Audio Device"],
        "excluded_devices": []
    },
    "actions": {
        "set_default_sink": "USB Audio Device",
        "enable_rules": ["rule_work_headset"],
        "disable_rules": ["rule_speakers"]
    }
}
```

**Fonctionnalités** :
- Détection de hotplug (watch /dev/snd)
- Application automatique au branchement
- Fallback si appareil non trouvé
- Profils multiples activables en cascade

**Interface** :
- Section "Profils matériel"
- Prévisualisez la configuration avant activation
- Enregistrement en un clic du profil courant

### 1.3 Routage dynamique et chaînes

**Problématique** : Créer un bus virtuel pour mixer plusieurs apps, appliquer des filtres avant la sortie.

**Implémentation** :
```python
RoutingChain = [
    {"type": "input", "source": "Firefox PID:1234"},
    {"type": "filter", "kind": "eq", "preset": "enhance_voice"},
    {"type": "output", "sink": "Haut-parleurs"},
    {"type": "monitor", "sink": "Recording"}  # Parallèle
]
```

**Fonctionnalités** :
- Graphe de routage visual (drag-drop nodes)
- Support des filtres LADSPA/LV2 si disponibles
- Création de buses virtuelles via wpctl
- Duplication temps réel vers monitoring

**Interface** :
- Éditeur graphique type "patchbay"
- Aperçu en temps réel
- Sauvegarde comme chaîne réutilisable

---

## 2. Multi-périphérique avancé (Priorité 🟠 Moyenne)

### 2.1 Zones audio

**Problématique** : 3 zones (salon, chambre, bureau) avec contrôle indépendant du volume.

**Implémentation** :
```python
AudioZone = {
    "name": "Salon",
    "sinks": ["Bose Soundbar", "Ampli stéréo"],
    "volume": 80,
    "mute": false,
    "label": "Zone Salon"
}
```

**Fonctionnalités** :
- Grouper logiquement les sinks
- Volume/mute par zone
- Balancer le flux entre sinks d'une zone
- Présets de volumes (petit/moyen/cinéma)

**Interface** :
- Organisateur de zones par drag-drop
- Slider de volume par zone (regroupé)
- Nommer/iconer les zones

### 2.2 Synchronisation de latence

**Problématique** : Lire une vidéo sur 2 écrans doit rester synchronisé audio.

**Implémentation** :
```python
# Mesure la latence via test tone
def measure_latency(sink_id: int) -> float:
    # Génère bruit blanc → mesure réflexion
    # Retourne latence en ms
    pass

# Compense via delai
def apply_latency_compensation(sink_id: int, offset_ms: float):
    # Ajoute délai via wpctl (si support)
    pass
```

**Fonctionnalités** :
- Outil de mesure intégré
- Compensation automatique
- Graphe montrant synchro relative
- Sauvegarder offsets par paire

**Interface** :
- Onglet "Diagnostics" → "Sync"
- Test en 1 clic, affichage temps réel
- Ajustement slider si compensation auto insuffisante

### 2.3 Hot-plugging intelligent

**Problématique** : Débrancher un casque → basculer vers une autre sortie sans silence.

**Implémentation** :
```python
HotPlugAction = {
    "trigger": "device_removed",
    "condition": "is_default_sink",
    "fallback_sink": "Haut-parleurs intégrés",
    "fade_out_ms": 100,  # Crossfade
    "notify_user": true
}
```

**Fonctionnalités** :
- Détection événements udev/dbus
- Basculement sans coupure (crossfade 100ms)
- Notification utilisateur
- Journalisation événements
- Option : redemander l'app où rediriger

**Interface** :
- Section "Hot-plugging" en Préférences
- Config du fallback par device
- Historique des switchs

---

## 3. Fonctions audio spécialisées (Priorité 🟠 Moyenne)

### 3.1 Égaliseur paramétrique

**Problématique** : Booster les basses pour la musique, affaiblir sur Zoom.

**Implémentation** :
```python
EQPreset = {
    "name": "Bass Boost",
    "bands": [
        {"freq": 60, "gain_db": 6, "q": 0.7},
        {"freq": 250, "gain_db": 0, "q": 0.7},
        {"freq": 1000, "gain_db": -2, "q": 0.7},
        {"freq": 4000, "gain_db": 3, "q": 0.7},
    ]
}
```

**Fonctionnalités** :
- 5-31 bandes ajustables
- Presets intégrés (cinéma, musique, voix, etc.)
- Sauvegarde presets custom
- Application par app ou globale
- Visualisation courbe de réponse

**Interface** :
- Slider par bande (drag horizontal)
- Courbe de réponse live
- Dropdown presets
- A/B comparaison (avant/après)

### 3.2 Normalisation dynamique

**Problématique** : Zoom trop bas, musique trop fort → normaliser automatiquement.

**Implémentation** :
```python
DynamicNorm = {
    "enabled": true,
    "target_level_db": -20,  # LUFS target
    "attack_ms": 10,
    "release_ms": 1000,
    "max_gain_db": 12,
    "per_app": false  # ou par app
}
```

**Fonctionnalités** :
- Leveling multiband (FFT-based)
- Paramètres attack/release ajustables
- Par flux ou global
- Affichage du headroom courant

**Interface** :
- Toggle simple + sliders avancés
- VU-meter avec target level
- Graph du gain appliqué en temps réel

### 3.3 Compression et expansion

**Problématique** : Voix trop variable, réduire dynamique (compresser) ou augmenter contraste (expander).

**Implémentation** :
```python
Compressor = {
    "ratio": 4.0,  # 4:1
    "threshold_db": -20,
    "attack_ms": 5,
    "release_ms": 100,
    "makeup_gain_db": 4
}
```

**Fonctionnalités** :
- Ratio/threshold/attack/release ajustables
- Makeup gain auto
- Visualisation gain reduction meter
- Chaîner avec EQ

**Interface** :
- Sliders ou input numérique
- Graphe de transfer (input → output)
- Gain reduction meter en temps réel

---

## 4. Outils de productivité (Priorité 🟢 Basse)

### 4.1 Presets et scénarios

**Problématique** : "Réunion Zoom" doit configurer micros, sortie casque, mute bruit.

**Implémentation** :
```python
Scenario = {
    "name": "Réunion Zoom",
    "description": "Casque USB, micro XLR, désactiver musique",
    "steps": [
        {"action": "set_default_sink", "value": "USB Headset"},
        {"action": "select_input_device", "value": "Presonus XLR"},
        {"action": "mute_app", "app": "Spotify"},
        {"action": "apply_preset", "eq": "Enhance Voice"},
        {"action": "normalize", "enabled": true}
    ]
}
```

**Fonctionnalités** :
- Création de scénarios custom
- Activation en 1 clic
- Export/import
- Déclenchement automatique par heure/app
- Rollback au profil précédent

**Interface** :
- Gestionnaire de scénarios
- Éditeur drag-drop des étapes
- Test en live
- Boutons de démarrage rapide

### 4.2 Raccourcis clavier

**Problématique** : Mute Zoom en Ctrl+Alt+M, basculer profil avec Win+1.

**Implémentation** :
```python
HotKey = {
    "combo": "Ctrl+Alt+M",
    "action": "toggle_mute_app",
    "target_app": "zoom.us",
    "enabled": true
}
```

**Fonctionnalités** :
- Binding clavier global (X11/Wayland)
- Actions : mute/unmute app, switch scenario, toggle zone, etc.
- Affichage en toast notification
- Éditeur graphique des bindings

**Interface** :
- Liste des raccourcis actuels
- Édition : "Appuyez sur le combo" pour capturer
- Test du binding en direct

### 4.3 Macros enchaînées

**Problématique** : "Fin de journée" → augmenter musique, arrêter enregistrement, notifier.

**Implémentation** :
```python
Macro = {
    "name": "Fin de journée",
    "triggers": ["time_19:00", "manual"],
    "actions": [
        {"delay_ms": 0, "action": "set_app_volume", "app": "Spotify", "vol": 80},
        {"delay_ms": 500, "action": "set_zone_volume", "zone": "Salon", "vol": 100},
        {"delay_ms": 0, "action": "notify", "message": "Fin de journée appliquée"}
    ]
}
```

**Fonctionnalités** :
- Enchaînement avec délais
- Triggers : temps, app, événement
- Débogage avec logs
- Sauvegarde comme modèle

**Interface** :
- Éditeur visuel timeline
- Drag-drop des actions
- Preuve d'exécution en logs
- Dry-run avant activation

---

## 5. Fiabilité et supervision (Priorité 🔴 Élevée)

### 5.1 Historique et audit

**Problématique** : Qui a changé le volume ? Quand le casque a déconnecté ?

**Implémentation** :
```python
AuditLog = {
    "timestamp": "2026-05-25T14:35:12.456Z",
    "event_type": "volume_changed",
    "actor": "user" | "rule" | "hotplug" | "macro",
    "details": {
        "node_id": 42,
        "old_value": 0.5,
        "new_value": 0.8,
        "reason": "user_interaction" | "auto_normalize"
    }
}
```

**Fonctionnalités** :
- Journal complet (fichier ou SQLite)
- Export CSV/JSON
- Filtrage par type/date/acteur
- 24h de rétention par défaut
- Graphe statistiques (changements/jour, apps actives)

**Interface** :
- Onglet "Historique"
- Timeline avec zoom/filter
- Graphes statistiques
- Export bouton

### 5.2 Undo/Redo

**Problématique** : "Oups, j'ai mute tout le système" → annuler.

**Implémentation** :
```python
UndoStack = [
    {"timestamp": 12:35:01, "action": "set_volume", "undo": {...}, "redo": {...}},
    {"timestamp": 12:35:05, "action": "mute_sink", "undo": {...}, "redo": {...}},
]
# Garder dernier 50
```

**Fonctionnalités** :
- Stack 50 actions (FIFO)
- Undo/redo par keystroke (Ctrl+Z/Y)
- Menu et boutons UI
- Impossible de redo après nouvelle action

**Interface** :
- Boutons Undo/Redo en haut
- Historique popup au survol
- Raccourcis clavier

### 5.3 Diagnostics et recovery

**Problématique** : Statut santé du système audio, détecter goulots/latences.

**Implémentation** :
```python
DiagnosticReport = {
    "timestamp": "...",
    "checks": [
        {"name": "PipeWire status", "status": "OK", "latency_ms": 2.5},
        {"name": "Default sink availability", "status": "OK"},
        {"name": "Mic input level", "status": "WARNING", "reason": "too low"},
        {"name": "Xruns detected", "status": "CRITICAL", "count": 12, "cause": "CPU overload"}
    ],
    "recommendations": [...]
}
```

**Fonctionnalités** :
- Auto-check toutes les 60s
- Détection Xruns (audio dropouts)
- Analyse des goulots CPU
- Suggestions d'optimisation
- Test microphone (recording → playback)

**Interface** :
- Tableau de bord "Santé audio"
- Couleurs status (🟢 OK, 🟡 WARN, 🔴 CRITICAL)
- Détails de chaque check
- "Réparer" bouton pour actions courantes

### 5.4 Sauvegarde automatique et recovery

**Problématique** : Crash du gestionnaire → récupérer l'état précédent.

**Implémentation** :
```python
# Toutes les 30s ou lors d'un changement majeur
StateSnapshot = {
    "timestamp": "...",
    "default_sink": 42,
    "sinks": [{...}, ...],
    "streams": [{...}, ...],
    "rules_active": [...],
    "scenario_active": "..."
}
# Fichier: ~/.config/linux-audio-manager/state.snapshot.json
```

**Fonctionnalités** :
- Sauvegarde delta (diff avant/après)
- Auto-restore au lancement si crash détecté
- Historique rollback (derniers 10 snapshots)
- Option ask/auto/manual restore

**Interface** :
- Toast "Récupération de crash" avec options
- Menu Édition → "Revenir à un point antérieur"
- Status indicator en bas (dernier snapshot ok)

---

## Timeline d'implémentation suggérée

### **v0.2 (1-2 mois)** : Fondations expert
- ✅ Règles par application + hardware profiles
- ✅ Historique + undo/redo simple
- ✅ Diagnostics basiques (santé PipeWire)
- ✅ Zones audio simples

### **v0.3 (2-3 mois)** : Audio avancé
- ✅ Égaliseur 5 bandes
- ✅ Normalisation dynamique
- ✅ Presets et scénarios
- ✅ Hot-plugging robuste

### **v0.4 (3+ mois)** : Expert professionnel
- ✅ Compression/expansion
- ✅ Routage graphique avancé
- ✅ Raccourcis globaux
- ✅ Macros enchaînées
- ✅ Synchronisation latence

### **v1.0+** : Stabilisation + ecosystem
- Intégration DBus complète
- Support LADSPA/LV2 plugins
- Exportation projets Ardour
- Monitoring temps réel
- Intégration system tray

---

## Dépendances et contraintes

| Fonctionnalité | Dépendance | Notes |
|---|---|---|
| Règles/profiles | Aucune | Pure Python |
| Presets JSON | json stdlib | ✅ |
| Historique | sqlite3 stdlib | Alternatif JSON |
| Diagnostics Xruns | Accès /proc/asound | Nécessite privilèges |
| Raccourcis globaux | python-xlib (X11) ou Wayland proto | Optionnel, fallback simple |
| Graphe latence | numpy optionnel | Visuel basique sans |
| Équaliseur | ALSA/JACK (via subprocess) | Simulé sans, full avec |

---

## Points de décision pour l'équipe

1. **Graphe visuel du routage** : Tkinter simple vs. Qt5 vs. Web UI ?
2. **Base de données** : SQLite vs. JSON files ?
3. **Équaliseur** : Implémentation maison vs. PulseAudio dssi vs. JACK ?
4. **Macros** : Langage simple DSL vs. Python embedded vs. YAML ?
5. **Intégration système** : D-Bus vs. fichiers de config vs. socket ?
