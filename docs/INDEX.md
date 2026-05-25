# Index Documentation LAM

Navigation rapide de toute la documentation Linux Audio Manager.

---

## 📚 Documentation générale

| Document | Audience | Contenu |
|----------|----------|---------|
| [README.md](../README.md) | Everyone | Overview projet, features, use cases, quick start |
| [CHANGELOG.md](../CHANGELOG.md) | Developers | Historique versions et changements |

---

## 🎯 Planification & Roadmap

| Document | Audience | Contenu |
|----------|----------|---------|
| [roadmap.md](roadmap.md) | Product, Dev | Vision v0.1-v1.0+, features Partie 1-2, jalons, timeline |
| [parte2-plan.md](partie2-plan.md) | Developers | Spécifications détaillées 5 sections Partie 2, code examples |
| [V02-QUICKSTART.md](V02-QUICKSTART.md) | Developers | Plan implémentation v0.2, code skeletons, phases, timeline |

---

## 🏗️ Architecture & Design

| Document | Audience | Contenu |
|----------|----------|---------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Architects, Developers | Design modulaire, domaines responsabilité, modules v0.1-v1.0+ |
| [DECISIONS.md](DECISIONS.md) | Architects | 7 décisions techniques with options analysis (database, UI, DSP, macros, etc.) |
| [gnome-structure.md](gnome-structure.md) | Developers | Arborescence GNOME, build system (Meson), packaging |
| [dependencies.md](dependencies.md) | Developers | Liste dépendances, version requirements, optional packages |

---

## 🔧 Configuration & Build

| Document | Audience | Contenu |
|----------|----------|---------|
| [changelog.md](changelog.md) | Contributors | Format changelog, règles, exemples |
| [../Makefile](../Makefile) | Developers | Build targets: `make run`, `make check`, `make clean` |

---

## 📖 Usage Documentation (Future)

*(À créer pour v0.2)*

- `USER_GUIDE.md` — Guide utilisateur (screenshots, workflows)
- `ADMIN_GUIDE.md` — Guide administrateur (installation, config systéme)
- `TROUBLESHOOTING.md` — FAQ + solutions problèmes courants
- `KEYBOARD_SHORTCUTS.md` — Listes raccourcis clavier

---

## 👨‍💻 Developer Documentation

### Par domaine

#### Audio Backend
- [src/audio.py](../src/audio.py) — PipeWire interface (v0.1)
  - Get audio state, set volume, toggle mute, link creation
  - New in v0.2+: Extended API pour monitoring, latency, advanced routing

#### Configuration & Persistence
- [src/config.py](../src/config.py) — Settings persistence (v0.1)
  - Load/save settings.json, last sink, routing state
  - New in v0.2+: Rules, profiles, zones, scenarios

#### UI Framework
- [src/window.py](../src/window.py) — GTK4/GTK3 UI (v0.1)
  - MainWindow GTK4 with libadwaita
  - MainWindow GTK3 fallback
  - New in v0.2+: Rules Manager, Zones Organizer, History, Diagnostics tabs

#### Application Entry
- [src/main.py](../src/main.py) — App startup (v0.1)
  - GTK4/GTK3 auto-detection
  - Config restoration
  - Event loop management

### New Modules v0.2+
- `src/audit_log.py` — SQLite historique
- `src/state_manager.py` — Atomic state snapshots
- `src/undo_redo.py` — Undo/redo stack (50 actions)
- `src/routing_rules.py` — Rules engine (matcher + apply)
- `src/hardware_profiles.py` — Hardware profiles + hotplug
- `src/audio_zones.py` — Zone grouping + volume balancing

### New Modules v0.3+
- `src/equalizer.py` — EQ 5/10/31 bandes
- `src/normalizer.py` — Normalisation dynamique LUFS
- `src/scenarios.py` — Scénarios + triggers
- `src/hotkeys.py` — Raccourcis clavier globaux
- `src/hotplug.py` — Hot-plugging robuste + crossfade

