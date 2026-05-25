# Décisions techniques Partie 2

## 1. Base de données : SQLite vs JSON vs Hybrid

### Option A : SQLite (✅ RECOMMANDÉ pour v0.2)

**Avantages** :
- ✅ Audit log : requêtes complexes (filter, aggregate, date range)
- ✅ Performance : 100k entrées < 100ms query
- ✅ Intégrité : ACID, transactions
- ✅ Export facile (CSV, JSON)
- ✅ Déjà en stdlib Python

**Inconvénients** :
- ⚠️ Setup initial (CREATE TABLE)
- ⚠️ Migration schema si changement

**Décision** : **SQLite pour audit.db + JSON pour configs** (meilleur des deux mondes)

---

### Option B : JSON files only

**Avantages** :
- ✅ Simple, aucune dépendance
- ✅ Versionnable (git)
- ✅ Human-readable

**Inconvénients** :
- ❌ Slow pour 100k lignes (100+ ms)
- ❌ Pas de query complex (must load all)
- ❌ Concurrence (lock) difficile
- ❌ Export compliqué

**Décision** : Pas assez performant pour historique volumineux.

---

### Option C : Hybrid (SQLite audit + JSON config)

**Approche** :
```
~/.config/linux-audio-manager/
├── audit.db              # SQLite : audit_log + metrics tables
├── settings.json         # Config basiques
├── rules.json            # Règles + profiles
├── scenarios.json        # Scénarios
└── state.snapshot.json   # État courant
```

**Implémentation** :
```python
# audit_log.py
class AuditLog:
    def __init__(self):
        self.db = sqlite3.connect("~/.config/.../audit.db")
        self.db.row_factory = sqlite3.Row
    
    def record(self, event: dict):
        self.db.execute("""
            INSERT INTO audit_log (timestamp, type, actor, node_id, details)
            VALUES (datetime('now'), ?, ?, ?, json(?))
        """, (event["type"], event["actor"], event.get("node_id"), 
              json.dumps(event.get("details", {}))))
        self.db.commit()
    
    def query(self, filters: dict) -> list:
        # WHERE event_type=? AND timestamp > ? AND...
        pass
    
    def export_csv(self, filepath):
        # SELECT * ... → CSV
        pass

# config.py
class ConfigManager:
    def __init__(self):
        self.path = Path.home() / ".config/linux-audio-manager"
        
    def load_rules(self) -> list[dict]:
        with open(self.path / "rules.json") as f:
            return json.load(f)
    
    def save_rules(self, rules: list[dict]):
        with open(self.path / "rules.json", 'w') as f:
            json.dump(rules, f, indent=2)
```

**Décision** : **Hybrid approach** = SQLite + JSON

---

## 2. UI pour graphe routage : Tkinter vs PyQt5 vs GTK native

### Option A : Tkinter

**Avantages** :
- ✅ Stdlib (aucune dépendance)
- ✅ Simple pour basic shapes
- ✅ Cross-platform

**Inconvénients** :
- ❌ Looks dated (90s)
- ❌ Limited d-n-d support
- ❌ Perf graphique faible
- ❌ Pas de thème moderne

**Décision** : Pas pour v0.3+

---

### Option B : PyQt5

**Avantages** :
- ✅ Graphique professionnel
- ✅ Drag-drop exceptionnel
- ✅ Widgets riches (dock, tree, table)
- ✅ QGraphicsView (patchbay possible)
- ✅ Designer UI (ui files)

**Inconvénients** :
- ❌ Dépendance heavyweight
- ❌ License LGPL (okay pour FOSS)
- ❌ Apprentissage courbe

**Décision** : Fortement considéré pour v0.4+

---

### Option C : GTK4 native

**Avantages** :
- ✅ Cohérent avec v0.1 (déjà utilisé)
- ✅ Lightweight, natif GNOME
- ✅ CSS theming
- ✅ Libadwaita for moderne look

**Inconvénients** :
- ⚠️ Canvas/drawing moins avancé que Qt
- ⚠️ Custom widgets plus complexe
- ⚠️ GTK3 fallback compliqué pour graphe

