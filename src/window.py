from __future__ import annotations

import os
import re

from gi.repository import Gio, Gtk, GLib

from . import audio
from . import config

try:
    from gi.repository import Adw
    HAS_ADWAITA = True
except (ValueError, ImportError):
    Adw = None
    HAS_ADWAITA = False


# ---------------------------------------------------------------------------
# Helpers : noms lisibles
# ---------------------------------------------------------------------------

def _sink_label(raw: str) -> str:
    if not raw:
        return "Sortie inconnue"
    if " " in raw:
        return raw
    if "bluez" in raw.lower():
        return "Casque Bluetooth"
    name = re.sub(r"^alsa_(output|input)\.", "", raw)
    name = re.sub(r"pci-[\da-f_]+\.\d+\.", "", name)
    name = re.sub(r"usb-[^.]+\.", "", name)
    name = re.sub(r"[-_.]", " ", name).strip()
    return " ".join(w.capitalize() for w in name.split()) or raw


def _source_label(raw: str) -> str:
    if not raw:
        return "Entrée inconnue"
    if " " in raw:
        return raw
    return _sink_label(raw)


_APP_OVERRIDES: dict[str, str] = {
    "chromium": "Chromium",
    "chrome": "Google Chrome",
    "firefox": "Firefox",
    "firefox-esr": "Firefox",
    "spotify": "Spotify",
    "vlc": "VLC",
    "mpv": "MPV",
    "rhythmbox": "Rhythmbox",
    "audacious": "Audacious",
    "clementine": "Clementine",
    "strawberry": "Strawberry",
    "discord": "Discord",
    "teams": "Microsoft Teams",
    "zoom": "Zoom",
    "obs": "OBS Studio",
    "pavucontrol": "Contrôle du volume",
    "pw-play": "Lecture PipeWire",
    "paplay": "Lecture audio",
    "freerdp": "FreeRDP",
    "xfreerdp": "FreeRDP",
}


def _app_label(raw: str, node_name: str = "") -> str:
    if not raw:
        return "Application"
    key = raw.lower().strip()
    label = _APP_OVERRIDES.get(key, raw.strip())
    if label in ("Google Chrome", "Chromium") and node_name and node_name.lower() != key:
        nkey = node_name.lower().strip()
        return _APP_OVERRIDES.get(nkey, node_name.strip())
    return label


# ---------------------------------------------------------------------------
# Icône barre d'état (StatusNotifierItem via D-Bus — compatible GTK4)
# ---------------------------------------------------------------------------

class _TrayIndicator:
    """Icône systray via org.kde.StatusNotifierItem.
    Implémente aussi com.canonical.dbusmenu pour le menu contextuel.
    Ne dépend pas de Gtk.Menu (supprimé en GTK4).
    """

    _ITEM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category"   type="s"            access="read"/>
    <property name="Id"         type="s"            access="read"/>
    <property name="Title"      type="s"            access="read"/>
    <property name="Status"     type="s"            access="read"/>
    <property name="IconName"   type="s"            access="read"/>
    <property name="ToolTip"    type="(sa(iiay)ss)" access="read"/>
    <property name="Menu"       type="o"            access="read"/>
    <method name="Activate">
      <arg type="i" direction="in" name="x"/>
      <arg type="i" direction="in" name="y"/>
    </method>
    <method name="SecondaryActivate">
      <arg type="i" direction="in" name="x"/>
      <arg type="i" direction="in" name="y"/>
    </method>
    <method name="Scroll">
      <arg type="i" direction="in" name="delta"/>
      <arg type="s" direction="in" name="orientation"/>
    </method>
    <signal name="NewIcon"/>
    <signal name="NewTitle"/>
    <signal name="NewStatus"><arg type="s" name="status"/></signal>
  </interface>
</node>"""

    _MENU_XML = """<?xml version="1.0" encoding="UTF-8"?>
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version"       type="u"  access="read"/>
    <property name="TextDirection" type="s"  access="read"/>
    <property name="Status"        type="s"  access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i"          direction="in"  name="parentId"/>
      <arg type="i"          direction="in"  name="recursionDepth"/>
      <arg type="as"         direction="in"  name="propertyNames"/>
      <arg type="u"          direction="out" name="revision"/>
      <arg type="(ia{sv}av)" direction="out" name="layout"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai"        direction="in"  name="ids"/>
      <arg type="as"        direction="in"  name="propertyNames"/>
      <arg type="a(ia{sv})" direction="out" name="properties"/>
    </method>
    <method name="GetProperty">
      <arg type="i" direction="in"  name="id"/>
      <arg type="s" direction="in"  name="name"/>
      <arg type="v" direction="out" name="value"/>
    </method>
    <method name="Event">
      <arg type="i" direction="in" name="id"/>
      <arg type="s" direction="in" name="eventId"/>
      <arg type="v" direction="in" name="data"/>
      <arg type="u" direction="in" name="timestamp"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" direction="in"  name="id"/>
      <arg type="b" direction="out" name="needUpdate"/>
    </method>
    <signal name="LayoutUpdated">
      <arg type="u" name="revision"/>
      <arg type="i" name="parent"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg type="i" name="id"/>
      <arg type="u" name="timestamp"/>
    </signal>
  </interface>
