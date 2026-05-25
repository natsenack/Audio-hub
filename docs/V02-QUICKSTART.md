# Guide de démarrage v0.2

## Vue d'ensemble

v0.2 transforme LAM d'une simple interface de contrôle volume en **plateforme d'automatisation audio**. 
Cette guide aide à naviguer la transition v0.1 → v0.2.

---

## Avant de commencer

### Lire dans cet ordre

1. **[docs/roadmap.md](roadmap.md)** — Vue d'ensemble globale v0.1-v1.0+
2. **[docs/ARCHITECTURE.md](ARCHITECTURE.md)** — Design modulaire détaillé
3. **[docs/DECISIONS.md](DECISIONS.md)** — Choix techniques documentés
4. **Ce fichier** — Plan d'action v0.2

### Questions clés à répondre

- [ ] **Database** : Accepte SQLite + JSON hybrid ?
- [ ] **UI Framework** : GTK4 natif ou PyQt5 ?
- [ ] **Hotkeys** : python-xlib (X11) acceptable ?
- [ ] **Timeline** : 1-2 mois réaliste ?
- [ ] **Dépendances optionnelles** : Acceptables (numpy, xlib, etc.) ?

---

## Roadmap d'implémentation v0.2

### Phase 1 : Fondations (Semaine 1-2)

**Objectif** : Infrastructure pour règles et persistance avancée

#### 1.1 Database Setup
```python
# src/audit_log.py
class AuditLog:
    def __init__(self):
        self.db = sqlite3.connect(...audit.db)
    
    def record(self, event):
        # INSERT INTO audit_log ...
        pass
    
    def query_by_date(self, start, end):
        # SELECT * WHERE timestamp BETWEEN ...
        pass
    
    def export_csv(self):
        # SELECT * → CSV file
        pass
```

**Schema SQLite** :
```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT NOT NULL,     -- 'volume_changed', 'rule_applied', 'device_added'
    actor TEXT NOT NULL,          -- 'user', 'rule:123', 'hotplug', 'scenario:work'
    node_id INTEGER,              -- which device/app
    old_value TEXT,               -- JSON or plain
    new_value TEXT,
    details TEXT,                 -- JSON extra info
    FOREIGN KEY(node_id) REFERENCES nodes(id)
);

CREATE INDEX idx_timestamp ON audit_log(timestamp);
CREATE INDEX idx_type ON audit_log(event_type);
CREATE INDEX idx_actor ON audit_log(actor);
```

**Tests** :
```python
# tests/test_audit_log.py
def test_record_event():
    log = AuditLog()
    log.record({"type": "volume_changed", "actor": "user", ...})
    events = log.query_by_date(...)
    assert len(events) > 0

def test_export_csv():
    log.export_csv("export.csv")
    assert Path("export.csv").exists()
```

**Checklist** :
- [ ] SQLite DB create
- [ ] Schema avec indexes
- [ ] record() method
- [ ] query methods (by date, by type, by actor)
- [ ] export_csv()
- [ ] Unit tests 100% coverage
- [ ] Error handling (disk full, permissions)

---

#### 1.2 State Manager (Atomique)
```python
# src/state_manager.py
class StateManager:
    def __init__(self, config_dir):
        self.state_dir = config_dir / "state"
        self.state_dir.mkdir(exist_ok=True)
    
    def save_state(self, state: dict) -> bool:
        """Atomic save with rollback history"""
        tmpfile = self.state_dir / "state.json.tmp"
        try:
            with open(tmpfile, 'w') as f:
                json.dump(state, f, indent=2)
            
            # Rotate history: state.json → state.json.1 → state.json.2
            for i in range(1, 2):  # Keep last 2
                old = self.state_dir / f"state.json.{i}"
                new = self.state_dir / f"state.json.{i+1}"
                if old.exists():
                    old.replace(new)
            
            # Atomic rename
            if (self.state_dir / "state.json").exists():
                (self.state_dir / "state.json").replace(
                    self.state_dir / "state.json.1"
                )
            tmpfile.replace(self.state_dir / "state.json")
            return True
        except Exception as e:
            print(f"State save failed: {e}, no corruption")
            return False
    
    def load_state(self) -> dict:
        """Load current or fallback to history"""
        try:
            return json.load(open(self.state_dir / "state.json"))
        except:
            # Fallback
            try:
                return json.load(open(self.state_dir / "state.json.1"))
            except:
                return {}  # Empty default
    
    def restore_from_backup(self, index: int = 1) -> bool:
        """Restore from history (index 1=oldest available)"""
        backup = self.state_dir / f"state.json.{index}"
        if backup.exists():
            backup.replace(self.state_dir / "state.json")
            return True
        return False
```

