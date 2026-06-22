# AudioHub

Application GTK4 pour observer et router l'audio PipeWire, avec une extension GNOME Shell optionnelle.

## Etat du projet

- Point d'entree principal: `audio-hub.py` (lanceur fin)
- Lanceur local et installe: `launch.sh` puis binaire `audio-hub`
- Paquet Debian: `build.sh`
- Extension GNOME Shell: `metadata.json`, `extension.js`, `stylesheet.css`, `build-extension.sh`

## Structure reelle

```text
audio-hub/
├── audio-hub.py
├── audio_device_classifier.py
├── audiohub/
│   ├── __init__.py
│   ├── browser_streams.py
│   ├── gtk_app.py
│   ├── models.py
│   ├── paths.py
│   └── pipewire.py
├── launch.sh
├── build.sh
├── build-extension.sh
├── Makefile
├── requirements.txt
├── metadata.json
├── extension.js
├── stylesheet.css
├── tray_helper.py
├── test_device_classifier.py
├── test_audio.py
├── linux-audio-manager.py      # ancien prototype, non utilise par build/run
└── data/
    ├── audio-hub.desktop
    └── icons/
```

## Demarrage rapide

```bash
make run
```

Ou directement:

```bash
bash launch.sh
```

## Build

```bash
make build-deb
make build-extension
```

Le paquet Debian genere:

```bash
build/audio-hub_1.0_all.deb
```

L'extension GNOME genere:

```bash
build/audio-hub@localhost.github.io.zip
```

## Tests et verifications

```bash
make test
make check
```

Equivalent:

```bash
python3 -m unittest test_device_classifier.py
python3 -m py_compile audio-hub.py audio_device_classifier.py audiohub/*.py test_device_classifier.py test_stream_identity.py
```

## Dependances

Systeme:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 pipewire wireplumber
```

Python:

```bash
pip install -r requirements.txt
```

## Organisation du code

- `audio-hub.py` est maintenant un simple lanceur.
- `audiohub/gtk_app.py` contient l'application GTK4.
- `audiohub/models.py` centralise `Settings` et les modeles PipeWire.
- `audiohub/browser_streams.py` isole la detection des navigateurs, PWA et titres.
- `audiohub/paths.py` centralise les chemins projet/utilises par l'application.
- `audiohub/pipewire.py` contient le backend PipeWire et la logique de capture/routage.
- `audio_device_classifier.py` centralise la detection des types de peripheriques audio.
- `tray_helper.py` gere l'integration tray/AppIndicator.
- `extension.js` est l'extension GNOME Shell minimale pour ouvrir l'app et afficher `wpctl status`.

## Notes d'organisation

- `audio-hub.py` reste le point d'entree stable pour le build et le lancement.
- La logique partagee est maintenant recentree dans le package `audiohub/`.
- `linux-audio-manager.py` reste dans le depot comme ancien fichier de reference, mais il n'est pas lance par `make run`, `launch.sh` ou `build.sh`.
- La prochaine etape logique, si on veut aller encore plus loin, serait de decouper `audiohub/gtk_app.py` en sous-modules UI.

## Utilisation

Une fois installe:

```bash
audio-hub
```

## GNOME Shell

Installer localement l'extension:

```bash
make install-extension
make enable-extension
```

Verifier les extensions actives:

```bash
gnome-extensions list
```

## Troubleshooting

Etat PipeWire:

```bash
wpctl status
pw-dump | head
```

Logs GNOME Shell:

```bash
journalctl --user -u gnome-shell --no-pager -n 50
```