**Décision** : **GTK4 natif pour v0.3-0.4**, PyQt5 si graphe complexe nécessaire

---

### Option D : Web UI (future)

```
src/
├── backend/       # Existing Python + FastAPI
├── frontend/      # React/Vue web app
└── server.py      # WebSocket API
```

**Avantages** :
- ✅ Cross-platform (browser)
- ✅ Mobile-friendly
- ✅ Modern tools (React, Svelte)
- ✅ Cloud-ready

**Inconvénients** :
- ❌ Overhead (server + client)
- ❌ Latency réseau
- ❌ Plus complex

**Décision** : **v1.0+ bonus feature** (optionnel)

---

## 3. EQ Engine : Custom DSP vs ALSA/JACK vs Plugin

### Option A : Custom Python DSP

```python
# Filtre biquad simple
class BiQuadFilter:
    def __init__(self, freq, gain, q, sample_rate):
        self.a0, self.a1, self.a2 = ...  # Coefficients
        self.b0, self.b1, self.b2 = ...
    
    def process(self, samples: np.array) -> np.array:
        # y[n] = (b0*x[n] + b1*x[n-1] + b2*x[n-2]) ...
        # Biquad difference equation
        return output
```

**Avantages** :
- ✅ Pure Python, aucune dépendance
- ✅ 100% contrôlable
- ✅ Comprendre mieux l'EQ

**Inconvénients** :
- ❌ Basse qualité vs industry standard
- ❌ Coefficients complexes à calculer
- ❌ Performance (need numpy)
- ❌ Pas de precision double-précision réelle

**Décision** : Presets simples seulement

---

### Option B : ALSA/JACK Plugin (via subprocess)

```python
# Wrapper autour aplay avec filtre
def apply_eq_via_jack(input_device, eq_config):
    # JACK → jack_simple_client → biquad chain
    # Performance: possible, mais complexe
    pass
```

**Avantages** :
- ✅ Audio professionnel
- ✅ Basse latence (JACK)
- ✅ Précision full

**Inconvénients** :
- ❌ Dépendance JACK/ALSA
- ❌ Setup complexe
- ❌ Pas garanti sur toutes distros

**Décision** : Trop complexe pour v0.3, considérer v0.4

---

### Option C : Plugin (LADSPA/LV2)

```python
# Charger .so/.dll EQ plugin existant
import ctypes

eq_plugin = ctypes.CDLL("./eq.ladspa.so")
eq_plugin.run_eq_mono(buffer, config)
```

**Avantages** :
- ✅ Qualité studio
- ✅ Écosystème plugins existants
- ✅ Performance C/C++

**Inconvénients** :
- ❌ Distribution plugins compliquée
- ❌ License variety (GPL, propriétaire, etc.)
- ❌ Cross-platform hassle (.dll vs .so)

**Décision** : **v1.0+ plugin system** (volontaire)

---

### Décision finale

**v0.3** : Custom Python simple (presets uniquement)  
**v0.4+** : Ajouter NumPy-based EQ pour plus de bandes  
**v1.0+** : Plugin LADSPA/LV2 optionnel

---

## 4. Langage Macros : DSL simple vs Python embedded vs Lua

### Option A : DSL simple (YAML-like)

```yaml
name: "Réunion Zoom"
triggers:
  - "time 09:00-17:00"
  - "app: zoom.us"

steps:
  - delay: 0
    action: set_default_sink
    value: "USB Headset"
  
  - delay: 100
    action: mute_app
    app: "spotify"
  
  - delay: 200
    action: apply_eq
    preset: "enhance_voice"
```

