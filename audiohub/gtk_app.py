#!/usr/bin/env python3
"""
AudioHub — Application GTK4 + PipeWire
Routage audio avancé, barre d'état, mise à jour temps réel.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Adw, Gdk, Gio, GLib, Pango
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .models import PipeWireSink, PipeWireSource, PipeWireStream
from .paths import ICON_ROOT, PROJECT_ROOT
from .pipewire import AudioManager


# ─── CSS ──────────────────────────────────────────────────────────────────────

_CSS = b"""
.journal-mono     { font-family: monospace; font-size: 9pt; }
.role-badge       { border-radius: 12px; padding: 2px 10px;
                    font-size: 9pt; font-weight: bold; min-height: 0; }
.role-primary     { background: alpha(@accent_color, 0.20); color: @accent_color; }
.role-mirror      { background: alpha(@warning_color, 0.20); color: @warning_color; }
.role-idle        { background: alpha(@borders, 0.35);
                    color: alpha(@card_fg_color, 0.40); }
.device-name      { font-size: 11pt; font-weight: bold; }
.stat-badge       { border-radius: 6px; padding: 2px 8px; font-size: 9pt; }
.stream-vol-label { font-size: 11pt; font-weight: bold; color: @accent_color; }
.note-lbl         { font-size: 8.5pt; opacity: 0.60; }
.default-badge    { color: @warning_color; font-weight: bold; font-size: 9pt; }
.pop-section-lbl  { font-size: 8pt; font-weight: bold; opacity: 0.50;
                    margin-top: 6px; margin-bottom: 3px; }
