# Installation Guide - Linux Audio Manager

**Current Version**: 0.1.0  
**License**: GPL-3.0-or-later

---

## Option 1: Flathub (Recommended - Coming Soon ⏳)

```bash
# Install
flatpak install flathub io.github.linux-audio-manager

# Run
flatpak run io.github.linux-audio-manager
```

**Status**: Submitted to Flathub, awaiting publication (~3 days)

---

## Option 2: DEB Package (Debian/Ubuntu)

### Requirements
- Ubuntu 20.04+ or Debian Bookworm+
- `python3 >= 3.8`
- `gir1.2-gtk-4.0` (GTK4 bindings)
- `gir1.2-adwaita-1` (libadwaita bindings)
- `pipewire` (audio server)
- `wireplumber` (PipeWire policy)

### Install from DEB

```bash
# Download the DEB
wget https://github.com/natsenack/linux-audio-manager/releases/download/v0.1.0/linux-audio-manager_0.1.0_all.deb

# Install dependencies
sudo apt-get update
sudo apt-get install python3 gir1.2-gtk-4.0 gir1.2-adwaita-1 pipewire wireplumber

# Install the package
sudo dpkg -i linux-audio-manager_0.1.0_all.deb

# Verify installation
linux-audio-manager --help
```

### Run
```bash
# From terminal
linux-audio-manager

# From GNOME Applications menu
# Search: "Linux Audio Manager"
```

---

## Option 3: From Source

### Requirements
- Python 3.8+
- GTK 4.0+
- libadwaita 1.0+
- PipeWire
- WirePlumber

### Install

```bash
# Clone repository
git clone https://github.com/natsenack/linux-audio-manager.git
cd linux-audio-manager

# Install dependencies (Ubuntu/Debian)
sudo apt-get install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adwaita-1 \
                     pipewire wireplumber libgtk-4-dev libadwaita-1-dev

# Run directly
python3 -m src.main

# Or use Makefile
make run
```

---

## Configuration

Settings are stored in:
```
~/.config/linux-audio-manager/settings.json
```

**Do not edit manually** - Use the GUI to configure.

---

## Troubleshooting

### App won't start
```bash
# Check dependencies
python3 -c "import gi; gi.require_version('Gtk', '4.0'); print('GTK4: OK')"
python3 -c "import gi; gi.require_version('Adw', '1'); print('Adwaita: OK')"

# Check PipeWire
pw-cli info

# Run with debug
python3 -m src.main 2>&1 | grep -i error
```

### No audio devices detected
```bash
# Verify PipeWire is running
systemctl --user status pipewire

# List devices
pw-dump | grep -i "sink\|source"

# Restart PipeWire if needed
systemctl --user restart pipewire wireplumber
```

### Missing sounds after closing app
This is **intentional**. Audio routings persist to preserve your setup.

---

## Uninstall

### From DEB
```bash
sudo dpkg -r linux-audio-manager
```

### From Flatpak
```bash
flatpak uninstall io.github.linux-audio-manager
```

### From Source
```bash
rm -rf ~/linux-audio-manager
```

---

## Next Steps

1. **Open the app** → Check volumes and devices load correctly
2. **Read [README.md](README.md)** → Feature overview
3. **Check [docs/roadmap.md](docs/roadmap.md)** → Planned features
4. **Report issues** → https://github.com/natsenack/linux-audio-manager/issues

---

**Need Help?** Check [PROJECT_INDEX.md](PROJECT_INDEX.md) for documentation links.
