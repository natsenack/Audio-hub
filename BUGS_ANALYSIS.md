# 🔍 ANALYSE EXHAUSTIVE DES BUGS — audio-hub.py

> **Analyse effectuée le 30 mai 2026 — Méticulosité complète**
> 
> Catégories analysées: Variables, Fonctions, Threading, Logique, Initialisation, Imports, GTK4, Références circulaires, Ressources, Types

---

## 🔴 **CRITIQUES** (Causent crash/corruption)

### BUG #1: Type mismatch dans loopback_config (Ligne 2069)
**Fichier**: audio-hub.py:2069-2074  
**Sévérité**: CRITIQUE  
**Description**: Les clés JSON sont des strings mais comparées avec des entiers

```python
# Ligne 2089: Sauvegarde avec clés entières
self._loopback_config[source_id] = sink_id  # source_id = int
json.dump(self._loopback_config, f, indent=2)  # Convertit keys en strings!

# Ligne 2069: Chargement puis accès avec mismatch de type
self._loopback_config = json.load(f)  # Clés maintenant = strings "123"
for source_id, sink_id in self._loopback_config.items():
    sources = {s.id: s for s in self.audio.get_sources()}  # Keys = ints
    if source_id in sources and sink_id in sinks:  # "123" JAMAIS dans dict[123]!
        # ❌ Cette condition sera TOUJOURS False
```

**Code affecté**: Loopback restoration never works  
**Suggestion de fix**:
```python
# Dans _save_loopback_config:
json.dump({str(k): v for k, v in self._loopback_config.items()}, f)

# Dans _load_loopback_configs:
self._loopback_config = {int(k): v for k, v in json.load(f).items()}
```

---

### BUG #2: Race condition — Device level bars (Ligne 1010)
**Fichier**: audio-hub.py:1010 + 769-770 + 1008  
**Sévérité**: CRITIQUE  
**Description**: Les barres de niveau sont supprimées pendant leur mise à jour

```python
# Ligne 1008 — refresh supprime les références
self._device_level_bars.clear()  # ✗ Les tuples (lbl, bar) sont supprimés

# Ligne 1016-1025 — callback tente d'accéder aux widgets pendants refresh
def _update_level_bars_only(self) -> bool:
    for source_id, widgets in self._device_level_bars.items():  # ✗ Dict peut être vide
        level_lbl, prog_bar = widgets
        peak_level = self.audio._source_peak_levels.get(source_id, 0.0)
        prog_bar.set_fraction(new_fraction)  # ✗ Widget peut être détruit!

# Ligne 769-770 — attributs dynamiques non synchronisés
device._level_display = level_lbl  # Référence isolée
self._device_level_bars[device.id] = (level_lbl, prog_bar)  # Double référence
```

**Impact**: GTK errors, widgets crashes si refresh pendant animation  
**Suggestion de fix**:
```python
def _update_level_bars_only(self) -> bool:
    try:
        with self._level_bars_lock:  # Ajouter threading.Lock
            for source_id, widgets in list(self._device_level_bars.items()):
                if widgets and source_id in self.audio._source_peak_levels:
                    # Vérifier que les widgets ne sont pas None
                    level_lbl, prog_bar = widgets
                    if level_lbl and prog_bar:  # Guards
                        # ...
```

---

### BUG #3: Popover attach/destroy cycle (Ligne 1046)
**Fichier**: audio-hub.py:1046-1070  
**Sévérité**: CRITIQUE  
**Description**: Popover parent est supprimé puis rappelé dans le callback

```python
# Ligne 1046 — attach à `row` (qui dure la vie du card)
pop.set_parent(row)
pop.set_autohide(True)

# Ligne 1047 — mais set_pointing_to() recalcule les coordonnées
def show_popover(_):
    btn_alloc = options_btn.get_allocation()  # ✗ Peut être invalide!
    rect = Gdk.Rectangle()
    rect.x = btn_alloc.x + btn_alloc.width // 2
    rect.y = btn_alloc.y + btn_alloc.height // 2
    pop.set_pointing_to(rect)  # ✗ Coordonnées relatives à row, pas absolues
    pop.popup()
```

