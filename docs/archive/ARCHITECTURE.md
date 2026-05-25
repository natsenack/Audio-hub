# Architecture Partie 2 : Expert Audio

## Vision générale

Linux Audio Manager v0.2+ devient une **plateforme de gestion audio autonome** avec :
- **Moteur de routage intelligent** : Applique automatiquement des règles complexes
- **Supervision en temps réel** : Détecte problèmes, propose solutions
- **Écosystème extensible** : Plugins, D-Bus, intégration système
- **UX expertweb** : Patchbay visuelle, timeline, graphes

---

## Architecture modulaire

```
src/
├── audio.py                 # Core PipeWire (v0.1)
├── config.py               # Persistence (v0.1)
├── window.py               # UI GTK (v0.1)
├── main.py                 # App entry (v0.1)
│
├── routing_rules.py        # Règles app/device (v0.2)
├── hardware_profiles.py    # Profils matériel + hotplug (v0.2)
├── audio_zones.py          # Zones multiples (v0.2)
├── audit_log.py            # Historique complet (v0.2)
├── diagnostics.py          # Santé + recovery (v0.2)
├── undo_redo.py            # Undo/redo stack (v0.2)
│
├── equalizer.py            # EQ 5/10/31 bandes (v0.3)
├── normalizer.py           # Normalisation LUFS (v0.3)
├── scenarios.py            # Scénarios composés (v0.3)
├── hotkeys.py              # Raccourcis globaux X11/Wayland (v0.3)
├── hotplug.py              # Hot-plug robuste + crossfade (v0.3)
│
├── compressor.py           # Compression/expansion (v0.4)
├── routing_chains.py       # Graphe routage dynamique (v0.4)
├── latency_sync.py         # Sync multi-sink (v0.4)
├── macros.py               # Macros enchaînées (v0.4)
│
├── visualization.py        # Spectro, latence graphs (v0.4+)
├── dbus_service.py         # D-Bus interface (v1.0+)
├── effects.py              # Délai, reverb simple (v0.4+)
│
└── ui/
    ├── main_window.py      # Fenêtre principale enrichie
    ├── routing_editor.py   # Éditeur graphique chaînes
    ├── scenario_builder.py # Constructeur scénarios
    ├── hotkey_editor.py    # Édition raccourcis
    ├── diagnostics_tab.py  # Onglet diagnostics
    ├── history_viewer.py   # Visualisation historique
    └── widgets/            # Composants réutilisables
        ├── volume_slider.py
        ├── eq_graph.py
        ├── spectrum_analyzer.py
        └── ...

tests/
├── test_audio.py           # Tests backend
├── test_rules.py           # Tests routage
├── test_ui.py              # Tests UI
└── ...

docs/
├── partie2-plan.md         # Plan détaillé (👈 créé)
├── ARCHITECTURE.md         # Ce fichier
├── API.md                  # API interne v0.2+
└── ...
```

---

## Domaines de responsabilité

### 🎯 Routing Engine (`routing_rules.py`, `hardware_profiles.py`, `routing_chains.py`)

**Rôle** : Applique automatiquement des règles complexes aux flux audio

**Opérations clés** :
```python
# Matcher une app
rule.match(app_name="spotify", regex=False)  # → bool

# Appliquer une règle
rule.apply(stream)  # → set volume, sink, filters

# Hardware profile trigger
profile.triggered_by(devices=[...])  # → bool

# Chaînes de routage
chain.connect(source → filter → output)
```

**Événements** :
- App lancée/fermée → match rules
- Device branché/débranché → profile activation
- Règle enable/disable → reapply tous les flux
- Volume changé → log audit

---

### 🔊 Audio Engine (`audio.py` extended)

**Rôle** : Interface unifiée avec PipeWire, gère tous les nœuds

