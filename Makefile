.PHONY: help run test check git-sync build-extension build-deb build-deb-local install-extension install-deb enable-extension disable-extension uninstall-extension clean

APP_BIN = audio-hub
EXTENSION_UUID = audio-hub@localhost.github.io
GIT_COMMIT_MSG ?= chore: prepare deb build

help:
	@echo "AudioHub - Available targets:"
	@echo "  make run                   - Run the latest standalone app and replace any stale instance"
	@echo "  make test                  - Run lightweight Python tests"
	@echo "  make check                 - Compile-check Python sources + tests"
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
	python3 -m unittest test_device_classifier.py test_stream_identity.py

check:
	python3 -m py_compile audio-hub.py audio_device_classifier.py audiohub/__init__.py audiohub/browser_streams.py audiohub/gtk_app.py audiohub/models.py audiohub/paths.py audiohub/pipewire.py test_device_classifier.py test_stream_identity.py

git-sync:
	@echo "==> Git sync..."
	git add -A
	@if ! git diff --cached --quiet; then \
		git commit -m "$(GIT_COMMIT_MSG)"; \
	else \
		echo "Nothing to commit"; \
	fi
	git push origin HEAD

build-deb: git-sync
	bash build.sh

build-deb-local:
	bash build.sh

install-deb: build-deb
	sudo apt install ./build/$(APP_BIN)_1.0_all.deb

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