**Checklist** :
- [ ] StateManager class
- [ ] Atomic save (tmpfile → rename)
- [ ] Rollback history (rotate 2-3 versions)
- [ ] load_state() with fallbacks
- [ ] restore_from_backup()
- [ ] Error handling (no corruption on fail)
- [ ] Tests

---

#### 1.3 Undo/Redo Stack
```python
# src/undo_redo.py
class UndoRedo:
    def __init__(self, max_stack_size=50):
        self.max_size = max_stack_size
        self.undo_stack = []  # list of (action, old_state)
        self.redo_stack = []  # list of (action, new_state)
    
    def push(self, action: dict, old_state: dict) -> None:
        """Record action before executing"""
        self.undo_stack.append({"action": action, "old_state": old_state})
        self.redo_stack.clear()  # New action invalidates redo
        
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.pop(0)
    
    def undo(self) -> dict:
        """Undo last action, return old state"""
        if not self.undo_stack:
            return None
        item = self.undo_stack.pop()
        self.redo_stack.append(item)
        return item["old_state"]
    
    def redo(self) -> dict:
        """Redo last undone action, return new state"""
        if not self.redo_stack:
            return None
        item = self.redo_stack.pop()
        self.undo_stack.append(item)
        return item["new_state"]
    
    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0
    
    def timeline(self) -> list[str]:
        """List of actions for display"""
        return [item["action"]["description"] for item in self.undo_stack[-10:]]
```

**Checklist** :
- [ ] push(action, old_state)
- [ ] undo() with state restoration
- [ ] redo() with state restoration
- [ ] can_undo() / can_redo() for button enable
- [ ] timeline() for UI display
- [ ] Max 50-stack enforcement
- [ ] Tests Ctrl+Z scenarios

---

### Phase 2 : Routing Engine (Semaine 3-4)

**Objectif** : Appliquer des règles automatiquement aux flux audio

#### 2.1 Rules Engine
```python
# src/routing_rules.py
from dataclasses import dataclass
from enum import Enum
import re

class MatchType(Enum):
    EXACT = "exact"
    REGEX = "regex"
    WILDCARD = "wildcard"

@dataclass
class RoutingRule:
    id: str
    name: str
    enabled: bool
    
    # Matcher
    app_name: str
    match_type: MatchType = MatchType.REGEX
    
    # Actions
    target_sink: str = None       # Sink device ID
    apply_eq: str = None          # Preset name
    volume: float = None          # 0-1
    mute: bool = False
    priority: int = 100           # Execution order
    
    def match(self, stream: AudioStream) -> bool:
        """Does this rule apply to stream?"""
        if not self.enabled:
            return False
        
        if self.match_type == MatchType.EXACT:
            return stream.app_name == self.app_name
        elif self.match_type == MatchType.REGEX:
            return re.search(self.app_name, stream.app_name) is not None
        elif self.match_type == MatchType.WILDCARD:
            pattern = self.app_name.replace('*', '.*')
            return re.match(pattern, stream.app_name) is not None
        
        return False
    
    def apply(self, stream: AudioStream) -> None:
        """Apply rule actions to stream"""
        if self.target_sink:
            audio.set_node_sink(stream.node_id, self.target_sink)
        if self.volume is not None:
            audio.set_node_volume(stream.node_id, self.volume)
        if self.mute:
            audio.toggle_mute(stream.node_id)
        # ...etc

class RulesEngine:
    def __init__(self):
        self.rules = []
    
    def load_rules(self) -> list[RoutingRule]:
        """Load from rules.json"""
        with open(...) as f:
            rules_data = json.load(f)
        return [RoutingRule(**r) for r in rules_data]
    
    def save_rules(self, rules: list[RoutingRule]) -> None:
        """Save to rules.json"""
        with open(..., 'w') as f:
            json.dump([asdict(r) for r in rules], f, indent=2)
    
    def apply_rules(self, streams: list[AudioStream]) -> None:
        """Apply all rules to all streams"""
        for stream in streams:
            # Sorted by priority
            matching = [r for r in self.rules if r.match(stream)]
            for rule in sorted(matching, key=lambda r: r.priority):
                rule.apply(stream)
    
    def create_rule(self, name: str, app_pattern: str, actions: dict) -> RoutingRule:
        """UI helper"""
        rule = RoutingRule(
            id=str(uuid4()),
            name=name,
            enabled=True,
            app_name=app_pattern,
            **actions
        )
        self.rules.append(rule)
        self.save_rules(self.rules)
        return rule
    
    def delete_rule(self, rule_id: str) -> None:
        self.rules = [r for r in self.rules if r.id != rule_id]
        self.save_rules(self.rules)
    
    def toggle_rule(self, rule_id: str) -> None:
        for rule in self.rules:
            if rule.id == rule_id:
                rule.enabled = not rule.enabled
        self.save_rules(self.rules)
```