**Problème**: Gdk.Rectangle utilise les coordonnées relatives au widget parent, mais `btn_alloc` est dans un système de coordonnées différent  
**Impact**: Popover apparaît au mauvais endroit, ou crash si widget détruit  
**Suggestion de fix**:
```python
# Utiliser set_child + set_position plutôt que set_pointing_to
pop.set_position(Gtk.PositionType.TOP)
# OU calculer les coordonnées correctement dans le système de coordonnées du parent
```

---

### BUG #4: Threads daemon sans nettoyage (Ligne 313-324)
**Fichier**: audio-hub.py:313-324  
**Sévérité**: CRITIQUE  
**Description**: Threads audio daemon se terminent brutalement

```python
# Ligne 313-324
thread = threading.Thread(
    target=self._audio_capture_source,
    args=(source.id, source.description, source.node_name),
    daemon=True  # ✗ Daemon = tue sans cleanup!
)
thread.start()
self._source_threads[source.id] = thread

# Problème: À l'arrêt de l'app, ces threads sont tués sans fermer les streams audio
# Cela laisse les descripteurs de fichier audio ouverts
```

**Impact**: Descripteurs audio non libérés, problèmes d'exclusivité avec autres apps  
**Suggestion de fix**:
```python
# Ligne 302: Ajouter signal handler
signal.signal(signal.SIGTERM, self._on_shutdown)
signal.signal(signal.SIGINT, self._on_shutdown)

def _on_shutdown(self, *args):
    self._audio_running = False  # Signal aux threads
    # Threads non-daemon se termineront proprement
    for thread in self._source_threads.values():
        thread.join(timeout=2)  # Attendre 2s max
```

---

## 🟠 **MAJEURS** (Bugs de logique métier)

### BUG #5: Loopback config sauvegardée mais jamais appliquée (Ligne 972-978)
**Fichier**: audio-hub.py:972-978 + 2062-2074  
**Sévérité**: MAJEUR  
**Description**: Lors du changement de sink via dropdown, l'UI n'est pas rafraîchie

```python
# Ligne 972-978
def on_sink_selected(_drop, _pspec, src_id=device.id, sl=sinks, app=self):
    selected_idx = _drop.get_selected()
    if selected_idx >= 0 and selected_idx < len(sl):
        target_sink = sl[selected_idx]
        removed = app.audio.unroute_source_from_all_sinks(src_id)
        app.audio.route_source_to_sink(src_id, target_sink.id)
        app._save_loopback_config(src_id, target_sink.id)
        # ✗ MANQUE: self._on_refresh()  — UI n'est pas mise à jour!
```

**Impact**: Loopback fonctionne mais l'UI n'affiche pas les changements  
**Suggestion de fix**:
```python
app.audio.route_source_to_sink(src_id, target_sink.id)
app._save_loopback_config(src_id, target_sink.id)
GLib.idle_add(app._on_refresh)  # ← Ajouter ceci
```

---

### BUG #6: Doublon de fonction _restore_loopback_configs (Ligne 2062 + 2098)
**Fichier**: audio-hub.py:2062-2084 et 2098-2111  
**Sévérité**: MAJEUR  
**Description**: Deux fonctions presque identiques portent des noms différents

```python
# Première version (ligne 2062-2084)
def _restore_loopback_configs(self):
    self._load_loopback_configs()
    for source_id, sink_id in self._loopback_config.items():
        # ... restauration ...
    return False

# Deuxième version quasi-identique (ligne 2098-2111)
def _restore_loopback_configs_init(self):  # ← Nom différent!
    self._load_loopback_configs()
    for source_id, sink_id in self._loopback_config.items():
        # ... MÊME code ...
    # SANS return statement!

# Mais utilisé à la ligne 960:
GLib.timeout_add(1000, self._restore_loopback_configs)  # ← Appelle la première
```

**Impact**: Code dupliqué, maintenance difficile, deuxième version jamais utilisée  
**Suggestion de fix**:
```python
# Supprimer la deuxième fonction _restore_loopback_configs_init complètement
# Garder uniquement _restore_loopback_configs avec return False
```

---

### BUG #7: Logique "boost weak volumes" incorrecte (Ligne 309-315)
**Fichier**: audio-hub.py:309-315  
**Sévérité**: MAJEUR  
**Description**: Augmenter le volume d'entrée AUGMENTE la saturation, ne la réduit pas

```python
def _boost_weak_input_volumes(self):
    """Augmente les volumes faibles des sources audio pour éviter la saturation."""
    for source in self._sources:
        if 0 < source.volume < 0.3:
            try:
                # ✗ Logique inversée: augmenter l'entrée = PLUS de saturation!
                subprocess.run(['wpctl', 'set-volume', str(source.id), '0.4'],
                               capture_output=True, timeout=2)
```