**Nouvelles API v0.2+** :
```python
# Obtenir état complet
state = audio.get_full_state()  # → sinks, streams, links, devices

# Manipulation liens
link_id = audio.create_link(source_id, sink_id, options={})
audio.disconnect_link(link_id)

# Propriétés avancées
audio.set_node_property(node_id, "samplerate", 48000)
latency_ms = audio.get_latency(node_id)

# Event monitoring (async)
audio.on_device_added(callback)
audio.on_device_removed(callback)
audio.on_xrun_detected(callback)
```

---

### 🛡️ Supervision (`diagnostics.py`, `audit_log.py`, `undo_redo.py`)

**Rôle** : Tracer, analyser, permettre recovery

**Modules** :
- **AuditLog** : Événement → SQLite, query, export
- **Diagnostics** : Check santé (Xruns, latence, CPU), propose fixes
- **UndoRedo** : Stack actions (max 50), revert/replay
- **StateManager** : Snapshot tous les 30s, restore after crash

**Workflow** :
```
Action utilisateur
    ↓
UndoRedo.push(action)
    ↓
Audio.apply(action)
    ↓
AuditLog.record(action, actor="user")
    ↓
StateManager.snapshot() [if major change]
```

---

### 🎚️ DSP (Digital Signal Processing)

#### Equalizer (`equalizer.py`)
```python
EQ = {
    "preset": "bass_boost",
    "bands": [
        {"freq": 60, "gain": +6, "q": 0.7},
        {"freq": 1k, "gain": -2, "q": 1.0},
        ...
    ]
}

# Application
audio.apply_filter(node_id, eq_config)  # Via wpctl ou ALSA
```

#### Normalizer (`normalizer.py`)
```python
# Leveling en LUFS (Loudness Units relative to Full Scale)
Normalizer = {
    "target_lufs": -20,
    "attack_ms": 10,
    "release_ms": 1000,
    "max_gain": 12
}

# Détecte: loudness courant via FFT
# Applique: gain pour atteindre target (smooth)
```

#### Compressor (`compressor.py`)
```python
Compressor = {
    "threshold": -20,  # dB
    "ratio": 4.0,      # 4:1 compression
    "attack_ms": 5,
    "release_ms": 100,
    "makeup": True     # Auto makeup gain
}

# Implémentation: detector → gain computer → output
```

---

### 🎯 Automation & Macros

#### Rules Engine (`routing_rules.py`)
```python
# Règle = Matcher + Actions
Rule = {
    "id": "rule_1",
    "matcher": {
        "app": {"regex": "spotify|vlc"},  # ou "exact", "wildcard"
        "device": "present",              # présent au matching ?
        "priority": 100                   # ordre exécution
    },
    "actions": [
        {"type": "set_sink", "value": "Casque USB"},
        {"type": "apply_eq", "preset": "enhance_voice"},
        {"type": "set_volume", "value": 75}
    ]
}

# Execution
for rule in rules:
    if rule.match(stream, devices):
        for action in rule.actions:
            action.execute(stream)
```

#### Scenarios (`scenarios.py`)
```python
# Scénario = Séquence d'actions + triggers
Scenario = {
    "name": "Réunion Zoom",
    "triggers": ["time 09:00-17:00", "app:zoom.us"],
    "steps": [
        {"delay": 0, "action": "set_default_sink", "value": "USB Headset"},
        {"delay": 100, "action": "mute_app", "app": "spotify"},
        {"delay": 200, "action": "apply_eq", "preset": "enhance_voice"},
    ]
}

# Exécution
if scenario.triggered():
    for step in scenario.steps:
        sleep(step.delay)
        step.execute()
```

#### Macros (`macros.py`)
```python
# Macro = DSL simple pour scripting audio
macro_code = """
trigger time 18:00:00 daily
  set-zone-volume "Salon" 80
  mute-app "Zoom"
  notify "Fin de journée"
end
"""

# Parser → AST → Executor
```

---

### 🚀 User Interface Evolution

#### v0.1 Status
- ✅ Contrôle simple (volume, mute)
- ✅ Listes apps/sinks statiques
- ✅ Routage basique (change sink)

