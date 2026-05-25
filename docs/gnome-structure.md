# Structure GNOME

Cette arborescence suit les conventions habituelles d'une application GNOME moderne basee sur GTK4 et libadwaita.

## Dossiers

- `src/` : code de l'application, point d'entree, fenetre principale, logique metier.
- `data/` : fichiers installes avec l'application, metadata, schemas, UI et icones.
- `data/ui/` : interfaces GTK Builder (`.ui`).
- `data/icons/hicolor/scalable/apps/` : icone principale au format SVG.
- `po/` : fichiers de traduction.
- `flatpak/` : manifeste Flatpak pour le packaging et la distribution.
- `build-aux/` : scripts utilitaires de build ou d'assistance.
- `tests/` : tests unitaires ou d'integration.
- `docs/` : documentation projet.

## Fichiers attendus plus tard

- `meson.build` : build system principal.
- `meson_options.txt` : options de compilation.
- `data/*.desktop.in` : entree d'application pour le menu GNOME.
- `data/*.metainfo.xml.in` : metadonnees GNOME Software.
- `data/*.gschema.xml` : preferences via GSettings.
- `flatpak/*.json` : packaging Flatpak.

## Conventions GNOME a respecter

- Utiliser un app-id reverse DNS stable.
- Basculer l'interface sur GTK4 et libadwaita.
- Eviter les dialogues non natifs quand libadwaita propose un composant adapte.
- Utiliser les actions d'application et les raccourcis clavier GNOME.
- Garder le layout simple, lisible et compatible avec le mode sombre clair du systeme.