### Testing
- `tests/test_*.py` — Unit tests (pytest)
- CI/CD via GitHub Actions (future)

---

## 🗺️ Lecture Recommandée

### Pour comprendre le projet (1h)
1. Lire [README.md](../README.md)
2. Consulter [roadmap.md](roadmap.md) sections v0.1 ✅
3. Survoler [ARCHITECTURE.md](ARCHITECTURE.md) (5 min)

### Pour implémenter v0.2 (2h)
1. Lire [V02-QUICKSTART.md](V02-QUICKSTART.md) en entier
2. Consulter [ARCHITECTURE.md](ARCHITECTURE.md) sections "Domaines de responsabilité"
3. Vérifier [DECISIONS.md](DECISIONS.md) pour décisions concernées

### Pour contribuer (expertise domain)
1. Lire [ARCHITECTURE.md](ARCHITECTURE.md) section concernée
2. Consulter code existant (`src/*.py`)
3. Écrire tests (TDD)
4. Référencer [changelog.md](changelog.md) pour format

### Pour faire PR/review code
1. Vérifier [gnome-structure.md](gnome-structure.md) style
2. Lire [changelog.md](changelog.md) description
3. Vérifier tests passent (`pytest`)
4. Vérifier syntax (`make check`)

---

## 📊 État Documentation

### ✅ Complète
- Roadmap (v0.1-v1.0+)
- Architecture générale (v0.1-v0.4)
- Décisions techniques
- Plan v0.2 détaillé
- GNOME structure

### ⏳ In Progress
- User guide (attente v0.2 implémentation)
- Troubleshooting (attente retours utilisateurs)
- API docs (attente modules v0.2+)

### 📋 To Do
- Admin guide (post v0.3)
- Mobile app guide (post v1.0)
- Plugin API docs (v1.0+)
- Community contributions guide (v0.3+)

---

## 🔗 Ressources Externes

### PipeWire
- [PipeWire docs](https://docs.pipewire.org/)
- [PipeWire WirePlumber](https://pipewire.pages.freedesktop.org/wireplumber/)
- [wpctl man page](https://man.archlinux.org/man/wpctl.1.en)

### GTK & GNOME
- [GTK4 documentation](https://docs.gtk.org/gtk4/)
- [libadwaita](https://gnome.pages.gitlab.gnome.org/libadwaita/)
- [GNOME Guidelines](https://developer.gnome.org/guidelines/)

### Development
- [Python 3.8+](https://www.python.org/)
- [pytest](https://docs.pytest.org/)
- [Git workflow](https://git-scm.com/)

---

## ❓ FAQ Documentation

**Q: Par où commencer comme développeur ?**  
A: Lire README → V02-QUICKSTART → ARCHITECTURE, puis implémenter Phase 1.1

**Q: Où est le code ?**  
A: `src/` pour code, `tests/` pour tests, `docs/` pour documentation

**Q: Comment contribuer ?**  
A: Fork → branch feature → code + tests → référencer changelog.md → PR

**Q: Quand v0.2 sera-t-elle prête ?**  
A: 7 semaines estimées (1-2 mois) dépendant contributeurs

**Q: Puis-je modifier les décisions architecturales ?**  
A: Oui, feedback bienvenu. Voir [DECISIONS.md](DECISIONS.md) section justification

**Q: Comment signaler un bug ?**  
A: GitHub issues avec reproduction steps + logs

**Q: Comment demander une feature ?**  
A: Consulter [parte2-plan.md](partie2-plan.md) d'abord, puis GitHub discussion

---

## 📞 Contact & Support

- **Bug reports** : GitHub Issues
- **Feature requests** : GitHub Discussions
- **Documentation questions** : GitHub Issues tag `docs`
- **Code review** : GitHub Pull Requests

---

**Last updated**: v0.1.0 (mai 2026)  
**Maintainer**: Community