**Checklist** :
- [ ] RoutingRule dataclass
- [ ] Match engines (exact, regex, wildcard)
- [ ] apply() for actions
- [ ] RulesEngine load/save JSON
- [ ] apply_rules() to all streams
- [ ] create/delete/toggle methods
- [ ] Priority sorting
- [ ] Conflict detection
- [ ] Tests regex patterns

---

#### 2.2 Hardware Profiles
```python
# src/hardware_profiles.py
@dataclass
class HardwareProfile:
    name: str
    description: str
    
    # Trigger conditions
    required_devices: list[str]  # ["USB Headset", "Speaker"]
    
    # Actions when profile activated
    rules: list[RoutingRule]
    default_sink: str = None
    
    def triggered(self, current_devices: list[str]) -> bool:
        """Check if all required devices present"""
        return all(dev in current_devices for dev in self.required_devices)
    
    def activate(self) -> None:
        """Apply this profile"""
        for rule in self.rules:
            rule.apply(...)  # Apply all rules
        if self.default_sink:
            audio.set_default_sink(self.default_sink)
        audit_log.record({
            "type": "profile_activated",
            "actor": "hotplug",
            "details": {"profile": self.name}
        })

class ProfileManager:
    def __init__(self):
        self.profiles = []
        self.active_profile = None
    
    def check_and_apply(self, devices: list[str]) -> None:
        """Called when device list changes"""
        # Find matching profile with highest priority
        candidates = [p for p in self.profiles if p.triggered(devices)]
        if candidates:
            profile = max(candidates, key=lambda p: p.priority)
            if profile != self.active_profile:
                profile.activate()
                self.active_profile = profile
    
    def load_profiles(self) -> None:
        """Load from profiles.json"""
        with open(...) as f:
            data = json.load(f)
        self.profiles = [HardwareProfile(**p) for p in data]
```

**Checklist** :
- [ ] HardwareProfile dataclass
- [ ] triggered() condition check
- [ ] activate() method
- [ ] ProfileManager check_and_apply()
- [ ] Load/save profiles.json
- [ ] Priority sorting
- [ ] Tests device matching

---

### Phase 3 : Audio Zones (Semaine 4)

**Objectif** : Grouper sinks logiquement

```python
# src/audio_zones.py
@dataclass
class AudioZone:
    name: str
    description: str
    sink_ids: list[int]  # Which sinks in this zone
    
    def set_volume(self, volume: float) -> None:
        """Set volume for all sinks in zone"""
        for sink_id in self.sink_ids:
            audio.set_node_volume(sink_id, volume)
    
    def get_volume(self) -> float:
        """Average volume"""
        volumes = [audio.get_node_volume(id) for id in self.sink_ids]
        return sum(volumes) / len(volumes) if volumes else 0

class ZoneManager:
    def __init__(self):
        self.zones = []
    
    def create_zone(self, name: str, sink_ids: list[int]) -> AudioZone:
        zone = AudioZone(name=name, sink_ids=sink_ids)
        self.zones.append(zone)
        self.save_zones()
        return zone
    
    def save_zones(self) -> None:
        config.save_zones(self.zones)
```

