# Linux Audio Manager - Project Index

**Version**: 0.1.0 ✅  
**Status**: GNOME-compliant (9/10) - Ready for Flathub  
**Date**: 25 mai 2026

---

## 📁 Quick Navigation

### 📖 Documentation
- **[README.md](README.md)** - Start here! Overview + quick start
- **[docs/roadmap.md](docs/roadmap.md)** - v0.1.0 complete, v0.2+ planning
- **[docs/partie2-plan.md](docs/partie2-plan.md)** - Detailed roadmap for features

### 🚀 Getting Started
- **[QUICK_COMMANDS.sh](QUICK_COMMANDS.sh)** - Copy-paste commands for Flathub submission
- **[Makefile](Makefile)** - Build & run: `make` or `make run`

### 📦 Distribution
- **[docs/flathub/](docs/flathub/)** - Flathub submission docs
  - `FLATHUB_SUBMISSION_READY.md` - Step-by-step guide
  - `FLATHUB_SUBMISSION_PLAN.md` - Detailed phases
  - `FLATHUB_SUBMISSION.md` - Overview
- **[io.github.linux-audio-manager.yml](io.github.linux-audio-manager.yml)** - Flatpak manifest
- **[flathub.json](flathub.json)** - Flathub configuration

### 🛠️ Development
- **[src/](src/)** - Python source code
  - `main.py` - Application entry point
  - `window.py` - GTK4/libadwaita UI
  - `audio.py` - PipeWire backend
  - `config.py` - Settings persistence
- **[data/](data/)** - Desktop + metadata files
  - `.desktop` file (GNOME integration)
  - `.metainfo.xml` (AppStream)
- **[debian/](debian/)** - DEB package files

### 📋 Build & Installation
```bash
# Run locally
make

# Build DEB package
./prepare-submission.sh
# Then: dpkg -i build/linux-audio-manager_0.1.0_all.deb

# Build Flatpak
flatpak-builder --user --install build io.github.linux-audio-manager.yml
```

### 📚 Archived Documentation
- **[docs/archive/](docs/archive/)** - Old technical docs, reference material

---

## 🎯 Current Status

### ✅ COMPLETED (v0.1.0)
- ✅ GNOME-compliant UI (GTK4/libadwaita)
- ✅ PipeWire integration (real-time monitoring)
- ✅ Audio control (master volume, per-app, routing)
- ✅ Persistent configuration (~/.config/)
- ✅ i18n support (FR + EN)
- ✅ DEB package ready
- ✅ Flatpak manifest ready
- ✅ GitHub repository: https://github.com/natsenack/linux-audio-manager

### ⏳ NEXT STEPS (Flathub)
1. **Create Flathub issue** → https://github.com/flathub/flathub/issues/new?template=new_app.yml
   - Form fields in `docs/flathub/FLATHUB_SUBMISSION_READY.md`
2. **Wait for Flathub bot** → Creates repo (~24h)
3. **Push manifest** → Commands in `QUICK_COMMANDS.sh`
4. **Validation & publication** → ~3 days total

---

## 📊 Project Structure

```
linux-audio-manager/
├── README.md                          # Main documentation
├── LICENSE                            # GPL-3.0-or-later
├── Makefile                           # Build commands
├── pyproject.toml                     # Python packaging
│
├── src/                               # Application code
│   ├── __init__.py                    # App metadata
│   ├── main.py                        # Entry point
│   ├── window.py                      # GTK4 UI
│   ├── audio.py                       # PipeWire backend
│   └── config.py                      # Settings
│
├── data/                              # GNOME integration
│   ├── io.github.linux-audio-manager.desktop
│   └── io.github.linux-audio-manager.metainfo.xml
│
├── docs/                              # Documentation
│   ├── roadmap.md                     # Feature roadmap
│   ├── partie2-plan.md                # Detailed v0.2+ plan
│   ├── INDEX.md                       # Docs index
│   ├── flathub/                       # Submission docs
│   │   ├── FLATHUB_SUBMISSION_READY.md
│   │   ├── FLATHUB_SUBMISSION_PLAN.md
│   │   └── FLATHUB_SUBMISSION.md
│   └── archive/                       # Old reference docs
│
├── debian/                            # DEB package
│   ├── control
│   ├── rules
│   ├── compat
│   └── deb-builder.py
│
├── po/                                # Translations (i18n)
│   ├── LINGUAS
│   ├── linux-audio-manager.pot
│   └── fr.po
│
└── scripts/
    ├── build-flatpak.sh               # Flatpak build
    ├── prepare-submission.sh           # Pre-submit checks
    ├── submit-flathub.sh              # Submission workflow
    └── QUICK_COMMANDS.sh              # Copy-paste commands
```

---

## 🔧 Useful Commands

```bash
# Run application
make

# Check for errors
make check

# Build DEB
./prepare-submission.sh

# Quick Flathub commands
cat QUICK_COMMANDS.sh

# View roadmap
cat docs/roadmap.md
```

---

## 🤝 Contributing

See [README.md](README.md) for contribution guidelines.

---

## 📞 Support

- GitHub Issues: https://github.com/natsenack/linux-audio-manager/issues
- GNOME Help: https://help.gnome.org/
- PipeWire Docs: https://pipewire.org/

---

**Last Updated**: 25 mai 2026  
**Maintainer**: @natsenack  
**License**: GPL-3.0-or-later
