# Améliorations Multi-Sortie (v0.1.x)

## Vue d'ensemble

La fonctionnalité **multi-sortie** (duplication de flux audio vers plusieurs périphériques simultanément) a été améliorée avec une interface plus intuitive, un meilleur contrôle, et une gestion avancée des connexions.

---

## Changements v0.1 → Amélioré

### Avant : Interface minimale
```
┌─ Multi-sortie simple
│  ├─ "Dupliquer les flux actifs"
│  └─ [Bouton] "Dupliquer maintenant"
│     → Duplique TOUS les flux vers TOUS les sinks
│     → Pas de sélectivité
│     → Pas de visualisation des liens
```

### Après : Interface complète et ergonomique
```
┌─ Multi-sortie avancée
│
├─ Section 1 : Sélection des périphériques
│  ├─ ☑ Casque USB (vol: 85%)
│  ├─ ☑ Enceintes (vol: 100%)
│  └─ ☐ Micro (vol: 50%)
│
├─ Section 2 : Actions
│  ├─ [Dupliquer sélection] ← Seulement sinks cochés
│  └─ [Effacer tous les liens] ← Supprimer tout
│
└─ Section 3 : Connexions actives
   ├─ Spotify → Casque USB [✕]
   ├─ Spotify → Enceintes [✕]
   ├─ Firefox → Enceintes [✕]
   └─ ...
```

---

## Fonctionnalités nouvelles

### 1️⃣ Sélection des sinks (Checkboxes)
**Avant** : Tous les sinks utilisés, pas de choix
**Après** : Cocher/décocher les sinks désirés avant duplication

```python
# Nouvelle logique
selected_sink_ids = [sid for sid, cb in self._sink_checkboxes.items() 
                     if cb.get_active()]
# Dupliquer seulement vers sinks sélectionnés
```

✅ **Bénéfices** :
- Contrôle granulaire
- Évite duplications non désirées
- Multi-sortie "intelligente"

---

### 2️⃣ Affichage des connexions actives
**Avant** : Aucune visualisation des liens créés
**Après** : Liste complète avec suppression individuelle

```
Connexions actives (5)
├─ VLC → Casque USB [✕]
├─ Discord → USB Headset [✕]
├─ Firefox → Enceintes [✕]
└─ ...
```

✅ **Bénéfices** :
- Transparence sur les routages actuels
- Détection rapide de connexions non désirées
- Débuggage facile

---

### 3️⃣ Suppression individuelle de liens
**Avant** : Pas de moyen de supprimer un lien spécifique
**Après** : Bouton [✕] sur chaque connexion + "Effacer tous"

```python
def _on_remove_link(self, button, link_id: int):
    """Supprime une connexion spécifique."""
    if audio.disconnect_link(link_id):
        self._set_status(f"✅ Connexion {link_id} supprimée.")
        self._on_refresh()
```

✅ **Bénéfices** :
- Micro-gestion des routages
- Plus flexible que "tout ou rien"
- Moins de clics pour corriger

---

### 4️⃣ Persistance des préférences
**Avant** : Pas de mémoire des sinks préférés
**Après** : Mémorise les derniers sinks sélectionnés

```python
# Sauvegarder préférences
config.save_preferred_sinks([42, 45, 50])

# Restaurer au prochain démarrage
preferred = config.get_preferred_sinks()  # [42, 45, 50]
```

✅ **Bénéfices** :
- Workflow plus rapide (pas à resélectionner)
- UX fluide

---

### 5️⃣ Nouveau contrôle audio.py
**Nouvelles fonctions** :

```python
# Supprimer une connexion
disconnect_link(link_id: int) -> bool

# Obtenir tous les liens d'un flux
get_stream_links(stream_node_id: int) -> list[AudioLink]
```

✅ **Bénéfices** :
- API complète pour manipulation links
- Capable de gestion avancée v0.2+

---

## Améliorations UX/Feedback

### Icônes & Emojis statut

| Statut | Icône | Message |
|--------|-------|---------|
| ✅ Succès | ✅ | "Duplication réussie" |
| ❌ Erreur | ❌ | "Aucun flux audio actif" |
| ⚠️ Avertissement | ⚠️ | "Sélectionnez au least un périphérique" |
| ℹ️ Info | ℹ️ | "Aucune connexion à supprimer" |

### Flèche routage
Chaque connexion affiche direction claire :
- `Spotify → Casque USB`
- `Firefox → Enceintes`
- `Zoom → USB Headset`

---

## Technique : Architecture

### Backend (audio.py)
```python
class AudioLink:
    link_id: int              # ID PipeWire unique
    source_node_id: int       # App/stream
    dest_node_id: int         # Sink/device
    source_name: str
    dest_name: str
    active: bool              # Lien fonctionnel?

# Opérations
duplicate_stream_to_sink(stream_id, sink_id) → bool    # Créer lien
disconnect_link(link_id) → bool                        # Supprimer lien
get_audio_links() → list[AudioLink]                    # Lister tous liens
get_stream_links(stream_id) → list[AudioLink]          # Liens pour 1 flux
```