.pop-action-btn   { border-radius: 6px; padding: 4px 8px; }
.browser-title    { font-style: italic; }
.stream-hdr-ctrls { padding: 4px 14px 8px 14px; }
.sink-row         { border-radius: 6px; }
.sink-row:hover   { background: alpha(@card_fg_color, 0.05); }
.options-btn      { min-width: 32px; padding: 4px 8px; font-size: 11pt; }
.mic-level-label  { font-size: 8.5pt; opacity: 0.70; margin-bottom: 2px; }
.mic-level-bar    { min-height: 14px; }
progressbar { min-height: 14px; border-radius: 3px; }
progressbar trough { min-height: 14px; border-radius: 3px; background-color: alpha(@borders, 0.3); }
progressbar progress { background-color: @accent_color; border-radius: 3px; }
"""

# ─── Browsers connus ──────────────────────────────────────────────────────────

_BROWSERS = {
    'firefox': 'Firefox', 'firefox-esr': 'Firefox ESR',
    'chromium': 'Chromium', 'google-chrome': 'Chrome',
    'chrome': 'Chrome', 'brave': 'Brave', 'brave-browser': 'Brave',
    'opera': 'Opera', 'vivaldi': 'Vivaldi', 'librewolf': 'LibreWolf',
    'waterfox': 'Waterfox', 'floorp': 'Floorp', 'zen': 'Zen Browser',
    'epiphany': 'GNOME Web', 'falkon': 'Falkon',
}

# ─── Modes de canal ───────────────────────────────────────────────────────────

_CHAN_MODES = ['Stéréo', 'Mono', 'Swap', 'Gauche', 'Droite']
_CHAN_MODE_ID = {m: i for i, m in enumerate(_CHAN_MODES)}
_CHAN_TIPS = {
    'Stéréo': 'FL→FL, FR→FR  (normal)',
    'Mono':   '(FL+FR)→FL+FR  (mixe en mono)',
    'Swap':   'FL→FR, FR→FL  (canaux inversés)',
    'Gauche': 'FL→FL+FR  (gauche uniquement)',
    'Droite': 'FR→FL+FR  (droit uniquement)',
}

_SINK_ICONS = {
    'hdmi': 'video-display-symbolic',
    'usb':  'audio-headphones-symbolic',
    'bluetooth': 'audio-headphones-symbolic',
    'headphones': 'audio-headphones-symbolic',
    'spdif': 'audio-card-symbolic',
    'jack': 'audio-card-symbolic',
    'speaker': 'audio-speakers-symbolic',
}
_SOURCE_ICON = 'audio-input-microphone-symbolic'
_SOURCE_ALT_ICON = 'audio-card-symbolic'


# ─── Application GTK4 ────────────────────────────────────────────────────────

class LinuxAudioManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id='com.github.audio-hub',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.connect('activate', self.on_activate)
        self.connect('command-line', self.on_command_line)
        self.connect('shutdown', self._on_shutdown)
        self.audio  = AudioManager()
        self.window = None
        self._tray_helper_process = None
        self._device_level_bars = {}  # Dict pour stocker les références aux barres de niveau
        self._page_hosts = {}
        self._last_refresh_fingerprint = None
        self._expanded_stream_id = None
        self._stream_expand_widgets = {}
        self._expansion_syncing = False
        self._css_loaded = False
        self._timers_started = False
        self._timer_ids = []
        self._cleanup_done = False
        self._settings_window = None
        self._routing_filter = 'all'
        self._routing_query = ''
        self._autostart_file = Path.home() / '.config' / 'autostart' / 'audio-hub.desktop'
        # Configuration loopback
        import os
        config_dir = os.path.expanduser('~/.config/audio-hub')
        os.makedirs(config_dir, exist_ok=True)
        self._config_file = os.path.join(config_dir, 'loopback.json')
        self._loopback_config = {}  # {source_id: sink_id}

    def on_command_line(self, _app, command_line):
        arguments = list(command_line.get_arguments()[1:])

        if '--quit' in arguments:
            self._quit_app()
            return 0

        self.activate()

        if '--show-window' in arguments or not arguments:
            GLib.idle_add(self._show_window)

        return 0

    def on_activate(self, app):
        self._configure_icon_theme()
        self._apply_color_scheme(self._setting('theme', default='system'))

        if not self._css_loaded:
            css = Gtk.CssProvider()
            css.load_from_data(_CSS)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self._css_loaded = True

        if self.window is None:
            self.window = self._build_window()
            self.window.connect('close-request', self._on_window_close)

        if self._setting('tray', 'enabled', True) and not self.has_tray_helper():
            self._ensure_tray_helper()

        if not self._timers_started:
            self._start_background_timers()
            self._timers_started = True

        self.window.present()

    # ── Cleanup et gestion fermeture ──────────────────────────────────────────

    def _on_window_close(self, *args):
        """Cleanup au fermeture de la fenêtre."""
        self._cleanup_background_resources()
        return False  # Laisser la fermeture se faire normalement

    def _on_shutdown(self, *_args):
        self._cleanup_background_resources()

    def _cleanup_background_resources(self):
        """Arrête proprement les processus et threads auxiliaires."""
        if self._cleanup_done:
            return

        self._cleanup_done = True
        self.audio._audio_running = False
        for timer_id in self._timer_ids:
            try:
                GLib.source_remove(timer_id)
            except Exception:
                pass
        self._timer_ids.clear()
        for thread_state in self.audio._source_threads.values():
            try:
                thread_state['stop_event'].set()
                thread_state['thread'].join(timeout=0.5)
            except Exception:
                pass
        if self._tray_helper_process and self._tray_helper_process.poll() is None:
            try:
                self._tray_helper_process.terminate()
                self._tray_helper_process.wait(timeout=2)
            except Exception:
                pass

    # ── Auto-refresh temps réel ───────────────────────────────────────────────

    def _auto_refresh(self) -> bool:
        """Détecte les changements PipeWire sans reconstruire les onglets."""
        try:
            self.audio.refresh()
            if not self.window or not self.window.get_visible():
                return True
            fingerprint = self._build_refresh_fingerprint()
            if fingerprint != self._last_refresh_fingerprint:
                self._last_refresh_fingerprint = fingerprint
                GLib.idle_add(self._refresh_dynamic_pages)
        except Exception:
            pass
        return True  # continuer le timer

    def _update_level_bars_only(self) -> bool:
        """Met à jour rapidement les barres de niveau des micros depuis le cache."""
        try:
            if self.window and self.window.get_visible() and hasattr(self, '_device_level_bars'):
                # Créer une copie pour éviter les race conditions pendant refresh
                level_bars_copy = dict(self._device_level_bars)
                for source_id, widgets in level_bars_copy.items():
                    if widgets:
                        try:
                            # Vérifier que le widget existe toujours (peut avoir été détruit)
                            if source_id not in self._device_level_bars:
                                continue
                            # widgets est un tuple (level_lbl, prog_bar)
                            level_lbl, prog_bar = widgets
                            # Lire le niveau du CACHE (pas de la source)
                            peak_level = self.audio._source_peak_levels.get(source_id, 0.0)
                            level_pct = int(peak_level * 100)
                            # Mettre à jour le label avec le pourcentage
                            level_lbl.set_text(f'{level_pct}%')
                            # Mettre à jour la fraction de la barre (0.0 à 1.0)
                            new_fraction = min(1.0, max(0.0, peak_level))
                            prog_bar.set_fraction(new_fraction)
                            # Forcer le redessinage
                            prog_bar.queue_draw()
                        except Exception:
                            # Widget détruit ou inaccessible, ignorer silencieusement
                            pass
        except Exception:
            pass
        return True

    # ── Gestion tray helper (AppIndicator subprocess) ────────────────────────

    def _resolve_tray_helper_path(self):
        """Trouve le chemin du fichier tray_helper.py."""
        tray_helper = PROJECT_ROOT / 'tray_helper.py'
        if tray_helper.exists():
            return tray_helper
        return None

    def _ensure_tray_helper(self) -> bool:
        """Lance tray_helper.py si AppIndicator est disponible."""
        if self._tray_helper_process is not None and self._tray_helper_process.poll() is None:
            return True
        
        helper_path = self._resolve_tray_helper_path()
        if helper_path is None:
            return False
        
        try:
            probe = subprocess.run(
                [sys.executable, str(helper_path), "--probe"],
                capture_output=True,
                text=True,
                check=False,
                timeout=2
            )
        except Exception:
            return False
        
        if probe.returncode != 0:
            return False
        
        try:
            self._tray_helper_process = subprocess.Popen(
                [sys.executable, str(helper_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=None
            )
        except Exception:
            self._tray_helper_process = None
            return False
        
        return self._tray_helper_process is not None and self._tray_helper_process.poll() is None

    def has_tray_helper(self) -> bool:
        """Vérifie si le tray helper est actif."""
        return self._tray_helper_process is not None and self._tray_helper_process.poll() is None

    def _stop_tray_helper(self):
        """Arrête le processus tray helper."""
        if self._tray_helper_process is None:
            return
        
        if self._tray_helper_process.poll() is None:
            try:
                self._tray_helper_process.terminate()
                self._tray_helper_process.wait(timeout=2)
            except Exception:
                try:
                    self._tray_helper_process.kill()
                except Exception:
                    pass

    def _configure_icon_theme(self):
        """Configure le thème d'icônes pour trouver les icônes d'AudioHub."""
        icon_directory = ICON_ROOT
        if icon_directory.exists():
            try:
                # GTK4: utiliser get_for_display
                display = Gdk.Display.get_default()
                if display:
                    theme = Gtk.IconTheme.get_for_display(display)
                    theme.add_search_path(str(icon_directory))
            except (AttributeError, TypeError):
                # Fallback si la méthode n'existe pas
                try:
                    Gtk.IconTheme.get_default().add_search_path(str(icon_directory))
                except:
                    pass
        
        # Les icônes installées seront dans /usr/share/icons/hicolor/

    # ── Fenêtre ───────────────────────────────────────────────────────────────

    def _setting(self, *keys, default=None):
        return self.audio.settings.get('preferences', *keys, default=default)

    def _set_setting(self, *args):
        self.audio.settings.set('preferences', *args)

    def _start_background_timers(self):
        self._timer_ids = [
            GLib.timeout_add(1000, self._restore_loopback_configs),
            GLib.timeout_add_seconds(5, self._monitor_loopback_links),
            GLib.timeout_add_seconds(int(self._setting('refresh_interval', default=2)), self._auto_refresh),
            GLib.timeout_add(200, self._update_level_bars_only),
        ]

    def _restart_background_timers(self):
        for timer_id in self._timer_ids:
            try:
                GLib.source_remove(timer_id)
            except Exception:
                pass
        self._start_background_timers()

    def _apply_color_scheme(self, scheme):
        manager = Adw.StyleManager.get_default()
        schemes = {
            'system': Adw.ColorScheme.DEFAULT,
            'dark': Adw.ColorScheme.FORCE_DARK,
            'light': Adw.ColorScheme.FORCE_LIGHT,
        }
        manager.set_color_scheme(schemes.get(scheme, Adw.ColorScheme.DEFAULT))

    def _show_settings(self, _button=None):
        if self._settings_window is not None:
            self._settings_window.present()
            return

        win = Adw.PreferencesWindow(transient_for=self.window, modal=True)
        win.set_title('Paramètres — AudioHub')
        win.set_default_size(620, 700)
        self._settings_window = win

        page = Adw.PreferencesPage()
        general = Adw.PreferencesGroup(title='Général', description='Comportement de l’application')

        tray_row = Adw.SwitchRow(title='Icône dans la barre système',
                                 subtitle='Afficher AudioHub dans la zone de notification')
        tray_row.set_active(bool(self._setting('tray', 'enabled', default=True)))
        tray_row.connect('notify::active', self._on_tray_setting_changed)
        general.add(tray_row)

        autostart_row = Adw.SwitchRow(
            title='Lancer AudioHub au démarrage',
            subtitle='Démarrer automatiquement dans la barre système',
        )
        autostart_row.set_active(bool(self._setting('startup', 'autostart', default=False)))
        autostart_row.connect('notify::active', self._on_autostart_setting_changed)
        general.add(autostart_row)

        close_row = Adw.SwitchRow(title='Réduire dans la barre système à la fermeture',
                                  subtitle='Le bouton de fermeture masque la fenêtre au lieu de quitter')
        close_row.set_active(bool(self._setting('window', 'minimize_on_close', default=True)))
        close_row.connect('notify::active', lambda row, _pspec:
                          self._set_setting('window', 'minimize_on_close', row.get_active()))
        general.add(close_row)

        refresh_row = Adw.ComboRow(title='Actualisation automatique',
                                   subtitle='Fréquence de lecture des changements PipeWire')
        refresh_model = Gtk.StringList.new(['1 seconde', '2 secondes', '5 secondes', '10 secondes'])
        refresh_row.set_model(refresh_model)
        refresh_values = [1, 2, 5, 10]
        current_refresh = int(self._setting('refresh_interval', default=2))
        refresh_row.set_selected(refresh_values.index(current_refresh) if current_refresh in refresh_values else 1)
        def on_refresh_changed(row, _pspec):
            value = refresh_values[row.get_selected()]
            self._set_setting('refresh_interval', value)
            if self._timers_started:
                self._restart_background_timers()
        refresh_row.connect('notify::selected', on_refresh_changed)
        general.add(refresh_row)
        page.add(general)

        audio_group = Adw.PreferencesGroup(title='Audio',
                                           description='Affichage et comportement du mixeur')
        meters_row = Adw.SwitchRow(title='Afficher les vumètres des microphones',
                                   subtitle='Afficher le niveau d’entrée en temps réel dans Périphériques')
        meters_row.set_active(bool(self._setting('audio', 'show_meters', default=True)))
        meters_row.connect('notify::active', lambda row, _pspec: self._on_meter_setting_changed(row))
        audio_group.add(meters_row)

        expanded_row = Adw.SwitchRow(title='Mémoriser le flux développé',
                                     subtitle='Restaurer le dernier flux ouvert dans l’onglet Routage')
        expanded_row.set_active(bool(self._setting('audio', 'remember_expanded', default=True)))
        expanded_row.connect('notify::active', lambda row, _pspec:
                             self._set_setting('audio', 'remember_expanded', row.get_active()))
        audio_group.add(expanded_row)
        page.add(audio_group)

        appearance = Adw.PreferencesGroup(title='Apparence', description='Personnaliser le thème visuel')
        theme_row = Adw.ComboRow(title='Thème')
        theme_row.set_model(Gtk.StringList.new(['Système', 'Sombre', 'Clair']))
        theme_values = ['system', 'dark', 'light']
        current_theme = self._setting('theme', default='system')
        theme_row.set_selected(theme_values.index(current_theme) if current_theme in theme_values else 0)
        def on_theme_changed(row, _pspec):
            value = theme_values[row.get_selected()]
            self._set_setting('theme', value)
            self._apply_color_scheme(value)
        theme_row.connect('notify::selected', on_theme_changed)
        appearance.add(theme_row)
        page.add(appearance)

        maintenance = Adw.PreferencesGroup(title='Outils',
                                           description='Actions rapides pour diagnostiquer et entretenir AudioHub')
        refresh_action = Adw.ActionRow(title='Rafraîchir PipeWire',
                                       subtitle='Relire immédiatement les périphériques et les flux')
        refresh_action_button = Gtk.Button(icon_name='view-refresh-symbolic')
        refresh_action_button.set_tooltip_text('Rafraîchir maintenant')
        refresh_action_button.set_valign(Gtk.Align.CENTER)
        refresh_action_button.connect('clicked', lambda _button: self._on_refresh())
        refresh_action.add_suffix(refresh_action_button)
        maintenance.add(refresh_action)

        diagnostic_action = Adw.ActionRow(title='Diagnostic système',
                                          subtitle='Voir les versions, statistiques et outils disponibles')
        diagnostic_button = Gtk.Button(icon_name='utilities-system-monitor-symbolic')
        diagnostic_button.set_tooltip_text('Afficher le diagnostic')
        diagnostic_button.set_valign(Gtk.Align.CENTER)
        diagnostic_button.connect('clicked', lambda _button: self._show_diagnostics())
        diagnostic_action.add_suffix(diagnostic_button)
        maintenance.add(diagnostic_action)

        folder_action = Adw.ActionRow(title='Dossier de configuration',
                                      subtitle=str(self.audio.settings._path.parent))
        folder_button = Gtk.Button(icon_name='folder-open-symbolic')
        folder_button.set_tooltip_text('Ouvrir le dossier')
        folder_button.set_valign(Gtk.Align.CENTER)
        folder_button.connect('clicked', lambda _button: self._open_config_directory())
        folder_action.add_suffix(folder_button)
        maintenance.add(folder_action)

        copy_action = Adw.ActionRow(title='Copier le chemin des réglages',
                                    subtitle=str(self.audio.settings._path))
        copy_button = Gtk.Button(icon_name='edit-copy-symbolic')
        copy_button.set_tooltip_text('Copier le chemin')
        copy_button.set_valign(Gtk.Align.CENTER)
        copy_button.connect('clicked', lambda _button: self._copy_settings_path())
        copy_action.add_suffix(copy_button)
        maintenance.add(copy_action)

        reset_row = Adw.ActionRow(title='Réinitialiser les préférences',
                                  subtitle='Rétablir le comportement et le thème par défaut')
        reset_button = Gtk.Button(label='Réinitialiser')
        reset_button.add_css_class('destructive-action')
        reset_button.set_valign(Gtk.Align.CENTER)
        reset_button.connect('clicked', lambda _button: self._reset_preferences(win))
        reset_row.add_suffix(reset_button)
        maintenance.add(reset_row)
        page.add(maintenance)
        win.add(page)
        win.connect('close-request', self._on_settings_closed)
        self._apply_color_scheme(self._setting('theme', default='system'))
        win.present()

    def _on_meter_setting_changed(self, row):
        self._set_setting('audio', 'show_meters', row.get_active())
        if self.window:
            self._on_refresh()

    def _open_config_directory(self):
        try:
            subprocess.Popen(['xdg-open', str(self.audio.settings._path.parent)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _copy_settings_path(self):
        if self.window:
            self.window.get_clipboard().set(str(self.audio.settings._path))

    def _show_diagnostics(self):
        def version(command):
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=3)
                return (result.stdout or result.stderr).strip().splitlines()[0][:100] or 'Indisponible'
            except Exception:
                return 'Indisponible'

        stats = self.audio.get_stats()
        details = '\n'.join([
            'AudioHub — Diagnostic système',
            '',
            f"PipeWire : {version(['pw-cli', '--version'])}",
            f"WirePlumber : {version(['wpctl', '--version'])}",
            f"wpctl : {'disponible' if self._command_exists('wpctl') else 'introuvable'}",
            f"pw-dump : {'disponible' if self._command_exists('pw-dump') else 'introuvable'}",
            '',
            f"Sorties audio : {stats['devices']}",
            f"Flux actifs : {stats['streams']}",
            f"Liens PipeWire : {stats['links']}",
            f"Flux cohérents : {stats['coherents']}",
            '',
            f"Réglages : {self.audio.settings._path}",
        ])
        self._show_text_window('Diagnostic AudioHub', details, 560, 430)

    @staticmethod
    def _command_exists(command):
        try:
            return subprocess.run(['which', command], capture_output=True, timeout=2).returncode == 0
        except Exception:
            return False

    def _show_text_window(self, title, text, width=540, height=450):
        win = Adw.Window(transient_for=self.window, modal=True)
        win.set_title(title)
        win.set_default_size(width, height)
        header = Adw.HeaderBar()
        view = Gtk.TextView(editable=False, cursor_visible=False, monospace=True)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.set_margin_top(16); view.set_margin_start(16)
        view.set_margin_end(16); view.set_margin_bottom(16)
        view.get_buffer().set_text(text)
        scroll = Gtk.ScrolledWindow()
        scroll.set_child(view); scroll.set_vexpand(True)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(header); root.append(scroll)
        win.set_content(root); win.present()

    def _on_settings_closed(self, _window):
        self._settings_window = None
        return False

    def _on_tray_setting_changed(self, row, _pspec):
        enabled = row.get_active()
        self._set_setting('tray', 'enabled', enabled)
        if enabled:
            self._ensure_tray_helper()
        else:
            self._stop_tray_helper()

    def _on_autostart_setting_changed(self, row, _pspec):
        enabled = row.get_active()
        self._set_setting('startup', 'autostart', enabled)
        if enabled and not self._setting('tray', 'enabled', default=True):
            # Un démarrage en arrière-plan doit rester récupérable depuis le
            # tray ; on le réactive automatiquement si nécessaire.
            self._set_setting('tray', 'enabled', True)
            self._ensure_tray_helper()
        self._set_autostart_enabled(enabled)

    def _set_autostart_enabled(self, enabled):
        """Installe ou retire l'entrée autostart de l'utilisateur courant."""
        try:
            if not enabled:
                if self._autostart_file.exists():
                    self._autostart_file.unlink()
                return

            self._autostart_file.parent.mkdir(parents=True, exist_ok=True)
            executable = shutil.which('audio-hub')
            if executable:
                exec_line = f'{executable} --background'
            else:
                launcher = str(PROJECT_ROOT / 'launch.sh')
                escaped_launcher = launcher.replace('\\', '\\\\').replace('"', '\\"')
                exec_line = f'"{escaped_launcher}" --background'
            desktop_entry = (
                '[Desktop Entry]\n'
                'Type=Application\n'
                'Name=AudioHub\n'
                'Comment=Routage audio PipeWire avancé\n'
                f'Exec={exec_line}\n'
                'Icon=audio-hub\n'
                'Terminal=false\n'
                'X-GNOME-Autostart-enabled=true\n'
            )
            self._autostart_file.write_text(desktop_entry, encoding='utf-8')
        except OSError as exc:
            self.audio._journal.append(f'# autostart: erreur — {exc}')

    def _reset_preferences(self, settings_window):
        self.audio.settings._data.pop('preferences', None)
        self.audio.settings.save()
        self._apply_color_scheme('system')
        self._set_autostart_enabled(False)
        if not self.has_tray_helper():
            self._ensure_tray_helper()
        if self._timers_started:
            self._restart_background_timers()
        settings_window.close()

    def _build_window(self):
        win = Adw.ApplicationWindow(application=self)
        win.set_title('AudioHub')
        win.set_default_size(1180, 780)
        win.connect('close-request', self._on_close_request)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbar = Gtk.HeaderBar()

        ref_btn = Gtk.Button(icon_name='view-refresh-symbolic')
        ref_btn.set_tooltip_text('Rafraîchir les données PipeWire')
        ref_btn.connect('clicked', self._on_refresh)
        hbar.pack_end(ref_btn)

        settings_btn = Gtk.Button(icon_name='preferences-system-symbolic')
        settings_btn.set_tooltip_text('Ouvrir les paramètres')
        settings_btn.connect('clicked', self._show_settings)
        hbar.pack_end(settings_btn)

        hide_btn = Gtk.Button(icon_name='window-minimize-symbolic')
        hide_btn.set_tooltip_text("Réduire dans la barre d'état")
        hide_btn.connect('clicked', lambda _: self.window.set_visible(False))
        hbar.pack_end(hide_btn)

        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)
        self._append_all_pages()
        self._last_refresh_fingerprint = self._build_refresh_fingerprint()

        main_box.append(hbar)
        main_box.append(self.notebook)
        win.set_content(main_box)
        return win

    def _on_close_request(self, win):
        """Minimize to tray on close button, unless Ctrl+Q used."""
        if self._setting('window', 'minimize_on_close', default=True):
            win.set_visible(False)
            return True
        self._cleanup_background_resources()
        return False

    def _on_refresh(self, _=None):
        self.audio.refresh()
        self._last_refresh_fingerprint = self._build_refresh_fingerprint()
        self._refresh_dynamic_pages()

    def _append_all_pages(self):
        self._page_hosts = {
            'devices': Gtk.Box(orientation=Gtk.Orientation.VERTICAL),
            'routing': Gtk.Box(orientation=Gtk.Orientation.VERTICAL),
            'about': Gtk.Box(orientation=Gtk.Orientation.VERTICAL),
        }
        self.notebook.append_page(self._page_hosts['devices'], Gtk.Label(label='🔊 Périphériques'))
        self.notebook.append_page(self._page_hosts['routing'], Gtk.Label(label='🔁 Routage'))
        self.notebook.append_page(self._page_hosts['about'], Gtk.Label(label='ℹ️ À propos'))
        self._refresh_dynamic_pages()

    def _refresh_dynamic_pages(self):
        self._set_page_content('devices', self._build_devices_page())
        self._set_page_content('routing', self._build_routing_page())
        self._set_page_content('about', self._build_about_page())
        return False

    def _set_page_content(self, page_name, widget):
        host = self._page_hosts.get(page_name)
        if host is None:
            return
        if page_name == 'devices':
            self._device_level_bars.clear()
        elif page_name == 'routing':
            self._stream_expand_widgets.clear()
        while host.get_first_child():
            host.remove(host.get_first_child())
        host.append(widget)

    def _build_refresh_fingerprint(self):
        sinks = tuple(
            (
                sink.id,
                sink.display_name,
                round(sink.volume, 3),
                sink.is_muted,
                sink.is_default,
                getattr(sink, 'role_label', ''),
                getattr(sink, 'transport_label', ''),
            )
            for sink in self.audio.get_sinks()
        )
        sources = tuple(
            (
                source.id,
                source.display_name,
                round(source.volume, 3),
                source.is_muted,
                source.is_default,
                getattr(source, 'role_label', ''),
                getattr(source, 'transport_label', ''),
            )
            for source in self.audio.get_sources()
        )
        streams = []
        for stream in self.audio.get_streams():
            identity = self.audio.get_stream_identity(stream.id, stream.name)
            streams.append(
                (
                    stream.id,
                    stream.pid,
                    round(stream.volume, 3),
                    stream.sample_rate,
                    stream.media_class,
                    stream.driver_id,
                    identity.get('kind'),
                    identity.get('primary'),
                    identity.get('secondary'),
                    identity.get('raw_title'),
                    identity.get('raw_artist'),
                    tuple(
                        (
                            connection.port_id,
                            connection.port_name,
                            connection.sink_name,
                            connection.sink_port,
                            connection.state,
                        )
                        for connection in stream.connections
                    ),
                )
            )
        stats = self.audio.get_stats()
        return (
            sinks,
            sources,
            tuple(streams),
            stats['links'],
            stats['coherents'],
            self.has_tray_helper(),
        )

    def _toggle_window(self):
        if self.window and self.window.get_visible():
            self.window.set_visible(False)
        elif self.window:
            self._on_refresh()
            self.window.present()

    def _show_window(self):
        if self.window:
            self._on_refresh()
            self.window.present()

    def _quit_app(self):
        self._cleanup_background_resources()
        self.quit()

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _sep(vert=False):
        return Gtk.Separator(orientation=Gtk.Orientation.VERTICAL if vert
                             else Gtk.Orientation.HORIZONTAL)

    @staticmethod
    def _esc(s): return GLib.markup_escape_text(str(s))

    def _sec_lbl(self, text):
        l = Gtk.Label(label=text); l.add_css_class('pop-section-lbl')
        l.set_halign(Gtk.Align.START); return l

    def _make_badge(self, text, css_class='stat-badge'):
        badge = Gtk.Label(label=text)
        badge.add_css_class(css_class)
        return badge

    def _is_stream_expanded(self, stream_id):
        if not self._setting('audio', 'remember_expanded', default=True):
            return False
        if self._expanded_stream_id is not None:
            return self._expanded_stream_id == stream_id
        saved = bool(self.audio.settings.get('ui', 'expanded', str(stream_id), default=False))
        if saved:
            self._expanded_stream_id = stream_id
            return True
        return False

    def _set_stream_expanded(self, stream_id, expanded):
        if self._expansion_syncing:
            return

        if expanded:
            self._expanded_stream_id = stream_id
        elif self._expanded_stream_id == stream_id:
            self._expanded_stream_id = None

        self._expansion_syncing = True
        try:
            for other_stream_id, (button, body_wrap) in self._stream_expand_widgets.items():
                is_expanded = expanded and other_stream_id == stream_id
                body_wrap.set_visible(is_expanded)
                button.set_label('▼' if is_expanded else '▶')
                if button.get_active() != is_expanded:
                    button.set_active(is_expanded)
                if self._setting('audio', 'remember_expanded', default=True):
                    self.audio.settings.set('ui', 'expanded', str(other_stream_id), is_expanded)

            if stream_id not in self._stream_expand_widgets:
                if self._setting('audio', 'remember_expanded', default=True):
                    self.audio.settings.set('ui', 'expanded', str(stream_id), expanded)
        finally:
            self._expansion_syncing = False

    # ══════════════════════════════════════════════════════════════════════════
    # ── Onglet Périphériques ──────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════

    def _build_devices_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_margin_top(18); page.set_margin_start(22)
        page.set_margin_end(22); page.set_margin_bottom(18)

        sinks   = self.audio.get_sinks()
        sources = self.audio.get_sources()

        def section(title, items, is_sink):
            grp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            tl = Gtk.Label(); tl.set_markup(f'<b>{title}</b>')
            tl.set_halign(Gtk.Align.START); tl.add_css_class('heading')
            tl.set_margin_bottom(6); grp.append(tl)
            if not items:
                el = Gtk.Label(label='Aucun périphérique détecté.')
                el.set_halign(Gtk.Align.START); el.add_css_class('dim-label')
                grp.append(el); return grp
            lb = Gtk.ListBox()
            lb.set_selection_mode(Gtk.SelectionMode.NONE)
            lb.add_css_class('boxed-list')
            for item in items: lb.append(self._make_device_card(item, is_sink))
            grp.append(lb); return grp

        s1 = section(f'Sorties audio  (Sink)  —  {len(sinks)} détecté(s)', sinks, True)
        s1.set_margin_bottom(22); page.append(s1)
        page.append(section(f"Entrées audio  (Source)  —  {len(sources)} détecté(s)", sources, False))
        scroll.set_child(page); return scroll

    def _make_device_card(self, device, is_sink: bool):
        """Crée une carte de périphérique avec tous les contrôles et la barre de niveau."""
        row = Gtk.ListBoxRow(); row.set_activatable(False); row.set_selectable(False)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_margin_top(16); outer.set_margin_start(16)
        outer.set_margin_end(16); outer.set_margin_bottom(16)

        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 1: En-tête avec icône + nom + badges
        # ═══════════════════════════════════════════════════════════════════════
        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        if is_sink:
            icon_name = _SINK_ICONS.get(getattr(device, 'icon_key', device.type), 'audio-speakers-symbolic')
        else:
            icon_name = _SOURCE_ICON if getattr(device, 'role', '') == 'microphone' else _SOURCE_ALT_ICON
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_icon_size(Gtk.IconSize.LARGE)
        hdr.append(icon)

        # Zone d'infos (nom + description)
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        info_box.set_hexpand(True)
        
        nm = Gtk.Label(label=device.display_name)
        nm.set_halign(Gtk.Align.START); nm.add_css_class('device-name')
        nm.set_ellipsize(Pango.EllipsizeMode.END)
        
        direction_label = 'Sortie' if is_sink else 'Entrée'
        sub_parts = [
            f'#{device.id}',
            direction_label,
            getattr(device, 'role_label', 'Audio'),
            getattr(device, 'transport_label', 'Audio'),
        ]
        sub = Gtk.Label()
        sub.set_markup(
            '<small>' + '  ·  '.join(self._esc(part) for part in sub_parts)
            + '  ·  ' + self._esc(device.node_name[:55]) + '</small>')
        sub.set_halign(Gtk.Align.START); sub.add_css_class('dim-label')
        sub.set_ellipsize(Pango.EllipsizeMode.END)
        
        info_box.append(nm)
        info_box.append(sub)
        hdr.append(info_box)

        # Badges (Mute + Défaut)
        badges = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        badges.set_valign(Gtk.Align.CENTER)
        badges.append(self._make_badge(getattr(device, 'transport_label', 'Audio')))
        badges.append(self._make_badge(getattr(device, 'role_label', 'Audio')))
        
        # Dropdown de routage SEULEMENT pour les entrées audio (mixer, pas les vrais micros)
        if not is_sink and hasattr(device, 'is_real_microphone') and not device.is_real_microphone:
            sinks = self.audio.get_sinks()
            if sinks:
                sink_drop = Gtk.DropDown.new_from_strings([s.display_name for s in sinks])
                sink_drop.set_tooltip_text('Écouter cette entrée dans cette sortie')
                sink_drop.set_size_request(150, -1)
                
                def on_sink_selected(_drop, _pspec, src_id=device.id, sl=sinks, app=self):
                    selected_idx = _drop.get_selected()
                    if selected_idx >= 0 and selected_idx < len(sl):
                        target_sink = sl[selected_idx]
                        # D'abord nettoyer les anciens loopbacks
                        removed = app.audio.unroute_source_from_all_sinks(src_id)
                        # Créer le nouveau loopback
                        app.audio.route_source_to_sink(src_id, target_sink.id)
                        # Sauvegarder la configuration
                        app._save_loopback_config(src_id, target_sink.id)
                        # Déclencher un rafraîchissement après changement de loopback
                        GLib.idle_add(lambda: app._on_refresh() or False)
                
                sink_drop.connect('notify::selected', on_sink_selected)
                badges.append(sink_drop)
        
        if device.is_muted:
            badges.append(self._make_badge('MUET', 'role-idle'))
        if device.is_default:
            badges.append(self._make_badge('Défaut', 'default-badge'))
        hdr.append(badges)
        
        outer.append(hdr)

        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 2: Barre de niveau UNIQUEMENT pour les micros
        # ═══════════════════════════════════════════════════════════════════════
        if (not is_sink and getattr(device, 'is_real_microphone', False)
                and self._setting('audio', 'show_meters', default=True)):
            level_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            level_section.set_margin_top(12)
            level_section.set_margin_bottom(10)
            level_section.set_margin_start(48)
            level_section.set_margin_end(0)
            
            # Conteneur pour la barre + label (horizontalement)
            bar_line = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            bar_line.set_hexpand(True)
            
            # Barre de progression native GTK4
            prog_bar = Gtk.ProgressBar()
            prog_bar.set_fraction(device.peak_level)
            prog_bar.set_hexpand(True)
            prog_bar.set_show_text(False)
            prog_bar.add_css_class('level-bar')
            bar_line.append(prog_bar)
            
            # Label pourcentage à droite
            level_lbl = Gtk.Label()
            level_lbl.set_text(f'{int(device.peak_level*100)}%')
            level_lbl.set_halign(Gtk.Align.CENTER)
            level_lbl.set_size_request(50, -1)
            level_lbl.add_css_class('monospace')
            bar_line.append(level_lbl)
            
            level_section.append(bar_line)
            outer.append(level_section)
            
            # Stocker les références pour les mises à jour
            device._level_display = level_lbl
            device._level_bar = prog_bar
            self._device_level_bars[device.id] = (level_lbl, prog_bar)

        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 3: Contrôle de volume
        # ═══════════════════════════════════════════════════════════════════════
        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ctrl.set_margin_start(48)
        ctrl.set_margin_top(8)
        
        vol_lbl = Gtk.Label(); vol_lbl.set_size_request(56, -1); vol_lbl.set_halign(Gtk.Align.END)
        vol_lbl.set_text('🔇' if device.is_muted else device.volume_pct)
        
        adj = Gtk.Adjustment(value=device.volume, lower=0.0, upper=1.0,
                              step_increment=0.01, page_increment=0.1, page_size=0.0)
        vs = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        vs.set_draw_value(False); vs.set_hexpand(True)
        
        def on_dv(sc, d=device, vl=vol_lbl):
            v=sc.get_value(); d.volume=v; vl.set_text(f'{int(v*100)}%')
            self.audio.set_volume(d.id, v)
        
        vs.connect('value-changed', on_dv)
        ctrl.append(vol_lbl); ctrl.append(vs)
        
        mute_btn = Gtk.ToggleButton(icon_name='audio-volume-muted-symbolic')
        mute_btn.set_active(device.is_muted); mute_btn.set_tooltip_text('Muet / Rétablir')
        mute_btn.connect('toggled', lambda _, did=device.id: self.audio.toggle_mute(did))
        ctrl.append(mute_btn)
        
        if not device.is_default:
            df = self.audio.set_default_sink if is_sink else self.audio.set_default_source
            def_btn = Gtk.Button(label='Définir par défaut')
            def_btn.connect('clicked', lambda _, fn=df, did=device.id: (fn(did), self._on_refresh()))
            ctrl.append(def_btn)
        
        outer.append(ctrl)
        row.set_child(outer)
        return row

    # ══════════════════════════════════════════════════════════════════════════
    def _get_enhanced_app_name(self, name):
        """Améliore un nom d'application avec des emojis intelligents."""
        if not name:
            return name
        name_lower = name.lower()
        app_emojis = {
            'firefox': '🦊 Firefox',
            'chrome': '🌐 Chrome',
            'chromium': '🌐 Chromium',
            'edge': '🌐 Edge',
            'microsoft edge': '🌐 Edge',
            'brave': '🌐 Brave',
            'opera': '🌐 Opera',
            'vivaldi': '🌐 Vivaldi',
            'discord': '💬 Discord',
            'spotify': '🎵 Spotify',
            'vlc': '▶️ VLC',
            'pulseaudio': '🔊 PulseAudio',
            'pipewire': '🔊 PipeWire',
            'wine': '🎮 Wine',
            'obs': '📹 OBS',
            'obs studio': '📹 OBS Studio',
            'zoom': '📞 Zoom',
            'skype': '📞 Skype',
            'teams': '📞 Microsoft Teams',
            'slack': '💬 Slack',
            'mumble': '🎙️ Mumble',
            'steam': '🎮 Steam',
        }
        for keyword, display_name in app_emojis.items():
            if keyword in name_lower:
                return display_name
        return name  # Retourner le nom original si pas de match

    def _get_stream_state(self, stream):
        """Retourne l'état du flux: ('playing'|'paused'|'stopped', emoji, couleur_css)."""
        if not stream.connections:
            return ('stopped', '⏹', 'role-idle')
        
        # Vérifier si au moins une connexion est active
        active_conns = [c for c in stream.connections if c.state == 'active']
        
        if not active_conns:
            return ('stopped', '⏹', 'role-idle')
        
        # Si une connexion est active, c'est "en cours de lecture"
        all_active = all(c.state == 'active' for c in stream.connections)
        if all_active:
            return ('playing', '▶', 'role-primary')
        
        # Partiellement actif = en pause/mixte
        return ('paused', '⏸', 'role-mirror')

    @staticmethod
    def _format_sample_rate_label(sample_rate):
        if sample_rate % 1000 == 0:
            return f'{sample_rate // 1000} kHz'
        return f'{sample_rate / 1000:.1f} kHz'

    def _sample_rate_choices(self, current_rate):
        rates = set(self.audio.COMMON_SAMPLE_RATES)
        if current_rate:
            rates.add(int(current_rate))
        return sorted(rates)

    def _make_sample_rate_dropdown(self, sink, *, compact=False):
        current_rate = int(getattr(sink, 'sample_rate', 48000) or 48000)
        rate_values = self._sample_rate_choices(current_rate)
        rate_labels = [self._format_sample_rate_label(rate) for rate in rate_values]
        dropdown = Gtk.DropDown.new_from_strings(rate_labels)
        try:
            selected_index = rate_values.index(current_rate)
        except ValueError:
            selected_index = 0
        dropdown.set_selected(selected_index)
        dropdown.set_tooltip_text(f'Fréquence de sortie pour {sink.display_name}')
        if compact:
            dropdown.set_size_request(110, -1)
        else:
            dropdown.set_hexpand(True)

        def on_rate_changed(drop, _pspec, rates=rate_values, target_sink=sink):
            selected = drop.get_selected()
            if selected < 0 or selected >= len(rates):
                return
            new_rate = rates[selected]
            if int(getattr(target_sink, 'sample_rate', 0) or 0) == new_rate:
                return
            self.audio.set_sink_sample_rate(target_sink, new_rate)
            GLib.idle_add(lambda: self._on_refresh() or False)

        dropdown.connect('notify::selected', on_rate_changed)
        return dropdown

    def _set_routing_query(self, query):
        if query == self._routing_query:
            return
        self._routing_query = query
        if self.window:
            self._refresh_dynamic_pages()

    def _set_routing_filter(self, filter_name):
        if filter_name == self._routing_filter:
            return
        self._routing_filter = filter_name
        if self.window:
            self._refresh_dynamic_pages()

    # ── Onglet Routage ────────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════

    def _build_routing_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_vexpand(True)
        sinks   = self.audio.get_sinks()
        all_streams = self.audio.get_streams()
        stats   = self.audio.get_stats()

        def matches_filter(stream):
            identity = self.audio.get_stream_identity(stream.id, stream.name)
            if self._routing_filter != 'all' and identity.get('kind') != self._routing_filter:
                return False
            query = self._routing_query.strip().lower()
            if not query:
                return True
            fields = ('primary', 'secondary', 'family', 'site_name',
                      'technical_name', 'identity_key', 'raw_title', 'raw_artist')
            haystack = ' '.join(str(identity.get(key) or '') for key in fields)
            props = self.audio._nodes.get(stream.id, {})
            haystack += ' ' + ' '.join(str(props.get(key) or '') for key in (
                'application.name', 'application.process.binary',
                'application.desktop_file', 'application.id'))
            return query in haystack.lower()

        streams = [stream for stream in all_streams if matches_filter(stream)]

        # ═══════════════════════════════════════════════════════════════════
        # ── SECTION 1: Titre et statut ────────────────────────────────────
        # ═══════════════════════════════════════════════════════════════════
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header.add_css_class('routing-header')
        
        # Titre principal
        tl = Gtk.Label(); tl.set_markup('<b>Routage Audio</b>'); tl.set_halign(Gtk.Align.START)
        tl.add_css_class('title-large')
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        title_box.set_margin_start(18); title_box.set_margin_end(18)
        title_box.set_margin_top(14); title_box.set_margin_bottom(6)
        title_box.append(tl)
        header.append(title_box)
        
        # Barre d'état avec badges
        sbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        sbar.set_margin_start(18); sbar.set_margin_end(18)
        sbar.set_margin_bottom(10)
        
        routed   = sum(1 for st in streams
                       if any(self.audio.is_linked(st.id, s.id) for s in sinks))
        unrouted = len(streams) - routed
        badges_data = [
            (f'🎵 {stats["streams"]} flux',    'accent', 'Flux audio détectés, même s’ils sont muets'),
            (f'🔊 {stats["devices"]} sorties', None,     'Périphériques de sortie'),
            (f'🔗 {stats["links"]} liens',  None,     'Liaisons PipeWire actives'),
        ]
        if routed > 0:
            badges_data.append((f'✅ {routed} routés', 'success', 'Flux avec routage actif'))
        if unrouted > 0:
            badges_data.append((f'⚠️ {unrouted} non routé{"s" if unrouted > 1 else ""}',
                                 'warning', 'Flux sans routage défini'))
        
        for text, css, tip in badges_data:
            badge = Gtk.Label(label=text); badge.add_css_class('stat-badge-routing')
            if css: badge.add_css_class(css)
            badge.set_tooltip_text(tip)
            sbar.append(badge)
        
        spacer = Gtk.Box(); spacer.set_hexpand(True); sbar.append(spacer)
        
        # Boutons d'action
        default_sink = next((s for s in sinks if s.is_default), sinks[0] if sinks else None)
        if default_sink and all_streams:
            ra_btn = Gtk.Button(label=f'Tout → {default_sink.display_name[:20]}')
            ra_btn.set_tooltip_text(f'Router tous les flux vers {default_sink.display_name}')
            def _do_route_all(_ds=default_sink, _sts=all_streams):
                for _st in _sts:
                    self.audio.set_stream_route(_st.id, _ds.id, 'PRIMARY', sinks)
                self._on_refresh()
            ra_btn.connect('clicked', lambda _: _do_route_all())
            sbar.append(ra_btn)
        
        rb = Gtk.Button(icon_name='view-refresh-symbolic')
        rb.set_tooltip_text('Rafraîchir'); rb.connect('clicked', self._on_refresh)
        sbar.append(rb)
        
        header.append(sbar)
        outer.append(header)
        outer.append(self._sep())

        filter_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        filter_row.set_margin_start(18); filter_row.set_margin_end(18)
        filter_row.set_margin_top(10); filter_row.set_margin_bottom(8)
        search = Gtk.SearchEntry()
        search.set_placeholder_text('Rechercher une application, un site ou un titre…')
        search.set_text(self._routing_query)
        search.set_hexpand(True)
        search.connect('search-changed', lambda entry: self._set_routing_query(entry.get_text()))
        filter_row.append(search)
        filter_model = Gtk.StringList.new([
            'Tous les flux', 'Applications natives', 'Navigateurs',
            'Webapps / PWA', 'Sites web'
        ])
        filter_drop = Gtk.DropDown.new(filter_model, None)
        filter_values = ['all', 'native_app', 'browser_shell', 'browser_app', 'browser_site']
        filter_drop.set_selected(filter_values.index(self._routing_filter))
        filter_drop.set_tooltip_text('Filtrer par type d’identité')
        filter_drop.connect(
            'notify::selected',
            lambda drop, _pspec: self._set_routing_filter(filter_values[drop.get_selected()]),
        )
        filter_row.append(filter_drop)
        outer.append(filter_row)

        # ═══════════════════════════════════════════════════════════════════
        # ── SECTION 2: Légende des rôles ─────────────────────────────────
        # ═══════════════════════════════════════════════════════════════════
        leg_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        leg_section.set_margin_start(18); leg_section.set_margin_end(18)
        leg_section.set_margin_top(8); leg_section.set_margin_bottom(8)
        
        leg_lbl = Gtk.Label(); leg_lbl.set_markup('<small><b>📌 Rôles des sorties audio :</b></small>')
        leg_lbl.add_css_class('dim-label'); leg_lbl.set_halign(Gtk.Align.START)
        leg_section.append(leg_lbl)
        
        leg_items = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        leg_items.set_margin_start(16)
        for bl_txt, bl_cls, bl_tip in [
            ('★ Primaire', 'role-primary', 'Sortie principale — exclusive'),
            ('⊕ Miroir',   'role-mirror',  'Copie du son vers sortie supplémentaire'),
            ('○ Off',      'role-idle',    'Non connecté — flux ignoré'),
        ]:
            bl = Gtk.Label(label=bl_txt); bl.add_css_class('role-badge')
            bl.add_css_class(bl_cls); bl.set_tooltip_text(bl_tip); leg_items.append(bl)
        leg_section.append(leg_items)
        outer.append(leg_section)
        outer.append(self._sep())

        # ═══════════════════════════════════════════════════════════════════
        # ── SECTION 3: Tous les flux audio détectés ──────────────────────
        # ═══════════════════════════════════════════════════════════════════
        content_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        content_header.set_margin_start(18); content_header.set_margin_end(18)
        content_header.set_margin_top(10); content_header.set_margin_bottom(6)
        ch_lbl = Gtk.Label(); ch_lbl.set_markup(
            f'<small><b>Flux visibles ({len(streams)} / {len(all_streams)})</b></small>')
        ch_lbl.add_css_class('dim-label')
        content_header.append(ch_lbl)
        outer.append(content_header)
        
        # Zone scrollable
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(6); content.set_margin_start(18)
        content.set_margin_end(18); content.set_margin_bottom(14)

        if not streams:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            empty.set_valign(Gtk.Align.CENTER); empty.set_vexpand(True)
            el = Gtk.Label()
            el.set_markup('<span size="xx-large">🔇</span>\n'
                          '<big><b>Aucun flux détecté</b></big>\n'
                          '<small>Lancez une application audio et configurez le routage</small>')
            el.set_justify(Gtk.Justification.CENTER); empty.append(el)
            content.append(empty)
        else:
            for stream in streams:
                content.append(self._make_stream_card(stream, sinks))
                # Restaurer les routages sauvegardés de manière asynchrone
                GLib.idle_add(lambda sid=stream.id, sk=sinks:
                              self.audio.restore_saved_routing(sid, sk) or False)

        scroll.set_child(content); outer.append(scroll)

        # ═══════════════════════════════════════════════════════════════════
        # ── SECTION 4: Journal PipeWire ──────────────────────────────────
        # ═══════════════════════════════════════════════════════════════════
        outer.append(self._sep())
        jl_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        jl_hdr.set_margin_start(18); jl_hdr.set_margin_end(18); jl_hdr.set_margin_top(8)
        jl_lbl = Gtk.Label()
        jl_lbl.set_markup('<small><b>📋 Journal des opérations PipeWire</b></small>')
        jl_lbl.set_halign(Gtk.Align.START); jl_lbl.set_hexpand(True)
        jl_lbl.add_css_class('dim-label')
        jl_hdr.append(jl_lbl)
        vider_btn = Gtk.Button(label='Vider'); 
        vider_btn.add_css_class('destructive-action')
        vider_btn.set_size_request(60, -1)
        jl_hdr.append(vider_btn)
        outer.append(jl_hdr)
        jl_scroll = Gtk.ScrolledWindow()
        jl_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        jl_scroll.set_size_request(-1, 80)
        jl_scroll.set_margin_start(18); jl_scroll.set_margin_end(18); jl_scroll.set_margin_bottom(10)
        j_tv  = Gtk.TextView(); j_tv.set_editable(False); j_tv.set_cursor_visible(False)
        j_tv.add_css_class('journal-mono')
        j_buf = j_tv.get_buffer(); j_buf.set_text(self.audio.get_journal())
        def _scroll_j(_): va=jl_scroll.get_vadjustment(); va.set_value(va.get_upper())
        jl_scroll.get_vadjustment().connect('changed', _scroll_j)
        vider_btn.connect('clicked', lambda _: (self.audio.clear_journal(), j_buf.set_text('')))
        jl_scroll.set_child(j_tv); outer.append(jl_scroll)
        return outer

    # ── Carte de flux ─────────────────────────────────────────────────────────

    def _make_stream_card(self, stream: PipeWireStream, sinks):
        sett    = self.audio.settings
        primary = self.audio.get_primary_sink(stream)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.add_css_class('card')

        # ══ LIGNE 1 : Identité du flux ════════════════════════════════════
        identity = self.audio.get_stream_identity(stream.id, stream.name)
        pid_txt = f'PID {stream.pid}' if stream.pid else ''

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row1.set_margin_top(12); row1.set_margin_start(14)
        row1.set_margin_end(14); row1.set_margin_bottom(6)

        # Icône
        icon_lbl = Gtk.Label(label=identity['icon'])
        icon_lbl.set_size_request(22, -1)
        row1.append(icon_lbl)

        # Nom + sous-titre
        name_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        disp = identity['primary']
        if identity['kind'] == 'native_app':
            disp = self._get_enhanced_app_name(disp)

        nm_lbl = Gtk.Label()
        nm_lbl.set_markup(f'<b>{self._esc(disp)}</b>')
        nm_lbl.set_halign(Gtk.Align.START)
        nm_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        name_vbox.append(nm_lbl)

        sub_parts = [identity['kind_label']]
        if identity.get('family'):
            sub_parts.append(identity['family'])
        if identity.get('secondary'):
            sub_parts.append(identity['secondary'])
        if sub_parts:
            sub_lbl = Gtk.Label()
            sub_lbl.set_markup(f'<small>{"  ·  ".join(self._esc(part) for part in sub_parts)}</small>')
            sub_lbl.set_halign(Gtk.Align.START)
            sub_lbl.add_css_class('dim-label')
            sub_lbl.add_css_class('browser-title')
            sub_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            name_vbox.append(sub_lbl)
        row1.append(name_vbox)

        # Méta
        meta_parts = [f'node:{stream.id}']
        if pid_txt: meta_parts.append(pid_txt)
        n_act = len(stream.active_connections)
        if stream.connections: meta_parts.append(f'{n_act}/{len(stream.connections)} conn.')
        meta = Gtk.Label()
        meta.set_markup(f'<small>{"  ·  ".join(meta_parts)}</small>')
        meta.add_css_class('dim-label'); meta.set_hexpand(True)
        meta.set_halign(Gtk.Align.END); meta.set_ellipsize(Pango.EllipsizeMode.START)
        row1.append(meta)

        if primary:
            rate_drop = self._make_sample_rate_dropdown(primary, compact=True)
            row1.append(rate_drop)
        else:
            rate_lbl = Gtk.Label()
            rate_lbl.set_markup(f'<small>{stream.sample_rate} Hz</small>')
            rate_lbl.add_css_class('dim-label')
            row1.append(rate_lbl)

        kind_badge = self._make_badge(identity['kind_label'])
        row1.append(kind_badge)

        # Badge d'état du flux (▶ en cours, ⏸ en pause, ⏹ arrêté)
        state_name, state_emoji, state_css = self._get_stream_state(stream)
        state_badge = Gtk.Label(label=state_emoji)
        state_badge.add_css_class('state-badge')
        state_badge.add_css_class(state_css)
        state_tooltip = {
            'playing': 'Flux en cours de lecture',
            'paused': 'Flux en pause ou partiellement connecté',
            'stopped': 'Flux arrêté ou non connecté'
        }
        state_badge.set_tooltip_text(state_tooltip.get(state_name, 'État inconnu'))
        row1.append(state_badge)

        # Bouton d'expansion (▶ / ▼) — un seul bouton
        expanded = self._is_stream_expanded(stream.id)
        exp_btn = Gtk.ToggleButton(label='▼' if expanded else '▶')
        exp_btn.set_active(expanded); exp_btn.add_css_class('flat')
        exp_btn.set_tooltip_text('Afficher / masquer les sorties audio')
        row1.append(exp_btn)

        card.append(row1)

        # ══ LIGNE 2 : Contrôles du flux ═══════════════════════════════════
        row2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row2.set_margin_start(36); row2.set_margin_end(14)
        row2.set_margin_bottom(10); row2.add_css_class('stream-hdr-ctrls')

        # Volume
        vol_l2 = Gtk.Label(label='🔊'); vol_l2.add_css_class('note-lbl'); row2.append(vol_l2)
        saved_sv = sett.get('stream_volume', str(stream.id))
        sv_val   = float(saved_sv) if saved_sv is not None else stream.volume
        sv_lbl = Gtk.Label(label=f'{int(sv_val*100)}%')
        sv_lbl.set_size_request(40, -1); sv_lbl.set_halign(Gtk.Align.END)
        sv_lbl.add_css_class('stream-vol-label')
        adj_sv = Gtk.Adjustment(value=sv_val, lower=0.0, upper=1.5,
                                 step_increment=0.01, page_increment=0.1, page_size=0.0)
        sv_slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj_sv)
        sv_slider.set_draw_value(False); sv_slider.set_size_request(140, -1)
        sv_slider.set_tooltip_text('Volume du flux  (0–150 %)')
        def on_sv(sc, st=stream, vl=sv_lbl):
            v=sc.get_value(); st.volume=v; vl.set_text(f'{int(v*100)}%')
            sett.set('stream_volume', str(st.id), round(v, 4))
            self.audio.set_stream_volume(st.id, v)
        sv_slider.connect('value-changed', on_sv)
        row2.append(sv_slider); row2.append(sv_lbl)
        sv_mute = Gtk.ToggleButton(icon_name='audio-volume-muted-symbolic')
        sv_mute.set_tooltip_text('Muet le flux')
        sv_mute.connect('toggled', lambda _, sid=stream.id: self.audio.toggle_mute(sid))
        row2.append(sv_mute)

        row2.append(self._sep(vert=True))

        # Balance
        bal_l = Gtk.Label(label='⬅ Bal ➡'); bal_l.add_css_class('note-lbl'); row2.append(bal_l)
        saved_bal = sett.get('stream_balance', str(stream.id))
        bal_val = float(saved_bal) if saved_bal is not None else 0.5
        adj_bal = Gtk.Adjustment(value=bal_val, lower=0.0, upper=1.0,
                                  step_increment=0.01, page_increment=0.1, page_size=0.0)
        bal_slider = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj_bal)
        bal_slider.set_draw_value(False); bal_slider.set_size_request(130, -1)
        bal_slider.set_tooltip_text('Balance gauche/droite  (centre = 0.50)')

        saved_mode = sett.get('stream_mode', str(stream.id), default='Stéréo')
        _cur_mode  = [saved_mode]  # mutable pour closure

        def on_bal(sc, st=stream, m=_cur_mode, vol_slider=sv_slider):
            b = sc.get_value()
            sett.set('stream_balance', str(st.id), round(b, 4))
            current_vol = vol_slider.get_value()
            self.audio.apply_stream_params(st.id, b, m[0], current_vol)
        bal_slider.connect('value-changed', on_bal)
        row2.append(bal_slider)

        ctr_btn = Gtk.Button(label='C'); ctr_btn.add_css_class('flat')
        ctr_btn.set_tooltip_text('Centrer la balance')
        ctr_btn.connect('clicked', lambda _: bal_slider.set_value(0.5))
        row2.append(ctr_btn)

        row2.append(self._sep(vert=True))

        # Mode canal
        ml = Gtk.Label(label='Mode :'); ml.add_css_class('note-lbl'); row2.append(ml)
        chan_store = Gtk.StringList.new(_CHAN_MODES)
        chan_drop  = Gtk.DropDown.new(chan_store, None)
        chan_drop.set_selected(_CHAN_MODE_ID.get(saved_mode, 0))
        chan_drop.set_size_request(96, -1)
        chan_drop.set_tooltip_text('\n'.join(f'{k}: {v}' for k, v in _CHAN_TIPS.items()))
        def on_mode(drop, _, st=stream, bs=bal_slider, m=_cur_mode, vol_slider=sv_slider):
            mode = _CHAN_MODES[drop.get_selected()]
            m[0] = mode
            sett.set('stream_mode', str(st.id), mode)
            current_vol = vol_slider.get_value()
            self.audio.apply_stream_params(st.id, bs.get_value(), mode, current_vol)
        chan_drop.connect('notify::selected', on_mode)
        row2.append(chan_drop)

        # Restaurer et appliquer les paramètres sauvegardés au chargement du flux
        if saved_bal is not None or saved_mode != 'Stéréo':
            GLib.idle_add(lambda sid=stream.id, b=bal_val, m=saved_mode, vs=sv_slider:
                          self.audio.apply_stream_params(sid, b, m, vs.get_value()) or False)

        card.append(row2)

        # ══ Résumé routage — sinks connectés (visible même replié) ══════
        srw = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        srw.set_margin_start(42); srw.set_margin_end(14)
        srw.set_margin_bottom(8); srw.set_margin_top(2)
        linked_sinks = [s for s in sinks if self.audio.is_linked(stream.id, s.id)]
        if linked_sinks:
            _arrow = Gtk.Label(); _arrow.set_markup('<small><b>→</b></small>')
            _arrow.add_css_class('dim-label'); srw.append(_arrow)
            for ls in linked_sinks:
                chip = Gtk.Label()
                chip.set_markup(f'<small>{self._esc(ls.display_name)}</small>')
                chip.add_css_class('role-badge')
                chip.add_css_class(
                    'role-primary' if (primary and ls.id == primary.id) else 'role-mirror')
                srw.append(chip)
        else:
            _nr = Gtk.Label(); _nr.set_markup('<small><i>⚠ Non routé</i></small>')
            _nr.add_css_class('dim-label'); srw.append(_nr)
        card.append(srw)
        # Données pour les détails techniques (affichés dans le corps déplié)
        _conn_lines = '\n'.join(
            f'  port {c.port_id}  {c.port_name}  →  {c.sink_name}:{c.sink_port}  [{c.state}]'
            for c in stream.connections) or '  (aucune connexion)'
        _np = self.audio._nodes.get(stream.id, {})
        _tech_details = (
            f'classification.kind:  {identity["kind"]}\n'
            f'classification.label: {identity["kind_label"]}\n'
            f'classification.family:{identity.get("family","")}\n'
            f'classification.identity:{identity.get("identity_key", "")}\n'
            f'classification.confidence:{identity.get("confidence", "")}\n'
            f'application.display: {identity.get("app_name", "")}\n'
            f'application.site:    {identity.get("site_name", "")}\n'
            f'application.name:   {_np.get("application.name","")}\n'
            f'application.binary: {_np.get("application.process.binary","")}\n'
            f'application.desktop:{_np.get("application.desktop_file","") or _np.get("application.id","")}\n'
            f'application.icon:   {_np.get("application.icon-name","") or _np.get("application.icon_name","")}\n'
            f'process.cmdline:    {_np.get("application.process.commandline","") or _np.get("process.commandline","")}\n'
            f'media.title:        {_np.get("media.title","")}\n'
            f'media.artist:       {_np.get("media.artist","")}\n'
            f'media.class:        {stream.media_class}\n'
            f'node.driver-id:     {stream.driver_id}\n'
            f'sample_rate:        {stream.sample_rate} Hz\n'
            f'Connexions:\n{_conn_lines}')

        # ══ Corps déplié : sinks + détails techniques ═════════════════════
        card.append(self._sep())
        body_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        body.set_margin_start(10); body.set_margin_end(10)
        body.set_margin_top(4);    body.set_margin_bottom(4)

        def rebuild_body(body_box=body, st=stream, sinks_list=sinks):
            while body_box.get_first_child():
                body_box.remove(body_box.get_first_child())
            for i, sink in enumerate(sinks_list):
                role = self._get_role(st, sink, primary)
                if i > 0: body_box.append(self._sep())
                body_box.append(self._make_sink_entry(sink, st, role,
                                                       sinks_list, body_box, rebuild_body))

        rebuild_body()
        body_wrap.append(body)

        # Détails techniques pliables intégrés au bas du corps
        _dt_sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        _dt_sep.set_margin_top(4); _dt_sep.set_margin_bottom(2)
        body_wrap.append(_dt_sep)
        _dt_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        _dt_hdr.set_margin_start(14); _dt_hdr.set_margin_end(14); _dt_hdr.set_margin_bottom(2)
        _dt_toggle = Gtk.ToggleButton(label='ⓘ Détails techniques')
        _dt_toggle.add_css_class('flat'); _dt_toggle.set_halign(Gtk.Align.START)
        _dt_hdr.append(_dt_toggle); body_wrap.append(_dt_hdr)
        _dt_tv_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        _dt_tv_box.set_margin_start(14); _dt_tv_box.set_margin_end(14); _dt_tv_box.set_margin_bottom(8)
        _dt_tv = Gtk.TextView(); _dt_tv.set_editable(False); _dt_tv.set_cursor_visible(False)
        _dt_tv.add_css_class('journal-mono'); _dt_tv.get_buffer().set_text(_tech_details)
        _dt_tv_box.append(_dt_tv); _dt_tv_box.set_visible(False)
        body_wrap.append(_dt_tv_box)
        _dt_toggle.connect('toggled', lambda b, db=_dt_tv_box: db.set_visible(b.get_active()))

        card.append(body_wrap); body_wrap.set_visible(expanded)
        self._stream_expand_widgets[stream.id] = (exp_btn, body_wrap)

        def on_expand(btn, bw=body_wrap, sid=str(stream.id)):
            if self._expansion_syncing:
                return
            is_expanded = btn.get_active()
            bw.set_visible(is_expanded)
            btn.set_label('▼' if is_expanded else '▶')
            self._set_stream_expanded(int(sid), is_expanded)
        exp_btn.connect('toggled', on_expand)
        return card

    def _get_role(self, stream, sink, primary):
        saved = self.audio.get_saved_sink_role(stream.id, sink)
        if saved:
            return saved
        if sink.is_muted: return 'idle'
        if primary and sink.id == primary.id: return 'PRIMARY'
        connected = self.audio.is_linked(stream.id, sink.id)
        return 'MIRROR' if connected else 'idle'

    # ── Entrée de sink (ligne dans la carte flux) ─────────────────────────────

    def _make_sink_entry(self, sink: PipeWireSink, stream: PipeWireStream,
                         role: str, sinks, body_box, rebuild_fn):
        _rd  = {'PRIMARY': '★  Primaire', 'MIRROR': '⊕  Miroir', 'idle': '○  Off'}
        _rc  = {'PRIMARY': 'role-primary', 'MIRROR': 'role-mirror', 'idle': 'role-idle'}

        entry = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        entry.set_margin_top(7); entry.set_margin_bottom(7)
        entry.set_margin_start(6); entry.set_margin_end(6)
        entry.add_css_class('sink-row')

        # Icône
        icon = Gtk.Image.new_from_icon_name(
            _SINK_ICONS.get(getattr(sink, 'icon_key', sink.type), 'audio-speakers-symbolic')
        )
        icon.set_icon_size(Gtk.IconSize.NORMAL); icon.set_size_request(22, -1)
        entry.append(icon)

        # Nom
        nm = Gtk.Label(label=f'{sink.display_name}  #{sink.id}')
        nm.set_size_request(220, -1); nm.set_halign(Gtk.Align.START)
        nm.set_ellipsize(Pango.EllipsizeMode.END); entry.append(nm)

        # Sélecteur de rôle — 3 boutons liés
        role_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        role_box.add_css_class('linked')

        p_btn = Gtk.ToggleButton(label='★ Primaire'); p_btn.set_active(role == 'PRIMARY')
        m_btn = Gtk.ToggleButton(label='⊕ Miroir');  m_btn.set_active(role == 'MIRROR')
        o_btn = Gtk.ToggleButton(label='○ Off');     o_btn.set_active(role == 'idle')
        for b in (p_btn, m_btn, o_btn): role_box.append(b)
        entry.append(role_box)

        # Dot de statut
        dot = Gtk.Label()
        if sink.is_muted: dot.set_markup('<span color="red">🔇</span>')
        elif role == 'idle': dot.set_markup('<span color="gray">●</span>')
        else: dot.set_markup('<span color="green">●</span>')
        entry.append(dot)

        # Vol périph (lecture seule)
        dv = Gtk.Label()
        dv.set_markup(f'<small>{sink.volume_pct}</small>' if role != 'idle' else '')
        dv.set_size_request(52, -1); dv.set_halign(Gtk.Align.END)
        dv.add_css_class('dim-label'); entry.append(dv)

        spacer = Gtk.Box(); spacer.set_hexpand(True); entry.append(spacer)

        # Créer une row pour avoir le bouton menu comme frère d'entry (pas enfant)
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        row.append(entry)
        
        # Bouton options (⋯) - FRÈRE d'entry, pas enfant
        options_btn = Gtk.Button(label='⋯')
        options_btn.add_css_class('flat')
        options_btn.add_css_class('options-btn')
        options_btn.set_tooltip_text('Options')
        row.append(options_btn)

        # Logique de changement de rôle
        def apply_role(new_role, pbn=p_btn, mbn=m_btn, obn=o_btn, d=dot, dvl=dv,
                       st=stream, s=sink, rb=rebuild_fn, sl=sinks, am=self.audio):
            # Mettre à jour l'UI localement
            pbn.set_active(new_role == 'PRIMARY')
            mbn.set_active(new_role == 'MIRROR')
            obn.set_active(new_role == 'idle')
            if s.is_muted: d.set_markup('<span color="red">🔇</span>')
            elif new_role == 'idle': d.set_markup('<span color="gray">●</span>')
            else: d.set_markup('<span color="green">●</span>')
            dvl.set_markup(f'<small>{s.volume_pct}</small>' if new_role != 'idle' else '')
            # Toutes les décisions passent par le contrôleur central :
            # l'exclusivité de Primaire, les miroirs et la persistance sont
            # ainsi identiques quel que soit le bouton utilisé.
            am.set_stream_route(st.id, s.id, new_role, sl)
            GLib.idle_add(rb)

        # Connexion des boutons de rôle
        _lock = [False]
        def on_role_btn(new_role):
            def cb(btn):
                if _lock[0]: return
                if not btn.get_active():
                    # Empêcher la désactivation sans sélection alternative
                    _lock[0] = True
                    btn.set_active(True)
                    _lock[0] = False
                    return
                apply_role(new_role)
            return cb

        p_btn.connect('clicked', on_role_btn('PRIMARY'))
        m_btn.connect('clicked', on_role_btn('MIRROR'))
        o_btn.connect('clicked', on_role_btn('idle'))

        # Connecter le popover
        pop = self._make_sink_popover(sink, stream, p_btn, m_btn, o_btn, dot, dv, apply_role)
        pop.set_parent(row)  # Attacher à row (parent de bouton, au-dessus de entry)
        pop.set_autohide(True)  # Fermer auto quand on clique ailleurs
        
        def show_popover(_):
            # Récupérer les coordonnées du bouton dans la fenêtre (convertir en surface coords)
            rect = Gdk.Rectangle()
            x_origin = 0
            y_origin = 0
            widget = options_btn
            while widget and widget != self.window:
                alloc = widget.get_allocation()
                x_origin += alloc.x
                y_origin += alloc.y
                widget = widget.get_parent()
            
            rect.x = x_origin
            rect.y = y_origin
            rect.width = options_btn.get_allocation().width
            rect.height = options_btn.get_allocation().height
            pop.set_pointing_to(rect)
            pop.popup()
        
        options_btn.connect('clicked', show_popover)
        return row  # Retourner la row qui contient entry et options_btn

    # ── Popover "⋯" moderne ───────────────────────────────────────────────────

    def _make_sink_popover(self, sink, stream, p_btn, m_btn, o_btn, dot, dv_lbl, apply_role_fn):
        # Guard: vérifier que sink n'est pas None
        if sink is None:
            pop = Gtk.Popover()
            pop.set_child(Gtk.Label(label="Erreur: Sink non disponible"))
            return pop

        pop  = Gtk.Popover()
        pop.set_position(Gtk.PositionType.LEFT)
        pop.set_has_arrow(True)  # Afficher la flèche pointant vers le bouton

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(12); vbox.set_margin_bottom(12)
        vbox.set_margin_start(12); vbox.set_margin_end(12)
        vbox.set_size_request(290, -1)

        # ─ Header ──────────────────────────────────────────────────────
        hdr = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        tl  = Gtk.Label(); tl.set_markup(f'<b>{self._esc(sink.display_name or "Unknown")}</b>')
        tl.set_halign(Gtk.Align.CENTER)
        sl  = Gtk.Label()
        detail_parts = [
            f'node:{sink.id}',
            getattr(sink, 'role_label', 'Sortie audio'),
            getattr(sink, 'transport_label', 'Audio'),
        ]
        if sink.bus:
            detail_parts.append(str(sink.bus))
        sl.set_markup('<small>' + '  ·  '.join(self._esc(part) for part in detail_parts) + '</small>')
        sl.set_halign(Gtk.Align.CENTER); sl.add_css_class('dim-label')
        hdr.append(tl); hdr.append(sl)
        vbox.append(hdr); vbox.append(self._sep())

        # ─ Section Routage ─────────────────────────────────────────────
        vbox.append(self._sec_lbl('ROUTAGE'))
        role_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        role_row.add_css_class('linked'); role_row.set_homogeneous(True)
        for nr, label in [('PRIMARY', '★\nPrimaire'), ('MIRROR', '⊕\nMiroir'), ('idle', '○\nOff')]:
            def mk_cb(r):
                def cb(_):
                    apply_role_fn(r); pop.popdown()
                return cb
            rb = Gtk.Button(label=label); rb.connect('clicked', mk_cb(nr))
            role_row.append(rb)
        vbox.append(role_row); vbox.append(self._sep())

        # ─ Section Volume périphérique ─────────────────────────────────
        vbox.append(self._sec_lbl('VOLUME PÉRIPHÉRIQUE'))
        vol_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        vol_row.set_margin_top(4)
        vol_lbl = Gtk.Label(label=sink.volume_pct)
        vol_lbl.set_size_request(48, -1); vol_lbl.set_halign(Gtk.Align.END)
        adj = Gtk.Adjustment(value=sink.volume, lower=0.0, upper=1.0,
                              step_increment=0.01, page_increment=0.1, page_size=0.0)
        pvs = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        pvs.set_draw_value(False); pvs.set_hexpand(True)
        def on_pvol(sc, s=sink, vl=vol_lbl):
            v=sc.get_value(); s.volume=v; vl.set_text(f'{int(v*100)}%')
            self.audio.set_volume(s.id, v)
        pvs.connect('value-changed', on_pvol)
        vol_row.append(vol_lbl); vol_row.append(pvs)
        vbox.append(vol_row); vbox.append(self._sep())

        # ─ Section Fréquence ──────────────────────────────────────────
        vbox.append(self._sec_lbl('FRÉQUENCE'))
        rate_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        rate_row.set_margin_top(4)
        rate_value = Gtk.Label(label='Sortie audio')
        rate_value.set_size_request(96, -1)
        rate_value.set_halign(Gtk.Align.START)
        rate_value.add_css_class('dim-label')
        rate_row.append(rate_value)
        rate_row.append(self._make_sample_rate_dropdown(sink))
        vbox.append(rate_row)
        vbox.append(self._sep())

        # ─ Section Actions ─────────────────────────────────────────────
        vbox.append(self._sec_lbl('ACTIONS'))
        def action_btn(icon_name, label_txt, cb):
            b = Gtk.Button(); b.add_css_class('flat'); b.add_css_class('pop-action-btn')
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_start(4)
            ic = Gtk.Image.new_from_icon_name(icon_name); ic.set_icon_size(Gtk.IconSize.NORMAL)
            lb = Gtk.Label(label=label_txt); lb.set_halign(Gtk.Align.START)
            box.append(ic); box.append(lb)
            b.set_child(box); b.connect('clicked', cb); return b

        def do_mute(_):
            self.audio.toggle_mute(sink.id); pop.popdown()
        def do_default(_):
            self.audio.set_default_sink(sink.id); pop.popdown(); self._on_refresh()
        def do_copy(_):
            self.window.get_clipboard().set(str(sink.id)); pop.popdown()
        def do_info(_):
            if sink:  # Guard: vérifier que sink n'est pas None
                pop.popdown(); self._show_node_info(sink)

        vbox.append(action_btn('audio-volume-muted-symbolic', 'Basculer muet', do_mute))
        vbox.append(action_btn('starred-symbolic', 'Définir par défaut', do_default))
        vbox.append(action_btn('edit-copy-symbolic', f'Copier node ID  ({sink.id})', do_copy))
        vbox.append(action_btn('help-about-symbolic', 'Infos nœud PipeWire', do_info))

        pop.set_child(vbox)
        pop.set_offset(-6, 0)  # Décaler légèrement pour mieux coller au bouton
        return pop

    # ── Fenêtre info nœud ────────────────────────────────────────────────────

    def _show_node_info(self, sink):
        props = self.audio._nodes.get(sink.id, {})
        win = Adw.Window(); win.set_title(f'Nœud #{sink.id}  —  {sink.display_name}')
        win.set_default_size(540, 450); win.set_transient_for(self.window); win.set_modal(True)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vb.append(Gtk.HeaderBar())
        sc = Gtk.ScrolledWindow(); sc.set_vexpand(True)
        tv = Gtk.TextView(); tv.set_editable(False); tv.set_cursor_visible(False)
        tv.add_css_class('journal-mono')
        tv.set_margin_top(12); tv.set_margin_start(12)
        tv.set_margin_end(12);  tv.set_margin_bottom(12)
        tv.get_buffer().set_text(
            '\n'.join(f'{k}: {v}' for k, v in sorted(props.items()))
            or '(aucune propriété)')
        sc.set_child(tv); vb.append(sc); win.set_content(vb); win.present()

    # ── Onglet À propos ───────────────────────────────────────────────────────

    def _build_about_page(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        page.set_margin_top(28); page.set_margin_start(28)
        page.set_margin_end(28); page.set_margin_bottom(28)

        # ── Hero ────────────────────────────────────────────────────────
        hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        hero.set_halign(Gtk.Align.CENTER); hero.set_margin_bottom(20)
        logo = Gtk.Label(); logo.set_markup('<span size="56000">🎵</span>')
        t_lbl = Gtk.Label()
        t_lbl.set_markup('<span size="x-large"><b>AudioHub</b></span>')
        v_lbl = Gtk.Label()
        v_lbl.set_markup('<span color="gray">v1.0.0  ·  Routage audio PipeWire avancé</span>')
        hero.append(logo); hero.append(t_lbl); hero.append(v_lbl)
        page.append(hero); page.append(self._sep())

        # ── Récupération des versions et disponibilité des outils ────────
        def _ver(cmd):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
                return (r.stdout or r.stderr).strip().split('\n')[0][:60] or '—'
            except Exception: return '—'
        def _exists(name):
            try:
                return subprocess.run(['which', name], capture_output=True,
                                      timeout=2).returncode == 0
            except Exception: return False

        pw_ver    = _ver(['pw-cli', '--version'])
        wp_ver    = _ver(['wpctl', '--version'])
        tray_ok   = self.has_tray_helper()
        pwlink_ok = _exists('pw-link')
        pwcli_ok  = _exists('pw-cli')
        pwdump_ok = _exists('pw-dump')
        stats     = self.audio.get_stats()

        # ── Helpers ──────────────────────────────────────────────────────
        def info_row(label_txt, value_txt, ok_state=None):
            row = Gtk.ListBoxRow(); row.set_activatable(False); row.set_selectable(False)
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            hb.set_margin_top(10); hb.set_margin_bottom(10)
            hb.set_margin_start(16); hb.set_margin_end(16)
            kl = Gtk.Label(label=label_txt); kl.set_halign(Gtk.Align.START)
            kl.set_size_request(200, -1); kl.add_css_class('dim-label')
            vl = Gtk.Label(label=value_txt); vl.set_halign(Gtk.Align.START)
            vl.set_hexpand(True); vl.set_ellipsize(Pango.EllipsizeMode.END)
            hb.append(kl); hb.append(vl)
            if ok_state is not None:
                ic = Gtk.Image.new_from_icon_name(
                    'emblem-ok-symbolic' if ok_state else 'dialog-warning-symbolic')
                ic.set_icon_size(Gtk.IconSize.NORMAL); hb.append(ic)
            row.set_child(hb); return row

        def abt_section(title_txt, rows):
            sb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            sb.set_margin_top(16); sb.set_margin_bottom(4)
            st = Gtk.Label(); st.set_markup(f'<b>{title_txt}</b>')
            st.set_halign(Gtk.Align.START); sb.append(st)
            lb = Gtk.ListBox()
            lb.set_selection_mode(Gtk.SelectionMode.NONE)
            lb.add_css_class('boxed-list')
            for r in rows: lb.append(r)
            sb.append(lb); return sb

        # ── Ligne tray avec AppIndicator status ──────────────────────────────
        _tray_vl = Gtk.Label(label=''); _tray_vl.set_halign(Gtk.Align.START)
        _tray_vl.set_hexpand(True); _tray_vl.set_ellipsize(Pango.EllipsizeMode.END)
        _tray_ic = Gtk.Image.new_from_icon_name('process-working-symbolic')
        _tray_ic.set_icon_size(Gtk.IconSize.NORMAL)
        _tray_row = Gtk.ListBoxRow(); _tray_row.set_activatable(False); _tray_row.set_selectable(False)
        _tray_hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        _tray_hb.set_margin_top(10); _tray_hb.set_margin_bottom(10)
        _tray_hb.set_margin_start(16); _tray_hb.set_margin_end(16)
        _tray_kl = Gtk.Label(label="Barre d'état (tray)"); _tray_kl.set_halign(Gtk.Align.START)
        _tray_kl.set_size_request(200, -1); _tray_kl.add_css_class('dim-label')
        _tray_hb.append(_tray_kl); _tray_hb.append(_tray_vl); _tray_hb.append(_tray_ic)
        _tray_row.set_child(_tray_hb)
        def _upd_tray_row(vl=_tray_vl, ic=_tray_ic):
            ok = self.has_tray_helper()
            vl.set_text('Active — icône dans la barre système' if ok
                        else 'Inactive (AppIndicator non disponible)')
            ic.set_from_icon_name('emblem-ok-symbolic' if ok else 'dialog-warning-symbolic')
            return False
        _upd_tray_row()  # Mise à jour immédiate

        # ── Section Système PipeWire ─────────────────────────────────────
        page.append(abt_section('Système PipeWire', [
            info_row('PipeWire',    pw_ver),
            info_row('WirePlumber', wp_ver),
            info_row('pw-link',  'Disponible' if pwlink_ok else 'Introuvable', pwlink_ok),
            info_row('pw-cli',   'Disponible' if pwcli_ok  else 'Introuvable', pwcli_ok),
            info_row('pw-dump',  'Disponible' if pwdump_ok else 'Introuvable', pwdump_ok),
            _tray_row,
        ]))

        # ── Section Session audio ─────────────────────────────────────────
        page.append(abt_section('Session audio actuelle', [
            info_row('Flux actifs',      str(stats['streams'])),
            info_row('Sorties (sinks)',  str(stats['devices'])),
            info_row('Liens PipeWire',   str(stats['links'])),
            info_row('Flux cohérents',   str(stats['coherents'])),
            info_row('Rafraîchissement', 'Auto toutes les 2 s, sans recharger les onglets'),
            info_row('Paramètres',       str(self.audio.settings._path)),
        ]))

        # ── Section Fonctionnalités ──────────────────────────────────────
        feats = [
            ('Routage multi-sink',    'Router un flux vers plusieurs sorties simultanément'),
            ('Balance & mode canal',  'Stéréo, Mono, Swap, Gauche, Droite — via pw-cli'),
            ("Rôles Primaire/Miroir", 'Priorité et mirroring par flux et par sortie'),
            ('Détection navigateur',  'Firefox, Chrome, Brave, Opera, Vivaldi, LibreWolf…'),
            ('Titre & artiste',       'Lu depuis les propriétés PipeWire du nœud'),
            ('Temps réel',            'Détection automatique des nouveaux flux audio'),
            ('Persistance locale',    'Routage et volumes sauvegardés en JSON'),
        ]
        feat_rows = []
        for fname, fdesc in feats:
            row = Gtk.ListBoxRow(); row.set_activatable(False); row.set_selectable(False)
            hb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            hb.set_margin_top(8); hb.set_margin_bottom(8)
            hb.set_margin_start(16); hb.set_margin_end(16)
            ic = Gtk.Image.new_from_icon_name('emblem-ok-symbolic')
            ic.set_icon_size(Gtk.IconSize.NORMAL); hb.append(ic)
            vb2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            fl = Gtk.Label(label=fname); fl.set_halign(Gtk.Align.START)
            dl = Gtk.Label(label=fdesc); dl.set_halign(Gtk.Align.START)
            dl.add_css_class('dim-label'); dl.set_ellipsize(Pango.EllipsizeMode.END)
            vb2.append(fl); vb2.append(dl); hb.append(vb2)
            row.set_child(hb); feat_rows.append(row)
        page.append(abt_section('Fonctionnalités', feat_rows))

        # ── Bouton Quitter ──────────────────────────────────────────────
        quit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        quit_box.set_margin_top(24); quit_box.set_margin_bottom(4)
        quit_btn = Gtk.Button(label='Quitter AudioHub')
        quit_btn.add_css_class('destructive-action')
        quit_btn.connect('clicked', lambda w: self._quit_app())
        quit_box.append(quit_btn)
        page.append(quit_box)

        # ── Pied de page ─────────────────────────────────────────────────
        page.append(self._sep())
        foot = Gtk.Label()
        foot.set_markup(
            '<small>Backend : PipeWire + WirePlumber  ·  Interface : GTK4 + Adwaita\n'
            "Licence : GPL-2.0-or-later  ·  Double-clic sur l'icône tray = afficher/masquer</small>")
        foot.set_halign(Gtk.Align.CENTER); foot.set_justify(Gtk.Justification.CENTER)
        foot.add_css_class('dim-label'); foot.set_margin_top(10)
        page.append(foot)
        scroll.set_child(page); return scroll

    def _save_loopback_config(self, source_id: int, sink_id: int):
        """Sauvegarde la configuration de loopback."""
        import json
        # Convertir les clés en strings pour JSON (type mismatch fix)
        self._loopback_config[str(source_id)] = str(sink_id)
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self._loopback_config, f, indent=2)
        except Exception:
            pass

    def _load_loopback_configs(self):
        """Charge la configuration de loopback au démarrage."""
        import json
        try:
            if os.path.exists(self._config_file):
                with open(self._config_file, 'r') as f:
                    raw_config = json.load(f)
                    # Convertir les clés et valeurs en int pour cohérence interne
                    self._loopback_config = {int(k): int(v) for k, v in raw_config.items()}
        except Exception:
            self._loopback_config = {}

    def _restore_loopback_configs(self):
        """Restaure les loopbacks sauvegardés après le rafraîchissement."""
        self._load_loopback_configs()
        for source_id, sink_id in self._loopback_config.items():
            try:
                # Vérifier que la source et le sink existent
                sources = {s.id: s for s in self.audio.get_sources()}
                sinks = {s.id: s for s in self.audio.get_sinks()}
                if source_id in sources and sink_id in sinks:
                    self.audio.unroute_source_from_all_sinks(source_id, log_action=False)
                    self.audio.route_source_to_sink(source_id, sink_id, log_action=False)
            except Exception:
                pass
        return False  # Une seule exécution au démarrage
    
    def _monitor_loopback_links(self):
        """Surveille et rétablit automatiquement les loopbacks s'ils disparaissent."""
        try:
            self._load_loopback_configs()  # Recharger config silencieusement
            for source_id, sink_id in self._loopback_config.items():
                try:
                    # Vérifier que la source et le sink existent
                    sources = {s.id: s for s in self.audio.get_sources()}
                    sinks = {s.id: s for s in self.audio.get_sinks()}
                    if source_id in sources and sink_id in sinks:
                        # Vérifier si le loopback existe toujours
                        links = self.audio._links
                        loopback_exists = False
                        for link in links:
                            info = link.get('info', {})
                            out_node = info.get('output-node-id') or self.audio._port_to_node.get(info.get('output-port-id'))
                            in_node = info.get('input-node-id') or self.audio._port_to_node.get(info.get('input-port-id'))
                            if out_node == source_id and in_node == sink_id:
                                loopback_exists = True
                                break
                        
                        # Si loopback n'existe plus, le rétablir
                        if not loopback_exists:
                            self.audio.unroute_source_from_all_sinks(source_id, log_action=False)
                            self.audio.route_source_to_sink(source_id, sink_id, log_action=False)
                except Exception:
                    pass
        except Exception:
            pass
        
        return True  # GLib rappellera automatiquement cette fonction


# ─── Entrée ───────────────────────────────────────────────────────────────────

def main():
    app = LinuxAudioManagerApp()
    return app.run(sys.argv)

if __name__ == '__main__':
    raise SystemExit(main())