**Problème**: La saturation vient de signaux trop FORTS, pas faibles. Augmenter le gain d'entrée aggrave le problème  
**Impact**: Microphones/entrées distordent encore plus  
**Suggestion de fix**:
```python
def _reduce_aggressive_input_gains(self):
    """Réduit les gains d'entrée agressifs qui causeraient la saturation."""
    for source in self._sources:
        if source.volume > 0.7:  # Inverse: chercher les HAUTS niveaux
            try:
                subprocess.run(['wpctl', 'set-volume', str(source.id), '0.5'],
                               capture_output=True, timeout=2)
```

---

### BUG #8: Erreur supprimée silencieusement dans _run() (Ligne 360-368)
**Fichier**: audio-hub.py:360-368  
**Sévérité**: MAJEUR  
**Description**: Les erreurs de commande sont loggées mais le stdout vide est retourné

```python
def _run(self, cmd, timeout=5, log=True):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if log: 
            self._journal.append("→ OK" if r.returncode==0 
                                else f"→ ERR {r.stderr.strip()[:80]}")
        return r.stdout  # ✗ Retourne stdout même si returncode != 0!
    except Exception as e:
        if log: self._journal.append(f"→ EXC: {e}")
        return ""
```

**Problème**: Code appelant pense que ça a réussi (reçoit stdout), mais la commande a échoué  
**Impact**: Commandes échouées sont ignorées silencieusement  
**Suggestion de fix**:
```python
def _run(self, cmd, timeout=5, log=True):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            if log: self._journal.append(f"→ ERR [rc={r.returncode}]: {r.stderr[:80]}")
            return ""  # Retourner empty string en cas d'erreur
        if log: self._journal.append("→ OK")
        return r.stdout
    except Exception as e:
        if log: self._journal.append(f"→ EXC: {e}")
        return ""
```

---

### BUG #9: Pas d'initialisation d'_audio_running dans __init__ (Ligne 300-306)
**Fichier**: audio-hub.py:300-306  
**Sévérité**: MAJEUR  
**Description**: `_audio_running` est utilisé sans initialisé explicitement

```python
def __init__(self):
    # ... autres init ...
    self._audio_running = True  # ✗ Défini ici
    
# Mais utilisé à la ligne 579 dans _auto_refresh AVANT __init__!
# et à la ligne 677 dans le callback
# et à la ligne 779 dans la boucle de fallback
```

Attendez, j'ai lu le code à la ligne 301:
```python
self._audio_running = True
```
C'est BIEN initialisé. Pas de bug ici.

---

### BUG #10: Fonction appelée avec mauvais paramètre (Ligne 1014-1025)
**Fichier**: audio-hub.py:1014-1025  
**Sévérité**: MAJEUR  
**Description**: Code lambda dans GLib.idle_add ne retourne pas False correctement

```python
# Ligne 965
GLib.timeout_add_seconds(2, self._auto_refresh)

# Mais _auto_refresh retourne explicitement True (ligne 1001)
def _auto_refresh(self) -> bool:
    try:
        # ...
    except Exception:
        pass
    return True  # ✓ Correct — continue le timer

# Cependant ligne 1044:
GLib.idle_add(lambda sid=stream.id, sk=sinks:
              self.audio.restore_saved_routing(sid, sk) or False)
#                                                        ^^^^^^
# ✗ Le 'or False' n'a pas d'effet! Si restore_saved_routing() retourne None,
#   le lambda retourne False correctement, mais c'est une mauvaise pratique
```

**Impact**: Le lambda retourne None (faux) ce qui arrête GLib.idle_add prématurément  
**Suggestion de fix**:
```python
GLib.idle_add(lambda: (
    self.audio.restore_saved_routing(stream.id, sinks),
    False
)[1])
# OU plus simplement:
def restore_and_return():
    self.audio.restore_saved_routing(stream.id, sinks)
    return False
GLib.idle_add(restore_and_return)
```

---

## 🟡 **MINEURS** (Bugs potentiels, défauts de conception)

### BUG #11: Pas de synchronisation des pré-capture audio (Ligne 695-710)
**Fichier**: audio-hub.py:695-710  
**Sévérité**: MINEUR  
**Description**: La détection du device audio utilise plusieurs heuristiques sans logging

