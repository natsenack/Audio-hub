#!/bin/bash
set -e

echo "📦 Building Debian package v0.1.0..."

# Clean old build
rm -rf build/

# Create structure
mkdir -p build/linux-audio-manager-0.1.0/DEBIAN
mkdir -p build/linux-audio-manager-0.1.0/usr/local/bin
mkdir -p build/linux-audio-manager-0.1.0/usr/share/applications
mkdir -p build/linux-audio-manager-0.1.0/usr/share/metainfo
mkdir -p build/linux-audio-manager-0.1.0/usr/share/icons/hicolor/scalable/apps
mkdir -p build/linux-audio-manager-0.1.0/opt/linux-audio-manager

# Copy app files
cp -r src build/linux-audio-manager-0.1.0/opt/linux-audio-manager/
cp data/io.github.linux-audio-manager.desktop build/linux-audio-manager-0.1.0/usr/share/applications/
cp data/io.github.linux-audio-manager.metainfo.xml build/linux-audio-manager-0.1.0/usr/share/metainfo/
cp LICENSE build/linux-audio-manager-0.1.0/

# Copy icons
cp -r data/icons/hicolor/* build/linux-audio-manager-0.1.0/usr/share/icons/hicolor/ 2>/dev/null || true
cp data/icons/io.github.linux-audio-manager.svg build/linux-audio-manager-0.1.0/usr/share/icons/hicolor/scalable/apps/ 2>/dev/null || true

# Create wrapper script
cat > build/linux-audio-manager-0.1.0/usr/local/bin/linux-audio-manager << 'WRAPPER'
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/opt/linux-audio-manager')
from src.main import main
sys.exit(main(sys.argv))
WRAPPER
chmod 755 build/linux-audio-manager-0.1.0/usr/local/bin/linux-audio-manager

# Create control file
cat > build/linux-audio-manager-0.1.0/DEBIAN/control << 'CONTROL'
Package: linux-audio-manager
Version: 0.1.0
Section: sound
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1
Recommends: wireplumber
Maintainer: natsenack <threeaxe.france@gmail.com>
Homepage: https://github.com/natsenack/linux-audio-manager
Description: Modern audio management for Linux with PipeWire integration
 Linux Audio Manager is a modern audio management application that combines
 simple volume control with advanced PipeWire routing capabilities.
CONTROL
chmod 644 build/linux-audio-manager-0.1.0/DEBIAN/control

# Create install scripts
cat > build/linux-audio-manager-0.1.0/DEBIAN/postinst << 'POSTINST'
#!/bin/bash
set -e
update-desktop-database /usr/share/applications 2>/dev/null || true
POSTINST
chmod 755 build/linux-audio-manager-0.1.0/DEBIAN/postinst

echo "#!/bin/bash" > build/linux-audio-manager-0.1.0/DEBIAN/preinst
echo "pkill -f '/opt/linux-audio-manager/src/main.py' || true" >> build/linux-audio-manager-0.1.0/DEBIAN/preinst
chmod 755 build/linux-audio-manager-0.1.0/DEBIAN/preinst

echo "#!/bin/bash" > build/linux-audio-manager-0.1.0/DEBIAN/prerm
echo "pkill -f '/opt/linux-audio-manager/src/main.py' || true" >> build/linux-audio-manager-0.1.0/DEBIAN/prerm
chmod 755 build/linux-audio-manager-0.1.0/DEBIAN/prerm

cat > build/linux-audio-manager-0.1.0/DEBIAN/postrm << 'POSTRM'
#!/bin/bash
update-desktop-database /usr/share/applications 2>/dev/null || true
POSTRM
chmod 755 build/linux-audio-manager-0.1.0/DEBIAN/postrm

# Copy structure to /tmp for building (avoids permission issues)
cp -r build/linux-audio-manager-0.1.0 /tmp/

# Build DEB
cd /tmp
dpkg-deb --build -Zxz linux-audio-manager-0.1.0 linux-audio-manager_0.1.0_all.deb

# Copy back to project
cp linux-audio-manager_0.1.0_all.deb "/mnt/wwn-0x5000000000002733-part2/1. projet vscode/linux audio manager/build/"
cp -r linux-audio-manager-0.1.0 "/mnt/wwn-0x5000000000002733-part2/1. projet vscode/linux audio manager/build/"

echo ""
echo "✅ DEB créé:"
ls -lh "/mnt/wwn-0x5000000000002733-part2/1. projet vscode/linux audio manager/build/"*.deb