</node>"""

    # Items: id → {prop: (type_char, value)}
    # 0=racine  1=Afficher/Masquer  2=séparateur  3=Quitter
    _ITEMS: dict = {
        0: {"children-display": ("s", "submenu")},
        1: {"label": ("s", "Afficher / Masquer"), "enabled": ("b", True),  "visible": ("b", True)},
        2: {"type":  ("s", "separator"),           "enabled": ("b", True),  "visible": ("b", True)},
        3: {"label": ("s", "Quitter"),             "enabled": ("b", True),  "visible": ("b", True)},
    }

    def __init__(self, window, application) -> None:
        self._win = window
        self._app = application
        self._bus: Gio.DBusConnection | None = None
        self._revision = 1
        self._item_node = Gio.DBusNodeInfo.new_for_xml(self._ITEM_XML)
        self._menu_node = Gio.DBusNodeInfo.new_for_xml(self._MENU_XML)
        Gio.bus_get(Gio.BusType.SESSION, None, self._on_bus, None)

    # ---- connexion D-Bus ---------------------------------------------------

    def _on_bus(self, _src, result, _ud) -> None:
        try:
            self._bus = Gio.bus_get_finish(result)
        except Exception:
            return
        self._bus.register_object(
            "/StatusNotifierItem",
            self._item_node.interfaces[0],
            self._item_method, self._item_prop, None,
        )
        self._bus.register_object(
            "/StatusNotifierMenu",
            self._menu_node.interfaces[0],
            self._menu_method, self._menu_prop, None,
        )
        Gio.bus_own_name_on_connection(
            self._bus,
            f"org.kde.StatusNotifierItem-{os.getpid()}-1",
            Gio.BusNameOwnerFlags.NONE,
            self._name_acquired, None,
        )

    def _name_acquired(self, conn, name) -> None:
        if self._bus is None:
            return
        self._bus.call(
            "org.kde.StatusNotifierWatcher",
            "/StatusNotifierWatcher",
            "org.kde.StatusNotifierWatcher",
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (f"org.kde.StatusNotifierItem-{os.getpid()}-1",)),
            None, Gio.DBusCallFlags.NONE, -1, None, None, None,
        )

    # ---- StatusNotifierItem ------------------------------------------------

    def _item_method(self, conn, sender, path, iface, method, params, inv):
        if method in ("Activate", "SecondaryActivate"):
            GLib.idle_add(self._toggle)
        inv.return_value(GLib.Variant("()", ()))

    def _item_prop(self, conn, sender, path, iface, prop):
        mapping = {
            "Category":  GLib.Variant("s", "ApplicationStatus"),
            "Id":        GLib.Variant("s", "linux-audio-manager"),
            "Title":     GLib.Variant("s", "Linux Audio Manager"),
            "Status":    GLib.Variant("s", "Active"),
            "IconName":  GLib.Variant("s", "audio-volume-high"),
            "ToolTip":   GLib.Variant("(sa(iiay)ss)", (
                             "audio-volume-high", [],
                             "Linux Audio Manager", "Clic : afficher/masquer")),
            "Menu":      GLib.Variant("o", "/StatusNotifierMenu"),
        }
        return mapping.get(prop)

    # ---- dbusmenu ----------------------------------------------------------

    def _menu_prop(self, conn, sender, path, iface, prop):
        mapping = {
            "Version":       GLib.Variant("u", 4),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status":        GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }
        return mapping.get(prop)

    def _props_variant(self, item_id: int) -> dict:
        return {
            k: GLib.Variant(t, v)
            for k, (t, v) in self._ITEMS.get(item_id, {}).items()
        }

    def _build_item(self, item_id: int, depth: int):
        props = self._props_variant(item_id)
        children: list = []
        if item_id == 0 and depth != 0:
            nd = (depth - 1) if depth > 0 else -1
            for cid in (1, 2, 3):
                children.append(
                    GLib.Variant("(ia{sv}av)", self._build_item(cid, nd))
                )
        return (item_id, props, children)

    def _menu_method(self, conn, sender, path, iface, method, params, inv):
        try:
            if method == "GetLayout":
                parent_id, depth, _names = params.unpack()
                item = self._build_item(parent_id, depth if depth >= 0 else -1)
                inv.return_value(GLib.Variant("(u(ia{sv}av))", (self._revision, item)))

            elif method == "GetGroupProperties":
                ids, prop_names = params.unpack()
                result = []
                for i in ids:
                    props = self._props_variant(i)
                    if prop_names:
                        props = {k: v for k, v in props.items() if k in prop_names}
                    result.append((i, props))
                inv.return_value(GLib.Variant("(a(ia{sv}))", (result,)))

            elif method == "GetProperty":
                item_id, name = params.unpack()
                raw = self._ITEMS.get(item_id, {}).get(name)
                val = GLib.Variant(*raw) if raw else GLib.Variant("s", "")
                inv.return_value(GLib.Variant("(v)", (val,)))

            elif method == "Event":
                item_id, event_id, _data, _ts = params.unpack()
                if event_id == "clicked":
                    if item_id == 1:
                        GLib.idle_add(self._toggle)
                    elif item_id == 3:
                        GLib.idle_add(self._app.quit)
                inv.return_value(GLib.Variant("()", ()))

            elif method == "AboutToShow":
                inv.return_value(GLib.Variant("(b)", (False,)))

            else:
                inv.return_dbus_error(
                    "org.freedesktop.DBus.Error.UnknownMethod", method
                )
        except Exception as exc:
            inv.return_dbus_error("org.freedesktop.DBus.Error.Failed", str(exc))

    def _toggle(self) -> bool:
        if self._win.get_visible():
            self._win.hide()
        else:
            self._win.present()
        return False


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_main_window(application):
    return _MainWindow(application)


# ---------------------------------------------------------------------------
# Fenêtre principale
# ---------------------------------------------------------------------------

class _MainWindow(
    Adw.ApplicationWindow if HAS_ADWAITA else Gtk.ApplicationWindow
):
    def __init__(self, application) -> None:
        if HAS_ADWAITA:
            Adw.ApplicationWindow.__init__(self, application=application)
        else:
            Gtk.ApplicationWindow.__init__(
                self, application=application, type=Gtk.WindowType.TOPLEVEL
            )

        self.set_title("Linux Audio Manager")
        self.set_default_size(1020, 680)

        # État interne — suivi des widgets pour mises à jour en place
        self._stream_checkboxes: dict[int, dict[int, Gtk.CheckButton]] = {}
        self._stream_vol_scales: dict[int, Gtk.Scale] = {}    # flux sortie : node_id → Scale
        self._stream_bal_scales: dict[int, Gtk.Scale] = {}    # flux sortie : node_id → Scale balance
        self._stream_mute_btns:  dict[int, Gtk.Button] = {}   # flux sortie : node_id → Button mute
        self._sink_vol_scales:   dict[int, Gtk.Scale] = {}    # sinks : node_id → Scale
        self._sink_mute_btns:    dict[int, Gtk.Button] = {}   # sinks : node_id → Button
        self._source_vol_scales: dict[int, Gtk.Scale] = {}    # sources : node_id → Scale
        self._source_mute_btns:  dict[int, Gtk.Button] = {}   # sources : node_id → Button
        self._master_vol_scales: dict[int, Gtk.Scale] = {}    # slider master (défaut) : node_id → Scale
        self._master_mute_btns:  dict[int, Gtk.Button] = {}   # bouton mute master : node_id → Button
        self._expander_states:   dict[int, bool] = {}         # node_id → is_expanded
        self._vol_timers:        dict[int, int] = {}          # node_id → GLib timer id (debounce)
        self._updating = False                                 # garde-fou : évite boucles de rétro-action
        self._last_struct_fp: tuple | None = None             # fingerprint structure (IDs + défauts)
        self._last_vol_fp:    tuple | None = None             # fingerprint volumes + muted

        self._status_label = Gtk.Label(label="Chargement…")
        self._status_label.set_xalign(0)
        self._status_label.set_ellipsize(3)   # Pango.EllipsizeMode.END
        self._status_label.set_hexpand(False) # ne tire pas la largeur
        if HAS_ADWAITA:
            self._status_label.add_css_class("caption")
            self._status_label.add_css_class("dim-label")
            self._build_adwaita_ui(application)
        else:
            self._build_gtk3_ui(application)

        # Chargement initial
        self._refresh_ui()

        # Appliquer les routages sauvegardés dès que la boucle tourne
        GLib.idle_add(self._apply_startup_routing)

        # Actualisation automatique : 1 s quand visible, 3 s quand cachée
        self._tick_source: int = GLib.timeout_add(1000, self._tick)
        self.connect("notify::visible", self._on_visibility_changed)

        # Réaction immédiate aux événements PipeWire (volume externe, périphérique branché...)
        audio.start_pw_monitor(self._on_pw_event)

        # Icône dans la barre d'état
        self._tray = _TrayIndicator(self, application)
        if HAS_ADWAITA:
            self.connect("close-request", self._on_close_request)
        else:
            self.connect("delete-event", self._on_delete_event)

    # -----------------------------------------------------------------------
    # Construction UI — Adwaita
    # -----------------------------------------------------------------------

    def _build_adwaita_ui(self, application) -> None:
        # En-tête
        header = Adw.HeaderBar()
        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Rafraîchir")
        refresh_btn.connect("clicked", lambda *_: self._refresh_ui())
        header.pack_start(refresh_btn)
        quit_btn = Gtk.Button(label="Quitter")
        quit_btn.connect("clicked", lambda *_: application.quit())
        header.pack_end(quit_btn)

        # Sidebar gauche
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        sidebar_box.set_size_request(172, -1)
        sidebar_box.set_hexpand(False)
        sidebar_box.add_css_class("navigation-sidebar")

        app_lbl = Gtk.Label(label="Audio Manager")
        app_lbl.add_css_class("title-4")
        app_lbl.set_margin_start(14)
        app_lbl.set_margin_end(14)
        app_lbl.set_margin_top(18)
        app_lbl.set_margin_bottom(14)
        app_lbl.set_xalign(0)
        sidebar_box.append(app_lbl)
        sidebar_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Navigation
        self._nav_list = Gtk.ListBox()
        self._nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._nav_list.add_css_class("navigation-sidebar")

        self._sortie_nav_row = self._make_nav_row("audio-speakers-symbolic", "Sorties")
        self._entree_nav_row = self._make_nav_row("audio-input-microphone-symbolic", "Entrées")
        self._nav_list.append(self._sortie_nav_row)
        self._nav_list.append(self._entree_nav_row)
        sidebar_box.append(self._nav_list)

        # Séparateur + statut en bas de sidebar
        spacer = Gtk.Box()
        Gtk.Widget.set_vexpand(spacer, True)
        sidebar_box.append(spacer)
        sidebar_box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
        status_wrap = Gtk.Box()
        status_wrap.set_margin_start(12)
        status_wrap.set_margin_end(12)
        status_wrap.set_margin_top(8)
        status_wrap.set_margin_bottom(8)
        status_wrap.append(self._status_label)
        sidebar_box.append(status_wrap)

        # Stack de contenu
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        self._sortie_page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sortie_scroll = Gtk.ScrolledWindow()
        sortie_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sortie_scroll.set_child(self._sortie_page_box)
        self._stack.add_titled(sortie_scroll, "sortie", "Sorties")

        self._entree_page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        entree_scroll = Gtk.ScrolledWindow()
        entree_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        entree_scroll.set_child(self._entree_page_box)
        self._stack.add_titled(entree_scroll, "entree", "Entrées")
        Gtk.Widget.set_hexpand(self._stack, True)
        Gtk.Widget.set_vexpand(self._stack, True)

        self._nav_list.connect("row-selected", self._on_nav_select)
        self._nav_list.select_row(self._sortie_nav_row)

        # Mise en page principale
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(sidebar_box)
        main_box.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        main_box.append(self._stack)

        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(header)
        toolbar.set_content(main_box)
        if HAS_ADWAITA:
            self._toast_overlay = Adw.ToastOverlay()
            self._toast_overlay.set_child(toolbar)
            self.set_content(self._toast_overlay)
        else:
            self._toast_overlay = None
            self.set_content(toolbar)

    @staticmethod
    def _make_nav_row(icon: str, label: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(14)
        box.set_margin_end(14)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.append(Gtk.Image.new_from_icon_name(icon))
        lbl = Gtk.Label(label=label)
        lbl.set_xalign(0)
        box.append(lbl)
        row.set_child(box)
        return row

    def _on_nav_select(self, listbox, row) -> None:
        if row is self._sortie_nav_row:
            self._stack.set_visible_child_name("sortie")
        elif row is self._entree_nav_row:
            self._stack.set_visible_child_name("entree")

    # -----------------------------------------------------------------------
    # Construction UI — GTK3 (fallback)
    # -----------------------------------------------------------------------

    def _build_gtk3_ui(self, application) -> None:
        vbox = Gtk.VBox()
        bar = Gtk.HBox()
        refresh_btn = Gtk.Button(label="↻ Rafraîchir")
        refresh_btn.connect("clicked", lambda *_: self._refresh_ui())
        bar.pack_start(refresh_btn, False, False, 6)
        bar.pack_start(self._status_label, True, True, 6)
        quit_btn = Gtk.Button(label="Quitter")
        quit_btn.connect("clicked", lambda *_: application.quit())
        bar.pack_end(quit_btn, False, False, 6)
        vbox.pack_start(bar, False, False, 4)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._prefs_box = Gtk.VBox(spacing=8)
        self._prefs_box.set_margin_start(12)
        self._prefs_box.set_margin_end(12)
        scrolled.add_with_viewport(self._prefs_box)
        vbox.pack_start(scrolled, True, True, 0)
        vbox.show_all()
        self.add(vbox)

    # -----------------------------------------------------------------------
    # Actualisation et minuterie
    # -----------------------------------------------------------------------

    def _on_visibility_changed(self, *_) -> None:
        """Adapte la cadence du tick selon la visibilité de la fenêtre."""
        GLib.source_remove(self._tick_source)
        interval = 1000 if self.get_visible() else 3000
        self._tick_source = GLib.timeout_add(interval, self._tick)

    def _on_pw_event(self) -> None:
        """Appelé immédiatement quand PipeWire signale un changement audio externe."""
        self._tick()

    def _tick(self) -> bool:
        """Vérification périodique de l'état audio."""
        try:
            out, sinks, links, inp, sources, def_sink, def_src = audio.get_full_audio_state()

            struct_fp = (
                tuple(s.node_id for s in out),
                tuple(s.node_id for s in sinks),
                tuple(s.node_id for s in inp),
                tuple(s.node_id for s in sources),
                def_sink, def_src,
            )
            vol_fp = (
                tuple((s.node_id, int(s.volume * 100), s.muted) for s in out),
                tuple((s.node_id, int(s.volume * 100), s.muted) for s in sinks),
                tuple((s.node_id, int(s.volume * 100), s.muted) for s in inp),
                tuple((s.node_id, int(s.volume * 100), s.muted) for s in sources),
            )

            if struct_fp != self._last_struct_fp:
                # Structure changée (nouvelle app, périphérique branché, etc.) → rebuild complet
                self._last_struct_fp = struct_fp
                self._last_vol_fp = vol_fp
                if self.get_visible():
                    self._refresh_ui_with_state(
                        out, sinks, links, inp, sources, def_sink, def_src
                    )
            elif vol_fp != self._last_vol_fp:
                # Seuls volumes/muted ont changé → mise à jour en place (sans rebuild)
                self._last_vol_fp = vol_fp
                if self.get_visible():
                    self._updating = True
                    try:
                        self._update_volumes_in_place(out, sinks, inp, sources)
                    finally:
                        self._updating = False
        except Exception:
            pass
        return True  # Continuer le minuteur

    def _refresh_ui(self) -> None:
        out, sinks, links, inp, sources, def_sink, def_src = audio.get_full_audio_state()
        self._last_struct_fp = (
            tuple(s.node_id for s in out),
            tuple(s.node_id for s in sinks),
            tuple(s.node_id for s in inp),
            tuple(s.node_id for s in sources),
            def_sink, def_src,
        )
        self._last_vol_fp = (
            tuple((s.node_id, int(s.volume * 100), s.muted) for s in out),
            tuple((s.node_id, int(s.volume * 100), s.muted) for s in sinks),
            tuple((s.node_id, int(s.volume * 100), s.muted) for s in inp),
            tuple((s.node_id, int(s.volume * 100), s.muted) for s in sources),
        )
        self._refresh_ui_with_state(out, sinks, links, inp, sources, def_sink, def_src)

    def _refresh_ui_with_state(
        self,
        out, sinks, links, inp, sources,
        def_sink, def_src,
    ) -> None:
        if HAS_ADWAITA:
            self._rebuild_sortie_tab(out, sinks, links, def_sink)
            self._rebuild_entree_tab(inp, sources, def_src)
        else:
            for child in list(self._prefs_box.get_children()):
                self._prefs_box.remove(child)
            self._build_sinks_gtk3(sinks, def_sink)
            self._build_streams_gtk3(out, sinks, links, def_sink)
            self._prefs_box.show_all()

        n_out = len(out)
        n_inp = len(inp)
        n_sinks = len(sinks)
        n_sources = len(sources)
        parts = []
        if n_out == 1:
            parts.append("1 application")
        elif n_out > 1:
            parts.append(f"{n_out} applications")
        if n_inp == 1:
            parts.append("1 capture")
        elif n_inp > 1:
            parts.append(f"{n_inp} captures")
        parts.append(
            f"{n_sinks} sortie{'s' if n_sinks > 1 else ''}"
            f" · {n_sources} micro{'s' if n_sources > 1 else ''}"
        )
        self._status_label.set_text("  ·  ".join(parts))

    def _apply_startup_routing(self) -> bool:
        """Applique les routages sauvegardés au démarrage (une seule fois)."""
        try:
            out, sinks, links, _, _, def_sink, _ = audio.get_full_audio_state()
            saved = config.get_stream_routing()
            for stream in out:
                names = saved.get(stream.app_name)
                if names:
                    ids = [s.node_id for s in sinks if s.name in names]
                    if ids:
                        audio.apply_stream_routing(stream.node_id, ids)
        except Exception:
            pass
        return False  # Ne pas répéter

    # -----------------------------------------------------------------------
    # Onglet Sorties — Adwaita
    # -----------------------------------------------------------------------

    def _rebuild_sortie_tab(self, out, sinks, links, def_sink) -> None:
        # Capturer l'état des expanders avant de vider (déjà dans _expander_states)
        self._clear_box(self._sortie_page_box)
        self._stream_checkboxes = {}
        self._stream_vol_scales = {}
        self._stream_bal_scales = {}
        self._stream_mute_btns  = {}
        self._sink_vol_scales   = {}
        self._sink_mute_btns    = {}
        self._master_vol_scales = {}
        self._master_mute_btns  = {}

        page = Adw.PreferencesPage()

        # Volume général (sink par défaut)
        if def_sink:
            ds = next((s for s in sinks if s.node_id == def_sink), None)
            if ds:
                page.add(self._build_master_volume_group(
                    ds.node_id, ds.volume, ds.muted, "Volume de sortie", "sortie",
                ))

        page.add(self._build_sinks_group(sinks, def_sink))
        page.add(self._build_output_streams_group(out, sinks, links, def_sink))
        self._sortie_page_box.append(page)

    # -----------------------------------------------------------------------
    # Onglet Entrées — Adwaita
    # -----------------------------------------------------------------------

    def _rebuild_entree_tab(self, inp, sources, def_src) -> None:
        self._clear_box(self._entree_page_box)
        self._source_vol_scales = {}
        self._source_mute_btns  = {}
        self._master_vol_scales = {}
        self._master_mute_btns  = {}

        page = Adw.PreferencesPage()

        # Volume général (source par défaut)
        if def_src:
            ds = next((s for s in sources if s.node_id == def_src), None)
            if ds:
                page.add(self._build_master_volume_group(
                    ds.node_id, ds.volume, ds.muted, "Volume d'entrée", "entree",
                ))

        page.add(self._build_sources_group(sources, def_src))

        if inp:
            page.add(self._build_input_streams_group(inp))

        self._entree_page_box.append(page)

    # -----------------------------------------------------------------------
    # Groupes Adwaita
    # -----------------------------------------------------------------------

    def _build_master_volume_group(
        self, node_id: int, volume: float, muted: bool, title: str, tab: str,
    ) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title=title)
        pct = int(round(volume * 100))

        row = Adw.ActionRow()
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
        scale.set_value(pct)
        scale.set_draw_value(False)
        scale.set_size_request(260, -1)
        scale.set_valign(Gtk.Align.CENTER)
        vol_lbl = Gtk.Label(label=f"{pct}%")
        vol_lbl.set_width_chars(5)
        vol_lbl.set_xalign(1)
        scale.connect("value-changed", self._on_volume_changed, vol_lbl, node_id, title)
        self._master_vol_scales[node_id] = scale

        mute_btn = Gtk.Button()
        mute_btn.set_icon_name(
            "audio-volume-muted-symbolic" if muted else "audio-volume-high-symbolic"
        )
        mute_btn.set_valign(Gtk.Align.CENTER)
        mute_btn.connect("clicked", self._on_toggle_mute, mute_btn, node_id)
        self._master_mute_btns[node_id] = mute_btn

        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        ctrl.set_valign(Gtk.Align.CENTER)
        ctrl.append(scale)
        ctrl.append(vol_lbl)
        ctrl.append(mute_btn)
        row.add_suffix(ctrl)
        group.add(row)
        return group

    def _build_sinks_group(
        self, sinks: list[audio.AudioSink], default_sink_id: int | None,
    ) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Sorties audio",
            description="Sélectionnez la sortie par défaut et ajustez son volume.",
        )
        if not sinks:
            group.add(Adw.ActionRow(
                title="Aucune sortie détectée",
                subtitle="Vérifiez que PipeWire est actif.",
            ))
            return group

        for sink in sinks:
            pct = int(round(sink.volume * 100))
            is_default = sink.node_id == default_sink_id
            name = _sink_label(sink.name)

            row = Adw.ActionRow(
                title=name,
                subtitle="\u2713 Sortie par d\u00e9faut" if is_default else "",
            )
            row.set_title_lines(1)  # Troncature avec \u2026 au lieu du wrap caract\u00e8re par caract\u00e8re
            row.set_tooltip_text(name)  # Titre complet au survol
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
            scale.set_value(pct)
            scale.set_draw_value(False)
            scale.set_size_request(150, -1)
            scale.set_valign(Gtk.Align.CENTER)
            vol_lbl = Gtk.Label(label=f"{pct}%")
            vol_lbl.set_width_chars(5)
            vol_lbl.set_xalign(1)
            scale.connect("value-changed", self._on_volume_changed, vol_lbl, sink.node_id, name)
            self._sink_vol_scales[sink.node_id] = scale

            mute_btn = Gtk.Button()
            mute_btn.set_icon_name(
                "audio-volume-muted-symbolic" if sink.muted
                else "audio-volume-high-symbolic"
            )
            mute_btn.set_valign(Gtk.Align.CENTER)
            mute_btn.connect("clicked", self._on_toggle_mute, mute_btn, sink.node_id,
                             "audio-volume-high-symbolic")
            self._sink_mute_btns[sink.node_id] = mute_btn

            ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            ctrl.set_valign(Gtk.Align.CENTER)
            ctrl.append(scale)
            ctrl.append(vol_lbl)
            ctrl.append(mute_btn)
            row.add_suffix(ctrl)

            if not is_default:
                def_btn = Gtk.Button()
                def_btn.set_icon_name("starred-symbolic")
                def_btn.set_tooltip_text("Définir comme sortie par défaut")
                def_btn.add_css_class("flat")
                def_btn.set_valign(Gtk.Align.CENTER)
                def_btn.connect("clicked", self._on_set_default_sink, sink.node_id, name)
                row.add_suffix(def_btn)

            group.add(row)
        return group

    def _build_sources_group(
        self, sources: list[audio.AudioSource], default_source_id: int | None,
    ) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Périphériques d'entrée",
            description="Microphones et autres sources audio.",
        )
        if not sources:
            group.add(Adw.ActionRow(
                title="Aucun microphone détecté",
                subtitle="Branchez un périphérique d'entrée audio.",
            ))
            return group

        for src in sources:
            pct = int(round(src.volume * 100))
            is_default = src.node_id == default_source_id
            name = _source_label(src.name)

            row = Adw.ActionRow(
                title=name,
                subtitle="\u2713 Entrée par d\u00e9faut" if is_default else "",
            )
            row.set_title_lines(1)
            row.set_tooltip_text(name)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
            scale.set_value(pct)
            scale.set_draw_value(False)
            scale.set_size_request(150, -1)
            scale.set_valign(Gtk.Align.CENTER)
            vol_lbl = Gtk.Label(label=f"{pct}%")
            vol_lbl.set_width_chars(5)
            vol_lbl.set_xalign(1)
            scale.connect("value-changed", self._on_volume_changed, vol_lbl, src.node_id, name)
            self._source_vol_scales[src.node_id] = scale

            mute_btn = Gtk.Button()
            mute_btn.set_icon_name(
                "audio-volume-muted-symbolic" if src.muted
                else "audio-input-microphone-symbolic"
            )
            mute_btn.set_valign(Gtk.Align.CENTER)
            mute_btn.connect("clicked", self._on_toggle_mute, mute_btn, src.node_id,
                             "audio-input-microphone-symbolic")
            self._source_mute_btns[src.node_id] = mute_btn

            ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            ctrl.set_valign(Gtk.Align.CENTER)
            ctrl.append(scale)
            ctrl.append(vol_lbl)
            ctrl.append(mute_btn)
            row.add_suffix(ctrl)

            if not is_default:
                def_btn = Gtk.Button()
                def_btn.set_icon_name("starred-symbolic")
                def_btn.set_tooltip_text("Définir comme entrée par défaut")
                def_btn.add_css_class("flat")
                def_btn.set_valign(Gtk.Align.CENTER)
                def_btn.connect("clicked", self._on_set_default_source, src.node_id, name)
                row.add_suffix(def_btn)

            group.add(row)
        return group

    def _build_output_streams_group(
        self,
        streams: list[audio.AudioStream],
        sinks: list[audio.AudioSink],
        links: list[audio.AudioLink],
        default_sink_id: int | None,
    ) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Applications en cours",
            description="Volume, balance et routage par application.",
        )
        if not streams:
            group.add(Adw.ActionRow(
                title="Aucune application active",
                subtitle="Lancez une application utilisant le son pour la voir ici.",
            ))
            return group

        saved_routing = config.get_stream_routing()

        label_counts: dict[str, int] = {}
        for s in streams:
            lbl = _app_label(s.app_name, s.node_name)
            label_counts[lbl] = label_counts.get(lbl, 0) + 1
        label_idx: dict[str, int] = {}

        for stream in streams:
            base_name = _app_label(stream.app_name, stream.node_name)
            if label_counts.get(base_name, 1) > 1:
                label_idx[base_name] = label_idx.get(base_name, 0) + 1
                app_name = (
                    base_name if label_idx[base_name] == 1
                    else f"{base_name} ({label_idx[base_name]})"
                )
            else:
                app_name = base_name

            media = stream.media_name or ""

            saved_names = saved_routing.get(stream.app_name)
            if saved_names is not None:
                routed_ids = {s.node_id for s in sinks if s.name in saved_names}
                is_default_routing = False
            else:
                sl = [lk for lk in links if lk.source_node_id == stream.node_id]
                routed_ids = {lk.dest_node_id for lk in sl}
                is_default_routing = not routed_ids
                if is_default_routing and default_sink_id is not None:
                    routed_ids = {default_sink_id}

            routed_labels = [_sink_label(s.name) for s in sinks if s.node_id in routed_ids]
            subtitle = media  # routing affiché en toast uniquement

            if len(sinks) <= 1:
                group.add(Adw.ActionRow(title=app_name, subtitle=subtitle))
                continue

            expander = Adw.ExpanderRow(title=app_name, subtitle=subtitle)
            expander.set_title_lines(1)
            expander.set_subtitle_lines(1)
            # Restaurer l'état d'expansion précédent
            expander.set_expanded(self._expander_states.get(stream.node_id, False))
            expander.connect("notify::expanded", self._on_expander_changed, stream.node_id)

            # ── Volume de l'application ──────────────────────────────────
            pct = int(round(stream.volume * 100))
            vol_row = Adw.ActionRow(title="Volume")
            v_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
            v_scale.set_value(pct)
            v_scale.set_draw_value(False)
            v_scale.set_size_request(200, -1)
            v_scale.set_valign(Gtk.Align.CENTER)
            v_lbl = Gtk.Label(label=f"{pct}%")
            v_lbl.set_width_chars(5)
            v_lbl.set_xalign(1)
            v_scale.connect("value-changed", self._on_volume_changed, v_lbl, stream.node_id, app_name)
            self._stream_vol_scales[stream.node_id] = v_scale
            s_mute = Gtk.Button()
            s_mute.set_icon_name(
                "audio-volume-muted-symbolic" if stream.muted else "audio-volume-high-symbolic"
            )
            s_mute.set_valign(Gtk.Align.CENTER)
            s_mute.connect("clicked", self._on_toggle_mute, s_mute, stream.node_id,
                           "audio-volume-high-symbolic")
            self._stream_mute_btns[stream.node_id] = s_mute
            v_ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            v_ctrl.set_valign(Gtk.Align.CENTER)
            v_ctrl.append(v_scale)
            v_ctrl.append(v_lbl)
            v_ctrl.append(s_mute)
            vol_row.add_suffix(v_ctrl)
            expander.add_row(vol_row)

            # ── Balance gauche / droite ──────────────────────────────────
            bal_row = Adw.ActionRow(title="Balance")
            g_lbl = Gtk.Label(label="◄ G")
            g_lbl.add_css_class("dim-label")
            d_lbl = Gtk.Label(label="D ►")
            d_lbl.add_css_class("dim-label")
            b_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -100, 100, 1)
            b_scale.set_value(int(stream.balance * 100))
            b_scale.set_draw_value(False)
            b_scale.set_size_request(200, -1)
            b_scale.set_valign(Gtk.Align.CENTER)
            b_scale.connect("value-changed", self._on_balance_changed, stream.node_id)
            self._stream_bal_scales[stream.node_id] = b_scale
            reset_bal = Gtk.Button()
            reset_bal.set_icon_name("edit-undo-symbolic")
            reset_bal.set_tooltip_text("Centrer la balance")
            reset_bal.set_valign(Gtk.Align.CENTER)
            reset_bal.add_css_class("flat")
            reset_bal.connect("clicked", lambda *_, sc=b_scale: sc.set_value(0))
            b_ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            b_ctrl.set_valign(Gtk.Align.CENTER)
            b_ctrl.append(g_lbl)
            b_ctrl.append(b_scale)
            b_ctrl.append(d_lbl)
            b_ctrl.append(reset_bal)
            bal_row.add_suffix(b_ctrl)
            expander.add_row(bal_row)

            # ── Routage vers les sinks ───────────────────────────────────
            self._stream_checkboxes[stream.node_id] = {}
            for sink in sinks:
                sink_name = _sink_label(sink.name)
                is_sink_default = sink.node_id == default_sink_id
                sink_row = Adw.ActionRow(
                    title=sink_name,
                    subtitle="Sortie par défaut" if is_sink_default else "",
                )
                cb = Gtk.CheckButton()
                cb.set_active(sink.node_id in routed_ids)
                cb.set_valign(Gtk.Align.CENTER)
                self._stream_checkboxes[stream.node_id][sink.node_id] = cb
                sink_row.add_prefix(cb)
                sink_row.set_activatable_widget(cb)
                expander.add_row(sink_row)

            apply_row = Adw.ActionRow()
            apply_btn = Gtk.Button(label="Appliquer le routage")
            apply_btn.add_css_class("suggested-action")
            apply_btn.set_valign(Gtk.Align.CENTER)
            apply_btn.connect(
                "clicked",
                self._on_apply_routing,
                stream.node_id, stream.app_name, sinks, expander, media,
            )
            apply_row.add_suffix(apply_btn)
            expander.add_row(apply_row)

            group.add(expander)

        return group

    def _build_input_streams_group(
        self, inp: list[audio.AudioStream],
    ) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title="Applications d'enregistrement",
            description="Applications capturant de l'audio en entrée.",
        )
        if not inp:
            return group

        for stream in inp:
            app_name = _app_label(stream.app_name, stream.node_name)
            media = stream.media_name or ""
            pct = int(round(stream.volume * 100))

            row = Adw.ExpanderRow(
                title=app_name,
                subtitle=media if media else "Enregistrement en cours",
            )
            v_row = Adw.ActionRow(title="Volume")
            v_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 1)
            v_scale.set_value(pct)
            v_scale.set_draw_value(False)
            v_scale.set_size_request(200, -1)
            v_scale.set_valign(Gtk.Align.CENTER)
            v_lbl = Gtk.Label(label=f"{pct}%")
            v_lbl.set_width_chars(5)
            v_lbl.set_xalign(1)
            v_scale.connect("value-changed", self._on_volume_changed, v_lbl, stream.node_id, app_name)
            v_ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            v_ctrl.set_valign(Gtk.Align.CENTER)
            v_ctrl.append(v_scale)
            v_ctrl.append(v_lbl)
            v_row.add_suffix(v_ctrl)
            row.add_row(v_row)
            group.add(row)

        return group

    # -----------------------------------------------------------------------
    # Section "Sorties audio" — GTK3 (fallback)
    # -----------------------------------------------------------------------

    def _build_sinks_gtk3(self, sinks, default_sink_id) -> None:
        hdr = Gtk.Label()
        hdr.set_markup("<b>Sorties audio</b>")
        hdr.set_alignment(0, 0)
        self._prefs_box.pack_start(hdr, False, False, 0)
        for sink in sinks:
            pct = int(round(sink.volume * 100))
            is_default = sink.node_id == default_sink_id
            name = _sink_label(sink.name)
            row = Gtk.HBox(spacing=8)
            name_lbl = Gtk.Label()
            name_lbl.set_markup(f"<b>{name}</b>" + (" ★" if is_default else ""))
            name_lbl.set_alignment(0, 0)
            name_lbl.set_size_request(140, -1)
            row.pack_start(name_lbl, False, False, 0)
            scale = Gtk.HScale(adjustment=Gtk.Adjustment(pct, 0, 150, 1, 10, 0))
            scale.set_draw_value(False)
            vol_lbl = Gtk.Label(label=f"{pct}%")
            vol_lbl.set_size_request(40, -1)
            scale.connect("value-changed", self._on_volume_changed, vol_lbl, sink.node_id, name)
            row.pack_start(scale, True, True, 0)
            row.pack_end(vol_lbl, False, False, 0)
            if not is_default:
                def_btn = Gtk.Button(label="Défaut")
                def_btn.connect("clicked", self._on_set_default_sink, sink.node_id, name)
                row.pack_end(def_btn, False, False, 0)
            self._prefs_box.pack_start(row, False, False, 0)

    def _build_streams_gtk3(self, streams, sinks, links, default_sink_id) -> None:
        hdr = Gtk.Label()
        hdr.set_markup("<b>Applications en cours</b>")
        hdr.set_alignment(0, 0)
        hdr.set_margin_top(12)
        self._prefs_box.pack_start(hdr, False, False, 0)
        if not streams:
            self._prefs_box.pack_start(
                Gtk.Label(label="Aucune application audio active"), False, False, 0,
            )
            return
        self._stream_checkboxes = {}
        saved_routing = config.get_stream_routing()
        for stream in streams:
            app_name = _app_label(stream.app_name, stream.node_name)
            saved_names = saved_routing.get(stream.app_name)
            if saved_names is not None:
                routed_ids = {s.node_id for s in sinks if s.name in saved_names}
            else:
                sl = [lk for lk in links if lk.source_node_id == stream.node_id]
                routed_ids = {lk.dest_node_id for lk in sl}
                if not routed_ids and default_sink_id is not None:
                    routed_ids = {default_sink_id}
            frame_lbl = app_name
            if stream.media_name:
                frame_lbl += f"  —  {stream.media_name}"
            frame = Gtk.Frame()
            frame.set_margin_top(6)
            frame.set_label(frame_lbl)
            inner = Gtk.VBox(spacing=4)
            inner.set_margin_top(4)
            inner.set_margin_start(8)
            inner.set_margin_end(8)
            inner.set_margin_bottom(6)
            frame.add(inner)
            if len(sinks) > 1:
                self._stream_checkboxes[stream.node_id] = {}
                inner.pack_start(Gtk.Label(label="Envoyer vers :"), False, False, 0)
                for sink in sinks:
                    sink_name = _sink_label(sink.name)
                    cb = Gtk.CheckButton(label=sink_name)
                    cb.set_active(sink.node_id in routed_ids)
                    self._stream_checkboxes[stream.node_id][sink.node_id] = cb
                    inner.pack_start(cb, False, False, 0)
                apply_btn = Gtk.Button(label="Appliquer")
                apply_btn.connect(
                    "clicked",
                    self._on_apply_routing,
                    stream.node_id, stream.app_name, sinks, None, stream.media_name,
                )
                inner.pack_start(apply_btn, False, False, 2)
            self._prefs_box.pack_start(frame, False, False, 0)

    # -----------------------------------------------------------------------
    # Callbacks
    # -----------------------------------------------------------------------

    def _on_set_default_sink(self, _btn, node_id: int, name: str) -> None:
        # Sauvegarder les volumes actuels avant que WirePlumber ne les change
        try:
            out, sinks, _, _, _, _, _ = audio.get_full_audio_state()
            vol_snap = {s.node_id: s.volume for s in out}
            vol_snap.update({s.node_id: s.volume for s in sinks})
        except Exception:
            vol_snap = {}

        audio.set_default_sink(node_id)
        config.save_default_sink(node_id)
        self._status_label.set_text(f"Sortie par défaut : {name}")

        def _restore_and_refresh():
            for nid, vol in vol_snap.items():
                audio.set_node_volume(nid, int(vol * 100))
            self._refresh_ui()
            return False

        GLib.timeout_add(200, _restore_and_refresh)

    def _on_set_default_source(self, _btn, node_id: int, name: str) -> None:
        audio.set_default_source(node_id)
        self._status_label.set_text(f"Entrée par défaut : {name}")
        GLib.timeout_add(200, lambda: (self._refresh_ui(), False)[1])

    def _on_volume_changed(
        self,
        scale: Gtk.Scale,
        vol_lbl: Gtk.Label,
        node_id: int,
        name: str,
    ) -> None:
        pct = int(round(scale.get_value()))
        vol_lbl.set_text(f"{pct}%")  # Toujours mettre à jour l'étiquette
        if self._updating:
            return  # Mise à jour programmatique : ne pas renvoyer à PipeWire
        # Débounce 50 ms : annuler l'ancien timer et en émettre un nouveau
        old = self._vol_timers.get(node_id)
        if old:
            GLib.source_remove(old)
        self._vol_timers[node_id] = GLib.timeout_add(50, self._flush_volume, node_id, pct)

    def _flush_volume(self, node_id: int, pct: int) -> bool:
        """Appelé par le timer de débounce : envoie réellement le volume à PipeWire."""
        self._vol_timers.pop(node_id, None)
        audio.set_node_volume(node_id, pct)
        return False  # Ne pas répéter

    def _on_toggle_mute(
        self, _btn: Gtk.Button, icon_btn: Gtk.Button, node_id: int,
        unmuted_icon: str = "audio-volume-high-symbolic",
    ) -> None:
        audio.toggle_mute(node_id)
        cur = icon_btn.get_icon_name()
        icon_btn.set_icon_name(
            unmuted_icon
            if cur == "audio-volume-muted-symbolic"
            else "audio-volume-muted-symbolic"
        )

    def _on_balance_changed(self, scale: Gtk.Scale, node_id: int) -> None:
        if self._updating:
            return
        balance = scale.get_value() / 100.0
        # Passer le volume actuel pour préserver le niveau perçu lors du changement de balance
        vol_scale = self._stream_vol_scales.get(node_id)
        current_vol = (vol_scale.get_value() / 100.0) if vol_scale else 1.0
        audio.set_node_balance(node_id, balance, current_vol)

    def _on_apply_routing(
        self,
        _btn,
        stream_node_id: int,
        app_name: str,
        sinks: list[audio.AudioSink],
        expander,
        media: str,
    ) -> None:
        if stream_node_id not in self._stream_checkboxes:
            return
        selected_ids = [
            sid
            for sid, cb in self._stream_checkboxes[stream_node_id].items()
            if cb.get_active()
        ]
        audio.apply_stream_routing(stream_node_id, selected_ids)
        config.save_stream_routing(
            app_name,
            [s.name for s in sinks if s.node_id in selected_ids],
        )
        routed_labels = [_sink_label(s.name) for s in sinks if s.node_id in selected_ids]
        if not routed_labels:
            routing_text = "Routage : sortie par défaut"
        elif len(routed_labels) == 1:
            routing_text = f"Routage → {routed_labels[0]}"
        else:
            routing_text = f"Routage → {routed_labels[0]} + {len(routed_labels) - 1} autre(s)"
        self._show_toast(routing_text)
        if expander is not None and HAS_ADWAITA:
            expander.set_subtitle(media)
            expander.set_expanded(False)
        else:
            self._refresh_ui()

    # -----------------------------------------------------------------------
    # Utilitaires
    # -----------------------------------------------------------------------

    def _show_toast(self, text: str) -> None:
        """Affiche une notification éphémère (Adw.Toast) ou met à jour le status label."""
        if HAS_ADWAITA and self._toast_overlay is not None:
            toast = Adw.Toast.new(text)
            toast.set_timeout(3)
            self._toast_overlay.add_toast(toast)
        else:
            self._status_label.set_text(text)

    def _on_expander_changed(self, expander, _pspec, node_id: int) -> None:
        """Mémorise l'état ouvert/fermé d'un ExpanderRow pour le restaurer après rebuild."""
        self._expander_states[node_id] = expander.get_expanded()

    def _update_volumes_in_place(
        self,
        out: list,
        sinks: list,
        inp: list,
        sources: list,
    ) -> None:
        """Met à jour sliders et icônes mute sans reconstruire toute l'UI."""
        for s in out:
            sc = self._stream_vol_scales.get(s.node_id)
            if sc:
                sc.set_value(int(round(s.volume * 100)))
            bal = self._stream_bal_scales.get(s.node_id)
            if bal:
                bal.set_value(int(round(s.balance * 100)))
            btn = self._stream_mute_btns.get(s.node_id)
            if btn:
                btn.set_icon_name(
                    "audio-volume-muted-symbolic" if s.muted else "audio-volume-high-symbolic"
                )
        for s in sinks:
            sc = self._sink_vol_scales.get(s.node_id)
            if sc:
                sc.set_value(int(round(s.volume * 100)))
            sc = self._master_vol_scales.get(s.node_id)
            if sc:
                sc.set_value(int(round(s.volume * 100)))
            btn = self._sink_mute_btns.get(s.node_id)
            if btn:
                btn.set_icon_name(
                    "audio-volume-muted-symbolic" if s.muted else "audio-volume-high-symbolic"
                )
            btn = self._master_mute_btns.get(s.node_id)
            if btn:
                btn.set_icon_name(
                    "audio-volume-muted-symbolic" if s.muted else "audio-volume-high-symbolic"
                )
        for s in sources:
            sc = self._source_vol_scales.get(s.node_id)
            if sc:
                sc.set_value(int(round(s.volume * 100)))
            sc = self._master_vol_scales.get(s.node_id)
            if sc:
                sc.set_value(int(round(s.volume * 100)))
            btn = self._source_mute_btns.get(s.node_id)
            if btn:
                btn.set_icon_name(
                    "audio-volume-muted-symbolic" if s.muted else "audio-input-microphone-symbolic"
                )
            btn = self._master_mute_btns.get(s.node_id)
            if btn:
                btn.set_icon_name(
                    "audio-volume-muted-symbolic" if s.muted else "audio-input-microphone-symbolic"
                )
        for s in inp:
            sc = self._stream_vol_scales.get(s.node_id)
            if sc:
                sc.set_value(int(round(s.volume * 100)))

    def _on_close_request(self, *_) -> bool:
        """GTK4 : masquer la fenêtre au lieu de la fermer."""
        self.hide()
        return True  # True = annuler la fermeture par défaut

    def _on_delete_event(self, *_) -> bool:
        """GTK3 : masquer la fenêtre au lieu de la fermer."""
        self.hide()
        return True  # True = annuler la fermeture par défaut

    @staticmethod
    def _clear_box(box: Gtk.Box) -> None:
        child = box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            box.remove(child)
            child = nxt