**Checklist** :
- [ ] AudioZone dataclass
- [ ] set_volume() multi-sink
- [ ] get_volume() average
- [ ] ZoneManager create/delete
- [ ] UI drag-drop zones editor
- [ ] Load/save zones.json
- [ ] Tests volume balancing

---

### Phase 4 : UI Integration (Semaine 4)

**Objectif** : Ajouter UI sections pour nouvelles features

#### 4.1 New UI Tabs

```python
# src/window.py additions
class _MainWindowAdwaita(...):
    def _build_preferences_page(self):
        # Existing: Volume, Mute
        
        # NEW: Rules Manager tab
        rules_tab = self._build_rules_manager_tab()
        
        # NEW: Zones Organizer tab
        zones_tab = self._build_zones_organizer_tab()
        
        # NEW: History/Audit tab
        history_tab = self._build_history_tab()
        
        # NEW: Diagnostics tab
        diag_tab = self._build_diagnostics_tab()
    
    def _build_rules_manager_tab(self):
        """Create rule editor UI"""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # List of rules
        rules_store = Gtk.ListStore(str, str, bool)  # ID, Name, Enabled
        rules_view = Gtk.TreeView(rules_store)
        
        # Buttons: Add, Edit, Delete, Duplicate
        actions_box = Gtk.Box(...)
        add_btn = Gtk.Button(label="New Rule")
        add_btn.connect("clicked", self._on_add_rule)
        
        box.append(rules_view)
        box.append(actions_box)
        return box
    
    def _on_add_rule(self, button):
        """Open rule creation dialog"""
        dialog = RuleCreationDialog(self)
        dialog.present()
    
    def _build_zones_organizer_tab(self):
        """Drag-drop zones editor"""
        # Left: Available sinks
        # Right: Zones with sinks
        # Drag sink left→right to add to zone
        pass
    
    def _build_history_tab(self):
        """Audit log viewer"""
        # List: timestamp, type, actor, node, old→new
        # Filter: date range, event type
        # Export: CSV button
        pass
    
    def _build_diagnostics_tab(self):
        """Health check dashboard"""
        # Status: Xruns, latency, CPU usage
        # Tests: Record→playback (mic test), latency measure
        # Fixes: "Restart daemon" button
        pass
```

**Checklist** :
- [ ] Rules Manager tab
  - [ ] List rules with enable/disable toggle
  - [ ] New rule dialog (name, app pattern, actions)
  - [ ] Edit rule dialog
  - [ ] Delete button
  - [ ] Priority up/down buttons
- [ ] Zones Organizer tab
  - [ ] List sinks
  - [ ] List zones
  - [ ] Drag sink into zone
  - [ ] Zone volume slider (applies to all)
  - [ ] New/delete zone
- [ ] History tab
  - [ ] Timestamp + Event type + Actor + Details
  - [ ] Filter by date range
  - [ ] Filter by event type
  - [ ] Export CSV button
  - [ ] Search text
- [ ] Diagnostics tab
  - [ ] Show Xrun count + time
  - [ ] Show latency (ms)
  - [ ] Show CPU usage (%)
  - [ ] "Run tests" button
  - [ ] "Restart PipeWire daemon" button

---

## Testing Checklist v0.2

### Unit Tests
```bash
pytest tests/test_audit_log.py      # 100% coverage
pytest tests/test_state_manager.py  # Error scenarios
pytest tests/test_undo_redo.py      # Stack limits
pytest tests/test_routing_rules.py  # Matcher + apply
pytest tests/test_zones.py          # Volume balancing
```

### Integration Tests
```bash
pytest tests/test_v02_scenarios.py
# - Rule matches new stream → applies volume
# - Profile triggers on device hotplug
# - Zone volume affects all sinks
# - Undo changes restore state
# - Audit log records events
```

### UI Tests
```bash
# Manual (automated GTK testing is complex)
- [ ] Rules Manager: add/edit/delete works
- [ ] Zones: drag sink into zone, volume updates
- [ ] History: filter works, export creates file
- [ ] Diagnostics: tests complete without hang
- [ ] Undo button disables when nothing to undo
```