#### v0.2 (Nouvelle UI)
- ✅ **Rules Manager** : Create/edit/delete rules avec preview
- ✅ **Zones Organizer** : Drag-drop sinks dans zones
- ✅ **Diagnostics Tab** : Health check, Xrun detector, fix suggestions
- ✅ **History Viewer** : Timeline log, filter, export
- ✅ **Undo/Redo** : Buttons + hotkeys

#### v0.3 (Expert)
- ✅ **Scenario Builder** : Wizard visual steps
- ✅ **EQ Editor** : 5/31 bandes, presets, A/B compare
- ✅ **Hotkey Editor** : Capture combo, assign action
- ✅ **Notifications** : Desktop toast, action buttons

#### v0.4+ (Pro)
- ✅ **Routing Graph** : Patchbay-style visual editor
- ✅ **Macro Editor** : DSL editor avec syntax highlight
- ✅ **Latency Dashboard** : Graphs par route
- ✅ **Spectrum Analyzer** : FFT real-time

---

## Data Persistence Strategy

### Config Files
```
~/.config/linux-audio-manager/
├── settings.json           # Settingsbasiques (v0.1)
├── state.snapshot.json     # État courant + historique (v0.2)
├── audit.db               # SQLite audit log (v0.2)
├── rules.json             # Règles utilisateur (v0.2)
├── profiles.json          # Hardware profiles (v0.2)
├── scenarios.json         # Scénarios sauvegardés (v0.3)
├── hotkeys.json           # Raccourcis clavier (v0.3)
├── macros.yaml            # Macros sauvegardées (v0.4)
└── plugins/               # Plugin data (future)
```

### Schema SQLite (audit.db)
```sql
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT,  -- 'volume_changed', 'rule_applied', 'device_added', etc.
    actor TEXT,       -- 'user', 'rule:rule_id', 'hotplug', 'macro:macro_name'
    node_id INTEGER,
    old_value TEXT,
    new_value TEXT,
    details JSON
);

CREATE INDEX idx_timestamp ON audit_log(timestamp);
CREATE INDEX idx_event_type ON audit_log(event_type);
```

---

## Event System

### Internal Events
```python
# Audio engine dispatches events
event = AudioEvent(
    type="volume_changed",
    source="user" | "rule" | "hotplug",
    node_id=42,
    old=0.5,
    new=0.8
)

# Subscribers react
audit_log.on_event(event)
undo_redo.on_event(event)
ui_window.on_event(event)  # Update display
```

### Background Monitors (Threads)
```python
# Persistent monitoring (runs in background)
Monitor = {
    "diagnostics": {
        "interval_s": 60,
        "checks": ["xrun_detect", "latency", "cpu_usage"]
    },
    "hotplug": {
        "method": "udev" | "dbus" | "polling",
        "profile_apply": "auto" | "ask" | "manual"
    },
    "state_snapshot": {
        "interval_s": 30,
        "keep_count": 10
    }
}
```

---

## Integration Points

### D-Bus Interface (v1.0+)
```xml
<interface name="com.example.LinuxAudioManager">
  <method name="SetVolume">
    <arg name="node_id" type="i" direction="in"/>
    <arg name="volume" type="d" direction="in"/>
  </method>
  <method name="ApplyScenario">
    <arg name="scenario_name" type="s" direction="in"/>
  </method>
  <signal name="VolumeChanged">
    <arg name="node_id" type="i"/>
    <arg name="volume" type="d"/>
  </signal>
  <signal name="DevicePlugged">
    <arg name="device_name" type="s"/>
  </signal>
</interface>
```

### System Tray / Panel Icon
- Quick toggle: mute, switch scenario
- Show next scheduled macro
- Emergency stop (mute all)