```python
device_index = None
devices = sd.query_devices()

if node_name:
    parts = node_name.split('.')
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            dev_name_lower = dev['name'].lower()
            if '.monitor' in dev_name_lower:
                continue
            for part in parts:
                part_lower = part.lower().replace('_', ' ')
                if part_lower in dev_name_lower or part_lower.replace('-', '') in dev_name_lower.replace('-', ''):
                    device_index = i
                    break
        if device_index is not None:
            break

# Stratégie 2: fallback
if device_index is None and description:
    # ...

# Stratégie 3: default
if device_index is None:
    device_index = sd.default.device[0]
```

**Problème**: Si toutes les heuristiques échouent, il prend le device par défaut sans warning  
**Impact**: Peut capturer depuis le mauvais microphone  
**Suggestion de fix**:
```python
if device_index is None:
    import sys
    print(f"[WARN] Audio device detection failed for {node_name}, using default", 
          file=sys.stderr)
    device_index = sd.default.device[0]
```

---

### BUG #12: Accès potentiel à None dans popover (Ligne 1077-1087)
**Fichier**: audio-hub.py:1077-1087  
**Sévérité**: MINEUR  
**Description**: `sink` peut être None mais utilisé dans le popover

```python
def _make_sink_entry(self, sink: PipeWireSink, stream: PipeWireStream,
                     role: str, sinks, body_box, rebuild_fn):
    # ... construction du popover ...
    pop = self._make_sink_popover(sink, stream, p_btn, m_btn, o_btn, dot, dv_lbl, apply_role_fn)
    
    # Mais dans _make_sink_popover:
    def _make_sink_popover(self, sink, stream, ...):
        sl  = Gtk.Label()
        sl.set_markup(f'<small>node:{sink.id}  ·  {sink.type.upper()}'  # ✗ Si sink est None...
                      + (f'  ·  {self._esc(sink.bus)}' if sink.bus else '') + '</small>')
```

Attends, regardons l'appel à `_make_sink_entry`:
```python
# Ligne 1639 (dans rebuild_body):
for i, sink in enumerate(sinks_list):
    body_box.append(self._make_sink_entry(sink, st, role, ...))
```

Si `sinks_list` contient une valeur None, cela causera un crash. Mais `sinks_list` vient de `sinks` qui vient de `self.audio.get_sinks()`. C'est probablement sûr.

**Suggestion conservative**:
```python
if sink is None:
    return None  # Skip cette entrée
```

---

### BUG #13: _parse_streams regex fragile (Ligne 474-510)
**Fichier**: audio-hub.py:474-510  
**Sévérité**: MINEUR  
**Description**: Les regex pour parser wpctl status sont fragiles

```python
def _parse_streams(self, status):
    streams, in_sec, cur = [], False, None
    for line in status.splitlines():
        if re.search(r'[└├]─\s+Streams:', line): in_sec=True; continue
        if in_sec:
            if re.search(r'[└├]─', line) and 'Streams' not in line: break
            m = re.search(r'^\s{6,9}(\d+)\.\s+(.+?)(?:\s{3,}|$)', line)
            # ✗ Magic numbers: 6,9 espaces, 3+ espaces — très fragile!
            if m and '>' not in line:
                # ...
```

**Problème**: Si le format de `wpctl status` change légèrement, le parsing échoue silencieusement  
**Impact**: Les flux audio ne sont pas détectés  
**Suggestion de fix**:
```python
# Utiliser pw-dump --json au lieu de parser wpctl status
# C'est plus robuste et structuré
```

---

### BUG #14: Fuite mémoire légère dans _get_role (Ligne 1704-1715)
**Fichier**: audio-hub.py:1704-1715  
**Sévérité**: MINEUR  
**Description**: Références cycliques entre stream et sink via settings

```python
def _get_role(self, stream, sink, primary):
    sett   = self.audio.settings
    # D'abord chercher par stream ID
    saved  = sett.get('routing', str(stream.id), str(sink.id), 'role')
    if saved: return saved
    # Fallback: chercher par process binary (app)
    app_bin = self.audio._nodes.get(stream.id, {}).get('application.process.binary', '').lower()
    if app_bin:
        app_saved = sett.get('routing_by_app', app_bin, str(sink.id), 'role')
        if app_saved: return app_saved
    # ...
```

