.DEFAULT_GOAL := run

PYTHON ?= python3
APP_MODULE := src.main
APP_ID := io.github.linux-audio-manager
MANIFEST := $(APP_ID).json

.PHONY: run check clean install uninstall build-flatpak build-deb lint help

# Default: run the app in development mode
run: check
	$(PYTHON) -m $(APP_MODULE)

# Validate Python syntax
check:
	$(PYTHON) -m py_compile src/__init__.py src/main.py src/window.py src/audio.py src/config.py

# Clean Python cache
clean:
	find src -type d -name '__pycache__' -prune -exec rm -rf {} +
	find src -name '*.pyc' -delete
	rm -rf build/ dist/ *.egg-info/

# Install to system (requires root)
install:
	@echo "Installing to system..."
	install -Dm755 src/main.py /usr/local/bin/linux-audio-manager
	install -Dm644 data/io.github.linux-audio-manager.desktop /usr/share/applications/
	install -Dm644 data/io.github.linux-audio-manager.metainfo.xml /usr/share/metainfo/
	install -Dm644 LICENSE /usr/share/licenses/linux-audio-manager/LICENSE
	@echo "✓ Installation complete"

# Uninstall from system
uninstall:
	@echo "Uninstalling from system..."
	rm -f /usr/local/bin/linux-audio-manager
	rm -f /usr/share/applications/io.github.linux-audio-manager.desktop
	rm -f /usr/share/metainfo/io.github.linux-audio-manager.metainfo.xml
	rm -rf /usr/share/licenses/linux-audio-manager/
	@echo "✓ Uninstallation complete"

# Build Flatpak
build-flatpak: check
	@echo "Building Flatpak..."
	@bash build-flatpak.sh

# Build Debian package (no sudo required)
build-deb: check
	@echo "Building Debian package v0.1.0..."
	@bash build-deb.sh

# Run flatpak-builder-lint on manifest
lint-manifest:
	@echo "Linting Flatpak manifest..."
	@flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest $(MANIFEST)

# Display help
help:
	@echo "Linux Audio Manager - Build Targets"
	@echo ""
	@echo "Development:"
	@echo "  make run          - Run app in development mode"
	@echo "  make check        - Validate Python syntax"
	@echo "  make clean        - Remove Python cache"
	@echo ""
	@echo "Installation:"
	@echo "  make install      - Install to system (requires sudo)"
	@echo "  make uninstall    - Remove from system (requires sudo)"
	@echo ""
	@echo "Distribution:"
	@echo "  make build-flatpak - Build Flatpak package (for Flathub)"
	@echo "  make build-deb     - Build Debian package"
	@echo "  make lint-manifest - Lint Flatpak manifest (requires flatpak)"
	@echo ""