**Avantages** :
- ✅ Facile à apprendre (YAML connu)
- ✅ Safe (pas d'exec code)
- ✅ Versionnable git
- ✅ Validatable schema

**Inconvénients** :
- ❌ Limité (pas de boucle, condition complexe)
- ❌ Parser custom

**Décision** : **v0.3 DSL simple**

---

### Option B : Python embedded (exec)

```python
macro_code = """
if get_app_volume("zoom.us") < 50:
    set_app_volume("zoom.us", 75)
for i in range(3):
    toggle_mute(DEFAULT_SINK)
    sleep(100)
"""

exec(macro_code)
```

**Avantages** :
- ✅ Très flexible
- ✅ Turing-complete
- ✅ Pas de parser

**Inconvénients** :
- ❌ Security issue (arbitrary code execution)
- ❌ User error possible
- ❌ Hard to validate/optimize

**Décision** : **Dangereux**, éviter

---

### Option C : Lua (lightweight VM)

```lua
-- lupa Python wrapper
function on_zoom_active()
    set_default_sink("USB Headset")
    mute_app("spotify")
end

register_trigger("app:zoom.us", on_zoom_active)
```

**Avantages** :
- ✅ Lightweight (1 MB)
- ✅ Safe VM sandbox
- ✅ Flexible mais pas arbitraire

**Inconvénients** :
- ❌ Dépendance Lua (lupa)
- ❌ Courbe apprentissage
- ❌ Overkill pour v0.3

**Décision** : **v1.0+ optionnel** si besoin flexibilité

---

### Décision finale

**v0.3** : DSL YAML simple  
**v0.4+** : Ajouter conditions if/else, boucles simple  
**v1.0+** : Lua optionnel pour scripts avancés

---

## 5. Système de notifications : D-Bus vs GTK vs Externe

### Option A : D-Bus (Freedesktop Standard)

```python
import dbus
from dbus.exceptions import DBusException

def notify(title: str, message: str, actions: dict = None):
    try:
        bus = dbus.SessionBus()
        notify_obj = bus.get_object('org.freedesktop.Notifications',
                                     '/org/freedesktop/Notifications')
        notify_iface = dbus.Interface(notify_obj, 'org.freedesktop.Notifications')
        
        notify_iface.Notify(
            "Linux Audio Manager",  # app name
            0,                       # replaces_id
            "audio-manager-icon",    # icon
            title, message,
            [],                      # actions
            {"urgency": dbus.Byte(1)},
            5000                     # timeout (ms)
        )
    except DBusException:
        print(f"Fallback: {title} - {message}")
```

**Avantages** :
- ✅ Standard GNOME/Freedesktop
- ✅ Respect user settings (do-not-disturb)
- ✅ Notifications centralisées
- ✅ Actions buttons possible

**Inconvénients** :
- ⚠️ Fallback si D-Bus absent (rare)
- ⚠️ Async/callback model

**Décision** : **v0.3 D-Bus + fallback print**

---

### Option B : GTK InfoBar

```python
infobar = Gtk.InfoBar()
infobar.set_message_type(Gtk.MessageType.INFO)
label = Gtk.Label(label="Casque USB branché")
infobar.get_content_area().add(label)
window.add(infobar)
```

**Avantages** :
- ✅ Dans app (visible)
- ✅ Cohérent UI

**Inconvénients** :
- ❌ Dépend fenêtre ouverte
- ❌ Pas pour événements background

**Décision** : Complémentaire à D-Bus (in-window banner)

---

### Option C : Système externe (libnotify)

```bash
notify-send "Linux Audio Manager" "Device plugged"
```

**Avantages** :
- ✅ Works everywhere
- ✅ Respects system settings

**Inconvénients** :
- ❌ Dépendance `notify-send`
- ❌ Moins rich (no custom actions)

**Décision** : Fallback si D-Bus absent

---

### Décision finale

**D-Bus (primaire) + Fallback notify-send**

---

## 6. Hotkeys global : python-xlib vs evdev vs D-Bus

### Option A : python-xlib (X11)

```python
from Xlib import X, display

disp = display.Display()
root = disp.screen().root

# Grab global hotkey Ctrl+Alt+M
root.grab_key(M_code, X.ControlMask | X.Mod1Mask, 1, X.GrabModeAsync, X.GrabModeAsync)

# Event loop
while True:
    event = disp.next_event()
    if event.type == X.KeyPress:
        on_hotkey_pressed(event)
```

**Avantages** :
- ✅ X11 standard
- ✅ Reliable
- ✅ Global grab possible

**Inconvénients** :
- ❌ X11 only (pas Wayland)
- ❌ Dépendance python-xlib
- ❌ Security (can intercept all keys)

**Décision** : **v0.3 si X11, skip Wayland pour now**

---

### Option B : evdev (event device)

```python
from evdev import InputDevice, ecodes
import select

device = InputDevice('/dev/input/event0')

for event in device.read_loop():
    if event.type == ecodes.EV_KEY and event.value == 1:
        on_key_pressed(event.code)
```

**Avantages** :
- ✅ Works X11 + Wayland
- ✅ Direct hardware

**Inconvénients** :
- ❌ Requires root or input group
- ❌ All keys visible (security)
- ❌ Complex event handling

**Décision** : Too low-level

---

### Option C : D-Bus (Wayland future)

```python
# Via portal: org.freedesktop.portal.RemoteDesktop
# Control.Start() → access keyboard events
```

**Avantages** :
- ✅ Wayland compatible
- ✅ Sandboxed (permission)

**Inconvénients** :
- ❌ Complex API
- ❌ Portal support varies by DE
- ❌ Overkill for now

**Décision** : **v1.0+ Wayland support**

---

### Décision finale

**v0.3** : python-xlib pour X11 (fallback simple hotkeys non-global)  
**v1.0+** : Ajouter Wayland via D-Bus portal

---

## 7. Persistance État : Snapshots JSON vs State Directory

### Option A : Snapshot JSON único

```json
{
  "timestamp": "2026-05-25T14:35:00Z",
  "default_sink_id": 42,
  "sinks": [
    {"id": 42, "name": "Speakers", "volume": 0.75, "muted": false},
    {"id": 43, "name": "USB Headset", "volume": 0.5, "muted": false}
  ],
  "streams": [...],
  "active_scenario": "Work",
  "eq_active": true,
  "zones": {...}
}
```

**Avantages** :
- ✅ Simple, un fichier
- ✅ Atomic write
- ✅ Facile version

**Inconvénients** :
- ❌ Tout ou rien (partial crash loss)

**Décision** : **v0.1** (déjà utilisé)

---

### Option B : State Directory (atomique)

```
~/.config/linux-audio-manager/state/
├── .lock            # Prevents concurrent access
├── state.json.tmp   # Temp
├── state.json       # Current (mv atomic)
├── state.json.1     # Rollback history
└── state.json.2     # Rollback history
```

**Implémentation** :
```python
def save_state_atomic(state: dict):
    tmpfile = self.state_path / "state.json.tmp"
    with open(tmpfile, 'w') as f:
        json.dump(state, f)
    
    # Atomic rename
    tmpfile.replace(self.state_path / "state.json")
    
    # Rollback history
    for i in range(1, 3):
        old = self.state_path / f"state.json.{i}"
        new = self.state_path / f"state.json.{i+1}"
        if old.exists():
            old.replace(new)
    
    (self.state_path / "state.json").replace(
        self.state_path / "state.json.1"
    )
```

**Avantages** :
- ✅ Atomique (move = atomic)
- ✅ Rollback history (3 versions)
- ✅ Pas de corruption partielle

**Inconvénients** :
- ⚠️ Plus complexe

**Décision** : **v0.2 upgrade** pour robustesse

---

## Résumé Décisions

| Domaine | v0.2-0.3 | v0.4 | v1.0+ |
|---------|----------|------|-------|
| **Database** | SQLite audit + JSON config | —— | —— |
| **UI Routage** | GTK4 natif simple | GTK4 canvas avancé | PyQt5 optionnel |
| **EQ Engine** | Custom DSL 5 bandes | NumPy 31 bandes | LADSPA/LV2 plugin |
| **Macros DSL** | YAML simple | YAML + if/else | Lua optionnel |
| **Notifications** | D-Bus + fallback | —— | —— |
| **Hotkeys** | python-xlib X11 | —— | D-Bus Wayland |
| **State Persist** | JSON snapshot atomic | —— | —— |

**Overall Philosophy** : Stdlib + optionals, pas de heavyweights obligatoires.
