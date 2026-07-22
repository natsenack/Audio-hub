.PHONY: help run test check git-sync build-extension build-deb build-deb-local install-extension install-deb enable-extension disable-extension uninstall-extension clean

APP_BIN = audio-hub
DEB_VERSION ?= 1.0.6
DEB_PATH = build/$(APP_BIN)_$(DEB_VERSION)_all.deb
EXTENSION_UUID = audio-hub@localhost.github.io
GIT_COMMIT_MSG ?= chore: prepare deb build

help:
	@echo "AudioHub - Available targets:"
	@echo "  make run                   - Run the latest standalone app and replace any stale instance"
	@echo "  make test                  - No automated tests are currently shipped"
	@echo "  make check                 - Compile-check Python sources"
	@echo "  make build-extension       - Build the GNOME Shell extension package (ZIP)"
	@echo "  make git-sync              - Commit all changes and push HEAD to origin"
	@echo "  make build-deb             - Commit, push, then build the Debian package"
	@echo "  make build-deb-local       - Build the Debian package without git push"
	@echo "  make install-extension     - Install the extension locally for testing"
	@echo "  make install-deb           - Build and install the Debian package"
	@echo "  make enable-extension      - Enable the extension"
	@echo "  make disable-extension     - Disable the extension"
	@echo "  make uninstall-extension   - Uninstall the extension"
	@echo "  make clean                 - Clean build artifacts"

run:
	bash launch.sh --replace

test:
	@echo "No automated tests are currently shipped."

check:
	bash -n build.sh build-extension.sh launch.sh
	python3 -m py_compile audio-hub.py audio_device_classifier.py tray_helper.py audiohub/*.py
	@if command -v desktop-file-validate >/dev/null 2>&1; then desktop-file-validate data/com.audiohub.AudioHub.desktop; fi
	@if command -v appstreamcli >/dev/null 2>&1; then appstreamcli validate --no-net --strict data/com.audiohub.audiohub.metainfo.xml; fi
	@if command -v xmllint >/dev/null 2>&1; then xmllint --noout data/com.audiohub.audiohub.metainfo.xml; fi

git-sync:
	@echo "==> Git sync..."
	git -c safe.directory="$(CURDIR)" add -A
	@if ! git -c safe.directory="$(CURDIR)" diff --cached --quiet; then \
		git -c safe.directory="$(CURDIR)" commit -m "$(GIT_COMMIT_MSG)"; \
	else \
		echo "Nothing to commit"; \
	fi
	git -c safe.directory="$(CURDIR)" push origin HEAD

build-deb: git-sync
	DEB_VERSION="$(DEB_VERSION)" bash build.sh

build-deb-local:
	DEB_VERSION="$(DEB_VERSION)" VERSION="$(DEB_VERSION)" bash build.sh

install-deb: build-deb
	sudo apt install ./$(DEB_PATH)

build-extension:
	bash build-extension.sh

install-extension: build-extension
	gnome-extensions install --force build/$(EXTENSION_UUID).zip

enable-extension:
	gnome-extensions enable $(EXTENSION_UUID)

disable-extension:
	gnome-extensions disable $(EXTENSION_UUID)

uninstall-extension:
	gnome-extensions uninstall $(EXTENSION_UUID)

clean:
	rm -rf build/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

.DEFAULT_GOAL := help