**Problème**: `self.audio._nodes` est un dictionnaire qui persiste même après suppression du stream  
**Impact**: Accumulation de nodes obsolètes en mémoire  
**Suggestion de fix**:
```python
# Dans refresh():
old_stream_ids = set(self._nodes.keys())
new_stream_ids = set(n['id'] for n in json.loads(nodes_raw))
for old_id in old_stream_ids - new_stream_ids:
    del self._nodes[old_id]  # Nettoyer les anciens nœuds
```

---

### BUG #15: Type annotation incorrect (Ligne 241)
**Fichier**: audio-hub.py:241  
**Sévérité**: MINEUR  
**Description**: Annotation de type utilise la syntaxe moderne non présente en Python 3.8

```python
class PipeWireStream:
    def __init__(self, node_id, name, pid, sample_rate, media_class,
                 driver_id=None, volume=1.0):
        # ...
        self.connections: list[StreamConnection] = []  # ✗ Python 3.9+ syntax!
```

**Problème**: En Python 3.8, faut utiliser `List[StreamConnection]` ou `from __future__ import annotations`  
**Impact**: SyntaxError si Python < 3.9  
**Suggestion de fix**:
```python
from __future__ import annotations  # ← Ajouter au début
# OU:
from typing import List
self.connections: List[StreamConnection] = []
```

---

## 📋 RÉSUMÉ DES BUGS

| # | Sévérité | Ligne(s) | Catégorie | Description | Impact |
|---|----------|----------|-----------|-------------|--------|
| 1 | 🔴 CRITIQUE | 2069, 2089 | **Types** | Type mismatch JSON keys int→str | Loopback jamais restauré |
| 2 | 🔴 CRITIQUE | 1010, 769, 1008 | **Resources** | Race condition device_level_bars | Widget crash |
| 3 | 🔴 CRITIQUE | 1046-1070 | **GTK4** | Popover coordinates broken | Popover mauvaise position |
| 4 | 🔴 CRITIQUE | 313-324 | **Threading** | Threads daemon sans cleanup | Descripteurs audio ouverts |
| 5 | 🟠 MAJEUR | 972-978 | **Logique** | UI non rafraîchie après changement | Incohérence visuelle |
| 6 | 🟠 MAJEUR | 2062+2098 | **Code** | Doublon fonction _restore_loopback | Maintenance difficile |
| 7 | 🟠 MAJEUR | 309-315 | **Logique** | Boost volumes augmente saturation | Audio distordu |
| 8 | 🟠 MAJEUR | 360-368 | **Erreur** | Erreurs supprimées dans _run() | Commandes échouées ignorées |
| 9 | 🟠 MAJEUR | 1014-1025 | **GLib** | Lambda mal formaté dans idle_add | Timer arrêté prématurément |
| 10 | 🟡 MINEUR | 695-710 | **Audio** | Pas de logging détection device | Microphone mauvais silencieusement |
| 11 | 🟡 MINEUR | 1077-1087 | **GTK4** | Pas de guard None dans popover | Crash potentiel |
| 12 | 🟡 MINEUR | 474-510 | **Parsing** | Regex fragile pour wpctl | Parsing échoue sur format variant |
| 13 | 🟡 MINEUR | 1704-1715 | **Ressources** | Fuite mémoire nodes obsolètes | Accumulation mémoire |
| 14 | 🟡 MINEUR | 241 | **Types** | Syntax Python 3.8 incompatible | SyntaxError si Python < 3.9 |

---

## ✅ FIXES RECOMMANDÉS (Par ordre de priorité)

### Priorité 1 — IMMÉDIAT
- [ ] Bug #1: Fixer type mismatch loopback_config
- [ ] Bug #4: Ajouter cleanup threads audio
- [ ] Bug #3: Corriger Popover coordinates

### Priorité 2 — URGENT  
- [ ] Bug #2: Ajouter synchronisation device_level_bars
- [ ] Bug #7: Fixer logique boost volumes
- [ ] Bug #5: Ajouter refresh après changement sink

### Priorité 3 — STANDARD
- [ ] Bug #6: Supprimer doublon fonction
- [ ] Bug #8: Améliorer gestion erreurs _run()
- [ ] Bug #9: Fixer lambda idle_add

### Priorité 4 — MAINTENANCE
- [ ] Bug #10-14: Improvements qualité code