### Frontend (window.py - Adwaita)
```python
_build_multi_output_group()           # UI globale
  ├─ Selection checkboxes (sinks)
  ├─ Action buttons
  └─ _build_active_links_section()    # Affichage liens
      └─ _on_remove_link() callback
```

### Frontend (window.py - GTK3)
```python
_build_multi_output_group_gtk3()              # UI GTK3
  ├─ Selection checkboxes (sinks)
  ├─ Action buttons
  └─ _build_active_links_section_gtk3()      # Affichage liens
```

### Config (config.py)
```python
get_preferred_sinks() → list[int]      # Charger prefs
save_preferred_sinks(list[int]) → None # Sauvegarder prefs
```

---

## Cas d'usage améliorés

### Exemple 1 : Streaming multicanal
**Scénario** : Avoir Discord en casque, VLC en enceintes principales uniquement

**Avant** : Dupliquer tout, puis manuellement retirer connexions non désirées ❌
**Après** : ☑ Casque, ☐ Enceintes, ☑ Dupliquer sélection ✅

### Exemple 2 : Débugage routage
**Scénario** : "Pourquoi mon son sort deux fois?"

**Avant** : Aucune visibilité, essai/erreur ❌
**Après** : Voir exactement les connexions actives → Cliquer [✕] pour supprimer ✅

### Exemple 3 : Workflow quotidien
**Scénario** : Matin = Casque/Enceintes, Après-midi = Enceintes uniquement

**Avant** : Resélectionner manuellement à chaque fois ❌
**Après** : Préférences mémorisées, coches rappelées automatiquement ✅

---

## Tests & Validation

### ✅ Testé sur
- [x] Adwaita (GTK4) avec libadwaita
- [x] GTK3 fallback
- [x] PipeWire réel (pw-dump + wpctl)
- [x] Multi flux, multi sinks

### ✅ Vérifications
- [x] Syntaxe Python (`make check` 100%)
- [x] Interface se lance sans erreur
- [x] Checkboxes fonctionnent
- [x] Liens créés correctement (wpctl link)
- [x] Liens supprimés correctement (wpctl disconnect)
- [x] Persistance sinks préférés (config.json)
- [x] Status bar met à jour

---

## Backward Compatibility

✅ **Entièrement compatible v0.1.0**
- Pas de breaking changes
- Code existant fonctionne
- Nouvelle interface = amélioration transparente

---

## Roadmap Partie 2 (v0.2+)

Ces améliorations **jettent les bases** pour v0.2 :

1. **Zone Audio (v0.2)**
   - Grouper automatiquement sinks par zone (Salon, Chambre)
   - Multi-sortie → par zone, pas par sink individuel

2. **Routage Intelligent (v0.2)**
   - Règles : "VLC → toujours vers Enceintes"
   - Automatisation basée sur patterns

3. **Hot-plugging (v0.3)**
   - Brancher casque → auto-switch
   - Utilise infrastructure connexions/liens établie ici

4. **Graphe Visuel (v0.4)**
   - Patchbay-style drag-drop
   - Basé sur `get_audio_links()` et gestion connexions

---

## Fichiers modifiés

```
src/
├── audio.py
│   ├── NEW: disconnect_link()
│   └── NEW: get_stream_links()
├── window.py
│   ├── IMPROVED: _build_multi_output_group() (Adwaita)
│   ├── NEW: _build_active_links_section()
│   ├── NEW: _on_duplicate_selected_streams()
│   ├── NEW: _on_clear_all_links()
│   ├── NEW: _on_remove_link()
│   ├── IMPROVED: _build_multi_output_group_gtk3() (GTK3)
│   ├── NEW: _build_active_links_section_gtk3()
│   ├── NEW: _on_duplicate_selected_streams_gtk3()
│   ├── NEW: _on_clear_all_links_gtk3()
│   └── NEW: _on_remove_link_gtk3()
└── config.py
    ├── NEW: get_preferred_sinks()
    └── NEW: save_preferred_sinks()
```

---

## Statut v0.1 Partie 1

| Section | Avant | Après |
|---------|-------|-------|
| Interface GNOME | ✅ | ✅ Enrichie |
| Contrôle audio | ✅ | ✅ Stable |
| Routage de base | ✅ | ✅ Stable |
| **Multi-sortie** | ✅ Basique | ✅✅ **Avancée** |
| Persistance | ✅ | ✅ Enrichie |

---

## Conclusion

La **multi-sortie** est passée de feature minimale à **outil professionnel** :
- Interface intuitive (checkboxes, affichage liens)
- Contrôle fin (sélection, suppression individuelle)
- UX améliorée (feedback, icônes, persistance)
- Fondations solides pour v0.2+ (zones, routage, graphs)

🎯 **v0.1.0 Partie 1 : 100% complète et enrichie** 🎯