### Performance Benchmarks
```python
# tests/test_perf.py
- [ ] Rule matching 1000 streams: < 10ms
- [ ] Zone volume update 5 sinks: < 50ms
- [ ] Audit log query 100k entries: < 100ms
- [ ] Load all config files: < 500ms
- [ ] Memory footprint < 200MB
```

---

## Dépendances v0.2

### Stdlib uniquement
- `sqlite3` — Audit database
- `json` — Config files
- `pathlib` — File operations
- `dataclasses` — Data models
- `subprocess` — PipeWire commands
- `re` — Pattern matching
- `uuid` — Generate rule IDs

### Optionnel (fallback graceful)
- `numpy` — Future signal processing (v0.3+)

### Pas de nouvelles dépendances obligatoires

---

## Files à créer/modifier

### Nouveaux fichiers source
```
src/
├── audit_log.py          (NEW) 200 lignes
├── state_manager.py      (NEW) 150 lignes
├── undo_redo.py          (NEW) 120 lignes
├── routing_rules.py      (NEW) 250 lignes
├── hardware_profiles.py  (NEW) 200 lignes
└── audio_zones.py        (NEW) 150 lignes
```

### Fichiers modifiés
```
src/
├── window.py             [+4 new tabs, +500 lignes]
├── audio.py              [+event monitoring, ~50 lignes]
├── config.py             [+zone/rule/profile save, ~100 lignes]
└── main.py               [minor tweaks]
```

### Fichiers configuration
```
~/.config/linux-audio-manager/
├── audit.db              (NEW) SQLite
├── rules.json            (NEW) User rules
├── profiles.json         (NEW) Hardware profiles
├── zones.json            (NEW) Audio zones
└── state/
    ├── state.json        (NEW) Current state
    ├── state.json.1      (NEW) Backup
    └── state.json.2      (NEW) Backup
```

---

## Timeline estimé

| Tâche | Durée | Deps |
|-------|-------|------|
| Audit log (SQLite) | 3-5j | None |
| State manager (atomique) | 2j | Audit log |
| Undo/redo stack | 2j | State manager |
| Rules engine | 5-7j | Audit log |
| Hardware profiles | 3j | Rules |
| Audio zones | 3j | None |
| UI: 4 tabs | 7-10j | All above |
| Testing + bugfix | 5j | All |
| **Total** | **30-35j** | **~7 semaines** |

**Réaliste sur un développeur part-time ?**
- 7 semaines = ~2 mois ✅
- Diviser par 2-3 si plus de contributeurs

---

## Commencer maintenant

### Étape 1 : Setup dev environment
```bash
cd /path/to/linux-audio-manager

# Install dev tools
make check  # Verify Python syntax

# Create branch
git checkout -b feature/v0.2-foundations
```

### Étape 2 : Primeira tâche (Audit log)
```bash
# Create file
touch src/audit_log.py

# Follow skeleton in Phase 1.1 above

# Create tests
touch tests/test_audit_log.py

# Run tests
pytest tests/test_audit_log.py -v
```

### Étape 3 : Iterate
1. Implement one phase (Audit → State → Undo → Rules → Zones → UI)
2. Write tests
3. Test manually
4. Commit + push
5. Next phase

---

## Questions à poser à l'équipe

1. **Database** : SQLite + JSON acceptable ? Ou pure JSON ?
2. **UI Framework** : Rester GTK4 ? Ou PyQt5 pour graphique avancé ?
3. **Timeline** : 7 semaines avec part-time dev faisable ?
4. **Dépendances** : Accepter numpy (v0.3) et python-xlib (v0.3) ?
5. **Priorités** : Rules → Zones → History → Diagnostics... quel ordre user préfère ?

---

## Resources

- [ARCHITECTURE.md](ARCHITECTURE.md) — Architecture modulaire
- [DECISIONS.md](DECISIONS.md) — Décisions techniques
- [partie2-plan.md](partie2-plan.md) — Spécifications complètes
- PipeWire docs : https://docs.pipewire.org/
- GTK4 docs : https://docs.gtk.org/gtk4/

---

**v0.2 est prête à être implémentée. À vos claviers ! 🚀**
