from __future__ import annotations

import sys

import gi

# Essayer GTK4 + libadwaita (moderne), fallback sur GTK3 seul (compatible)
HAS_ADWAITA = False
try:
    gi.require_version("Adw", "1")
    gi.require_version("Gtk", "4.0")
    from gi.repository import Adw, Gtk, Gio, GLib
    HAS_ADWAITA = True
except ValueError:
    # Fallback GTK3
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, Gio, GLib
    Adw = None  # Marqueur : pas de libadwaita

from . import APP_ID, APP_NAME
from .window import create_main_window
from . import config


# Base appropriée selon la disponibilité
_AppBase = Adw.Application if HAS_ADWAITA else Gtk.Application


class LinuxAudioManagerApplication(_AppBase):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID)
        self.connect("shutdown", self._on_shutdown)
        self._install_actions()

    def _on_shutdown(self, _app) -> None:
        """Arrête uniquement le processus moniteur ; le routage audio reste intact."""
        try:
            from . import audio
            audio.stop_pw_monitor()
        except Exception:
            pass

    def _install_actions(self) -> None:
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self) -> None:
        # Utiliser get_windows() pour trouver la fenêtre même si elle est masquée
        windows = self.get_windows()
        if windows:
            windows[0].present()
            return
        window = create_main_window(self)
        # Restaurer le dernier sink utilisé
        last_sink = config.get_last_default_sink()
        if last_sink is not None:
            from . import audio
            audio.set_default_sink(last_sink)
        window.present()


def main(argv: list[str] | None = None) -> int:
    if HAS_ADWAITA:
        Adw.init()
    GLib.set_application_name(APP_NAME)
    application = LinuxAudioManagerApplication()
    # Interception propre de SIGINT (Ctrl+C) : quitte via la boucle GLib
    # sans traceback KeyboardInterrupt sur Python 3.14+
    try:
        from gi.repository import GLibUnix
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, 2, application.quit)
    except ImportError:
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, 2, application.quit)  # fallback ancien PyGObject
    try:
        return application.run(argv if argv is not None else sys.argv)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())