### Keyboard Input (v0.3+)
```python
# Global hotkeys via:
# - python-xlib (X11)
# - dbus (Wayland)
# - polling fallback

hotkey_map = {
    "Ctrl+Alt+M": "toggle_mute",
    "Ctrl+Alt+P": "next_profile",
    "Win+1": "apply_scenario:Work",
}
```

---

## Performance & Resource Use

### Memory Budget (Target)
- Base app: < 50 MB
- With large audit log: < 150 MB
- With all zones/rules: < 200 MB

### CPU Budget
- Idle: < 0.1% CPU
- During changes: < 5% CPU
- Diagnostics/monitoring: < 2% CPU overhead

### Latency
- Rule matching + apply: < 50 ms
- Scenario execution: < 200 ms total
- Hotplug response: < 100 ms
- UI update after event: < 16 ms (60 FPS)

---

## Testing Strategy

### Unit Tests
```python
tests/test_routing_rules.py
- Match app by regex/wildcard
- Priority ordering
- Conflict resolution

tests/test_audio_zones.py
- Grouping/ungrouping sinks
- Volume balancing

tests/test_audit_log.py
- Insert/query events
- Filtering, export
```

### Integration Tests
```python
tests/test_end_to_end.py
- App launch → rule match → volume set
- Device hotplug → profile activate
- Scenario trigger → sequence execute
```

### UI Tests
```python
tests/test_ui.py  (Pytest + mock GTK)
- Rules manager CRUD
- Zone organizer drag-drop
- Scenario builder steps
```

### Performance Tests
```python
tests/test_perf.py
- Rule matching 1000 apps: < 10 ms
- Audit log query 100k entries: < 100 ms
- Scenario execution 20 steps: < 500 ms
```

---

## Dependencies (v0.2+)

| Module | Dependency | Source | Notes |
|--------|-----------|--------|-------|
| `routing_rules.py` | stdlib | ✅ | JSON, regex, match |
| `audit_log.py` | sqlite3 (stdlib) | ✅ | Always available |
| `diagnostics.py` | subprocess | ✅ | pw-dump parsing |
| `hotkeys.py` | python-xlib OR dbus | ⚠️ | Optional, fallback simple |
| `equalizer.py` | numpy (optional) | ⚠️ | For FFT; fallback DSP |
| `visualization.py` | matplotlib (optional) | ⚠️ | For graphs; fallback text |
| `dbus_service.py` | dbus-python | ⚠️ | v1.0 only |

**Goal** : Toujours fonctionnel avec stdlib seul, features optionnel.

---

## Release Checklist (par version)

### v0.2 (Règles + Fondations)
- [ ] Routing rules engine
- [ ] Hardware profiles + hotplug detect
- [ ] Audio zones grouping
- [ ] Audit log (SQLite)
- [ ] Diagnostics/Xrun detect
- [ ] Undo/redo (50-stack)
- [ ] State snapshots
- [ ] UI: Rules manager, Zones tab, History, Diagnostics
- [ ] Tests: 80% coverage
- [ ] Docs: API, architecture, user guide

### v0.3 (Audio avancé)
- [ ] Equalizer (5/10/31 bandes)
- [ ] Normalizer (LUFS-based)
- [ ] Scenarios builder
- [ ] Hotkeys + global keyboard
- [ ] Hot-plugging robust + crossfade
- [ ] Notifications system
- [ ] UI: EQ editor, Scenario builder, Hotkey editor
- [ ] Tests: 85% coverage

### v0.4+ (Pro)
- [ ] Compression/expansion
- [ ] Routing graph (patchbay)
- [ ] Macros + DSL engine
- [ ] Latency sync + measurement
- [ ] Visualizations (spectro, waveform, latency graph)
- [ ] Tests: 90% coverage

### v1.0 (Stable)
- [ ] D-Bus service complete
- [ ] Plugin system (basic)
- [ ] Mobile app (optional)
- [ ] System tray integration
- [ ] User manual 100%
- [ ] Tests: 95% coverage
- [ ] Performance benchmarks
- [ ] Security review (D-Bus)
