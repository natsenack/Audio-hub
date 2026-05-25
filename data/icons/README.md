# Linux Audio Manager Icons

**Version**: 0.1.0  
**Date Created**: 25 mai 2026  
**Format**: SVG (vector) + PNG (raster at multiple resolutions) + ICO

---

## 📦 Files

### Vector Format
- **`io.github.linux-audio-manager.svg`** - Main vector logo (256x256, scalable)
- **`logo.svg`** - Alternative design variant

### Raster Formats (PNG)
- `io.github.linux-audio-manager-16.png` - Taskbar/small UI
- `io.github.linux-audio-manager-32.png` - System tray, menus
- `io.github.linux-audio-manager-48.png` - Application launcher
- `io.github.linux-audio-manager-64.png` - Medium UI elements
- `io.github.linux-audio-manager-128.png` - Application dialogs
- `io.github.linux-audio-manager-256.png` - Desktop shortcuts, high DPI

### Icon Format
- **`io.github.linux-audio-manager.ico`** - Windows ICO format (contains 16→256px variants)

### Hicolor Theme (FreeDesktop Standard)
Located in `hicolor/` subdirectory:
```
hicolor/
├── 16x16/apps/io.github.linux-audio-manager.png
├── 32x32/apps/io.github.linux-audio-manager.png
├── 48x48/apps/io.github.linux-audio-manager.png
├── 64x64/apps/io.github.linux-audio-manager.png
├── 128x128/apps/io.github.linux-audio-manager.png
├── 256x256/apps/io.github.linux-audio-manager.png
└── scalable/apps/io.github.linux-audio-manager.svg
```

---

## 🎨 Design

**Style**: Modern GNOME Human Interface Guidelines (HIG)

**Colors**:
- **Primary Blue**: #4a90e2 → #2563eb (gradient)
- **White accents**: #ffffff
- **Shadow**: 30% opacity

**Elements**:
- Speaker cone (audio output symbol)
- Sound wave arcs (representing frequency/signal propagation)
- Modern flat design with subtle gradient

**Inspired by**:
- GNOME Sound settings icon
- Audio/sound design patterns
- Material Design audio symbols

---

## 📋 Integration Points

### GNOME Desktop
- **Icon Name**: `io.github.linux-audio-manager`
- **Location**: `/usr/share/icons/hicolor/`
- **Referenced in**: 
  - `.desktop` file (`Icon=io.github.linux-audio-manager`)
  - `.metainfo.xml` (`<icon type="stock">`)
  - Application launcher menu

### Flatpak
- Icons embedded in Flatpak sandbox
- Paths: `/app/share/icons/hicolor/`

### Web/Documentation
- `io.github.linux-audio-manager-256.png` for GitHub repo thumbnail
- `io.github.linux-audio-manager.svg` for web scaling

---

## 🔧 Generation

Icons were generated using:
```bash
# From SVG to PNG (ImageMagick)
convert -background none io.github.linux-audio-manager.svg \
        -resize 256x256 io.github.linux-audio-manager-256.png

# Multiple sizes
for size in 16 32 48 64 128 256; do
  convert -background none io.github.linux-audio-manager.svg \
          -resize ${size}x${size} io.github.linux-audio-manager-${size}.png
done

# ICO format (Windows compatibility)
convert io.github.linux-audio-manager-*.png io.github.linux-audio-manager.ico
```

---

## 📐 Technical Specs

| Aspect | Value |
|--------|-------|
| **Main SVG Size** | 256x256px (scalable) |
| **Viewbox** | 0 0 256 256 |
| **PNG Sizes** | 16, 32, 48, 64, 128, 256px |
| **Format** | SVG 1.1, PNG (24-bit RGBA), ICO |
| **Background** | Transparent (PNG/SVG) |
| **Color Mode** | sRGB |
| **DPI** | 96px/inch (screen) |

---

## 🚀 Usage

### In Code
```python
# GTK4 Icon Loading
icon_theme = Gtk.IconTheme.get_for_display(display)
icon_paintable = icon_theme.lookup_icon(
    "io.github.linux-audio-manager",  # Icon name
    None, 64, 1, Gtk.TextDirection.LTR, 0
)
image = Gtk.Image.new_from_paintable(icon_paintable)
```

### In `.desktop` File
```ini
Icon=io.github.linux-audio-manager
```

### In AppStream Metadata
```xml
<icon type="stock">io.github.linux-audio-manager</icon>
```

---

## ✅ Compliance

- ✅ GNOME HIG icon guidelines
- ✅ FreeDesktop icon theme specification
- ✅ Accessible contrast ratio (>3:1 WCAG AA)
- ✅ Scalable to all common DPI levels
- ✅ Works on light and dark themes

---

## 📝 License

Icons are part of Linux Audio Manager and distributed under **GPL-3.0-or-later**.

For other uses or licensing, please contact the project maintainers.

---

**Generated**: 25 mai 2026  
**Tool**: ImageMagick  
**Version**: 0.1.0
