#!/usr/bin/env python3
"""
Linux Audio Manager — Application GTK4 + PipeWire
Routage audio avancé, barre d'état, mise à jour temps réel.

Fichier historique conserve comme reference.
Le point d'entree actif du projet est `audio-hub.py`.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('Gdk', '4.0')

from gi.repository import Gtk, Adw, Gdk, GLib, Pango
import json, re, subprocess, threading
from pathlib import Path


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
.menubutton-no-arrow image { min-width: 0; min-height: 0; padding: 0; margin: 0; }
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
    'speaker': 'audio-speakers-symbolic',
}
_SOURCE_ICON = 'audio-input-microphone-symbolic'


# ─── Persistance ──────────────────────────────────────────────────────────────

class Settings:
    def __init__(self, path: Path):
        self._path = path; self._data: dict = {}; self._load()

    def _load(self):
        try:   self._data = json.loads(self._path.read_text())
        except: self._data = {}

    def save(self):
        try:   self._path.write_text(json.dumps(self._data, indent=2))
        except: pass

    def get(self, *keys, default=None):
        d = self._data
        for k in keys:
            if not isinstance(d, dict): return default
            d = d.get(str(k))
            if d is None: return default
        return d

    def set(self, *args):
        *keys, value = args
        d = self._data
        for k in keys[:-1]: d = d.setdefault(str(k), {})
        d[str(keys[-1])] = value; self.save()


# ─── Modèles ──────────────────────────────────────────────────────────────────

class PipeWireSink:
    def __init__(self, node_id, nick, description, node_name,
                 dev_type, volume, is_muted, is_default, bus='pci'):
        self.id=node_id; self.nick=nick; self.description=description
        self.node_name=node_name; self.type=dev_type; self.volume=volume
        self.is_muted=is_muted; self.is_default=is_default; self.bus=bus
    @property
    def display_name(self): return self.nick if self.nick else self.description
    @property
    def volume_pct(self): return f"{int(self.volume*100)}%"


class PipeWireSource:
    def __init__(self, node_id, nick, description, node_name,
                 dev_type, volume, is_muted, is_default):
        self.id=node_id; self.nick=nick; self.description=description
        self.node_name=node_name; self.type=dev_type; self.volume=volume
        self.is_muted=is_muted; self.is_default=is_default
    @property
    def display_name(self): return self.nick if self.nick else self.description
    @property
    def volume_pct(self): return f"{int(self.volume*100)}%"


class StreamConnection:
    def __init__(self, port_id, port_name, sink_name, sink_port, state):
        self.port_id=port_id; self.port_name=port_name
        self.sink_name=sink_name; self.sink_port=sink_port; self.state=state


class PipeWireStream:
    def __init__(self, node_id, name, pid, sample_rate, media_class,
                 driver_id=None, volume=1.0):
        self.id=node_id; self.name=name; self.pid=pid
        self.sample_rate=sample_rate; self.media_class=media_class
        self.driver_id=driver_id; self.volume=volume
        self.connections: list[StreamConnection] = []
    @property
    def active_connections(self): return [c for c in self.connections if c.state=='active']
    @property
    def connected_sinks(self): return list(dict.fromkeys(c.sink_name for c in self.connections))
    @property
    def volume_pct(self): return f"{int(self.volume*100)}%"


# ─── Backend PipeWire ──────────────────────────────────────────────────────────

class AudioManager:
    def __init__(self):
        self.data_dir = Path.home() / '.local' / 'share' / 'audio-hub'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(self.data_dir / 'settings.json')
        self._journal: list[str] = []
        self._nodes: dict = {}
        self._stream_volumes: dict = {}
        self._ports: dict = {}         # {node_id: [{id, direction, name, channel}]}
        self._port_to_node: dict = {}  # {port_id: node_id}
        self._links: list = []
        self._links_count = 0
        self._sinks: list[PipeWireSink] = []
        self._sources: list[PipeWireSource] = []
        self._streams: list[PipeWireStream] = []
        self.refresh()

    def _run(self, cmd, timeout=5, log=True):
        if log: self._journal.append(f"$ {' '.join(str(c) for c in cmd)}")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if log: self._journal.append("→ OK" if r.returncode==0 else f"→ ERR {r.stderr.strip()[:80]}")
            return r.stdout
        except Exception as e:
            if log: self._journal.append(f"→ EXC: {e}")
            return ""

    def refresh(self):
        status_raw = self._run(['wpctl', 'status'],   log=False)
        nodes_raw  = self._run(['pw-dump', 'Node'],   log=False)
        ports_raw  = self._run(['pw-dump', 'Port'],   log=False)
        links_raw  = self._run(['pw-dump', 'Link'],   log=False)
        self._journal.append("$ wpctl status + pw-dump Node/Port/Link → OK")

        # ── Nœuds ──────────────────────────────────────────────────────
        self._nodes = {}; self._stream_volumes = {}
        try:
            for n in json.loads(nodes_raw):
                info = n.get('info', {})
                nid  = n['id']
                self._nodes[nid] = info.get('props', {})
                pprops = info.get('params', {}).get('Props', [{}])
                if pprops and isinstance(pprops, list):
                    v = pprops[0].get('volume') if isinstance(pprops[0], dict) else None
                    if v is not None: self._stream_volumes[nid] = float(v)
        except Exception: pass

        # ── Ports ──────────────────────────────────────────────────────
        self._ports = {}; self._port_to_node = {}
        try:
            for p in json.loads(ports_raw):
                info = p.get('info', {})
                nid  = info.get('props', {}).get('node.id')
                pid  = p['id']
                if nid is not None:
                    self._ports.setdefault(nid, []).append({
                        'id':        pid,
                        'direction': info.get('direction', ''),
                        'name':      info.get('props', {}).get('port.name', ''),
                        'channel':   info.get('props', {}).get('audio.channel', ''),
                    })
                    self._port_to_node[pid] = nid
        except Exception: pass

        # ── Liens ──────────────────────────────────────────────────────
        self._links = []
        try:
            self._links = json.loads(links_raw)
            self._links_count = len(self._links)
        except Exception: self._links_count = 0

        self._sinks   = self._parse_sinks(status_raw)
        self._sources = self._parse_sources(status_raw)
        self._streams = self._parse_streams(status_raw)

    # ── Parsing ──────────────────────────────────────────────────────────────

    def _parse_node_line(self, line):
        return re.search(r'(\*?)\s*(\d+)\.\s+(.+?)\s+\[vol:\s*([\d.]+)((?:\s+MUTED)?)\]', line)

    def _node_props(self, nid): return self._nodes.get(nid, {})

    def _parse_rate(self, props):
        raw = props.get('node.rate', '1/48000')
        try: return int(raw.split('/')[-1]) if isinstance(raw, str) and '/' in raw else int(raw)
        except: return 48000

    def _parse_sinks(self, status):
        sinks, in_sec = [], False
        for line in status.splitlines():
            if re.search(r'[├└]─\s+Sinks:', line): in_sec=True; continue
            if in_sec:
                if re.search(r'[├└]─', line) and 'Sinks' not in line: break
                m = self._parse_node_line(line)
                if not m: continue
                nid=int(m.group(2)); p=self._node_props(nid)
                bus=p.get('device.bus','pci'); nn=p.get('node.name','')
                sinks.append(PipeWireSink(
                    nid, p.get('node.nick',''), p.get('node.description', m.group(3).strip()), nn,
                    'hdmi' if 'hdmi' in nn.lower() else 'usb' if bus=='usb' or 'usb' in nn.lower() else 'speaker',
                    float(m.group(4)), 'MUTED' in m.group(5), bool(m.group(1).strip()), bus))
        return sinks

    def _parse_sources(self, status):
        sources, in_sec = [], False
        for line in status.splitlines():
            if re.search(r'[├└]─\s+Sources:', line): in_sec=True; continue
            if in_sec:
                if re.search(r'[├└]─', line) and 'Sources' not in line: break
                m = self._parse_node_line(line)
                if not m: continue
                nid=int(m.group(2)); p=self._node_props(nid)
                bus=p.get('device.bus','pci'); nn=p.get('node.name','')
                sources.append(PipeWireSource(
                    nid, p.get('node.nick',''), p.get('node.description', m.group(3).strip()), nn,
                    'usb' if bus=='usb' or 'usb' in nn.lower() else 'speaker',
                    float(m.group(4)), 'MUTED' in m.group(5), bool(m.group(1).strip())))
        return sources

    def _parse_streams(self, status):
        streams, in_sec, cur = [], False, None
        for line in status.splitlines():
            if re.search(r'[└├]─\s+Streams:', line): in_sec=True; continue
            if in_sec:
                if re.search(r'[└├]─', line) and 'Streams' not in line: break
                m = re.search(r'^\s{6,9}(\d+)\.\s+(.+?)(?:\s{3,}|$)', line)
                if m and '>' not in line:
                    nid=int(m.group(1)); p=self._node_props(nid)
                    cur = PipeWireStream(
                        nid, m.group(2).strip(), p.get('application.process.id'),
                        self._parse_rate(p), p.get('media.class','Stream/Output/Audio'),
                        p.get('node.driver-id'), self._stream_volumes.get(nid, 1.0))
                    streams.append(cur); continue
                m2 = re.search(r'^\s{10,}(\d+)\.\s+(\S+)\s+>\s+(.+?):(\S+)\s+\[(\w+)\]', line)
                if m2 and cur:
                    cur.connections.append(StreamConnection(
                        int(m2.group(1)), m2.group(2),
                        m2.group(3).strip(), m2.group(4), m2.group(5)))
        return streams

    # ── Données publiques ─────────────────────────────────────────────────────

    def get_sinks(self):   return self._sinks
    def get_sources(self): return self._sources
    def get_streams(self):
        """Retourne uniquement les vrais flux applicatifs (exclut les nœuds internes PipeWire)."""
        result = []
        for s in self._streams:
            # Exclure les nœuds PipeWire internes (rate < 1000 Hz = nœuds de contrôle)
            if s.sample_rate < 1000:
                continue
            p = self._nodes.get(s.id, {})
            binary = p.get('application.process.binary', '').lower()
            # Exclure les processus internes PipeWire et PulseAudio compat
            if binary in ('pipewire', 'pipewire-pulse', 'wireplumber'):
                continue
            result.append(s)
        return result
    def get_journal(self): return "\n".join(self._journal[-80:])
    def clear_journal(self): self._journal.clear()

    def get_stats(self):
        streams = self.get_streams()
        coherents = sum(1 for st in streams
                        if st.connections and all(c.state=='active' for c in st.connections))
        return {'streams': len(streams), 'devices': len(self._sinks),
                'links': self._links_count, 'coherents': coherents}

    def get_primary_sink(self, stream):
        if stream.driver_id:
            s = next((s for s in self._sinks if s.id == stream.driver_id), None)
            if s: return s
        for name in stream.connected_sinks:
            s = next((s for s in self._sinks
                      if name and (name in s.display_name or s.display_name in name
                                   or (s.nick and name in s.nick))), None)
            if s: return s
        return next((s for s in self._sinks if not s.is_muted),
                    self._sinks[0] if self._sinks else None)

    def get_browser_info(self, stream_id):
        """(browser_name|None, media_title, media_artist, app_name)"""
        p = self._nodes.get(stream_id, {})
        binary  = p.get('application.process.binary', '').lower()
        appname = p.get('application.name', '')
        title   = p.get('media.title', '') or p.get('media.name', '')
        artist  = p.get('media.artist', '')
        app_lower = appname.lower()
        browser = next((name for key, name in _BROWSERS.items()
                        if key in binary or key in app_lower), None)
        return browser, title, artist, appname

    def is_linked(self, stream_id, sink_id):
        for link in self._links:
            info = link.get('info', {})
            o = info.get('output-node-id') or self._port_to_node.get(info.get('output-port-id'))
            i = info.get('input-node-id')  or self._port_to_node.get(info.get('input-port-id'))
            if o == stream_id and i == sink_id: return True
        return False

    # ── Actions ───────────────────────────────────────────────────────────────

    def set_volume(self, node_id, vol):
        self._journal.append(f"# wpctl set-volume {node_id} {vol:.2f}  [device]")
        self._run(['wpctl', 'set-volume', str(node_id), f'{vol:.2f}'], log=False)

    def set_stream_volume(self, stream_id, vol):
        self._journal.append(f"# wpctl set-volume {stream_id} {vol:.2f}  [stream]")
        self._run(['wpctl', 'set-volume', str(stream_id), f'{vol:.2f}'], log=False)

    def apply_stream_params(self, stream_id, balance, mode, base_vol=1.0):
        """Applique balance + mode canal via pw-cli set-param Props."""
        b = float(balance)
        if mode == 'Gauche':
            L, R = base_vol, 0.0
        elif mode == 'Droite':
            L, R = 0.0, base_vol
        elif mode == 'Mono':
            L = R = base_vol * 0.707
        else:
            L = base_vol * min(1.0, (1.0 - b) * 2)
            R = base_vol * min(1.0, b * 2)
            if mode == 'Swap': L, R = R, L
        props = f'{{ "channelVolumes": [{L:.4f}, {R:.4f}] }}'
        self._run(['pw-cli', 'set-param', str(stream_id), 'Props', props], log=False)
        self._journal.append(
            f"# pw-cli set-param {stream_id} Props channelVol=[{L:.3f},{R:.3f}] "
            f"[bal={b:.2f} mode={mode}]")

    def route_stream_to_sink(self, stream_id, sink_id):
        """Crée des liens pw-link entre un flux et un sink."""
        out_ports = {p['channel']: p['id']
                     for p in self._ports.get(stream_id, []) if p['direction'] == 'output'}
        in_ports  = {p['channel']: p['id']
                     for p in self._ports.get(sink_id, [])   if p['direction'] == 'input'}
        linked = 0
        for ch in ('FL', 'FR', 'MONO', 'AUX0', 'AUX1', 'UNKNOWN'):
            if ch in out_ports and ch in in_ports:
                self._run(['pw-link', str(out_ports[ch]), str(in_ports[ch])], log=False)
                linked += 1
        self._journal.append(f"# pw-link stream:{stream_id} → sink:{sink_id} ({linked} ch)")

    def unroute_stream_from_sink(self, stream_id, sink_id):
        """Supprime les liens pw-link entre un flux et un sink."""
        removed = 0
        for link in list(self._links):
            info = link.get('info', {})
            o = info.get('output-node-id') or self._port_to_node.get(info.get('output-port-id'))
            i = info.get('input-node-id')  or self._port_to_node.get(info.get('input-port-id'))
            if o == stream_id and i == sink_id:
                self._run(['pw-link', '-d', str(link['id'])], log=False)
                removed += 1
        self._journal.append(f"# pw-link -d stream:{stream_id} → sink:{sink_id} ({removed} liens)")

    def toggle_mute(self, node_id):
        self._run(['wpctl', 'set-mute', str(node_id), 'toggle'])

    def set_default_sink(self, nid):   self._run(['wpctl', 'set-default', str(nid)])
    def set_default_source(self, nid): self._run(['wpctl', 'set-default', str(nid)])


# ─── Barre d'état système (tray) ─────────────────────────────────────────────

class TrayIcon:
    def __init__(self, app: 'LinuxAudioManagerApp'):
        self._app = app; self._icon = None
        GLib.idle_add(self._try_start)

    def _try_start(self) -> bool:
        try:
            import pystray
            from PIL import Image, ImageDraw
            self._start(pystray, Image, ImageDraw)
        except Exception: pass
        return False

    def _make_image(self, Image, ImageDraw):
        size = 64
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([2, 2, 62, 62], fill=(53, 132, 228, 255))
        d.polygon([(12,22),(12,42),(26,42),(38,54),(38,10),(26,22)], fill=(255,255,255,230))
        for r in [8, 14]:
            d.arc([38-r, 32-r, 38+r, 32+r], -65, 65, fill=(255,255,255,200), width=3)
        return img

    def _start(self, pystray, Image, ImageDraw):
        def show_hide(i=None, _=None): GLib.idle_add(self._app._toggle_window)
        def goto(n):
            def cb(i=None, _=None):
                GLib.idle_add(lambda: (self._app._show_window(), self._app.notebook.set_current_page(n)))
            return cb
        def do_refresh(i=None, _=None): GLib.idle_add(self._app._on_refresh)
        def do_quit(i=None, _=None):    GLib.idle_add(self._app._quit_app)
        menu = pystray.Menu(
            pystray.MenuItem('Linux Audio Manager', show_hide, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('🔊 Périphériques', goto(0)),
            pystray.MenuItem('🔁 Routage',       goto(1)),
            pystray.MenuItem('🔄 Rafraîchir',    do_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('✕  Quitter',       do_quit),
        )
        self._icon = pystray.Icon('audio-hub',
                                   self._make_image(Image, ImageDraw),
                                   'Linux Audio Manager', menu)
        threading.Thread(target=self._icon.run, daemon=True, name='lam-tray').start()

    def available(self) -> bool: return self._icon is not None
    def stop(self):
        if self._icon:
            try: self._icon.stop()
            except: pass


# ─── Application GTK4 ─────────────────────────────────────────────────────────

class LinuxAudioManagerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.github.audio-hub')
        self.connect('activate', self.on_activate)
        self.audio  = AudioManager()
        self.window = None
        self._tray  = None

    def on_activate(self, app):
        css = Gtk.CssProvider()
        css.load_from_data(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.window = self._build_window()
        self._tray  = TrayIcon(self)
        self.window.present()
        # Mise à jour temps réel : check léger toutes les 2 secondes
        GLib.timeout_add_seconds(2, self._auto_refresh)

    # ── Auto-refresh temps réel ───────────────────────────────────────────────

    def _auto_refresh(self) -> bool:
        """Détecte les changements de flux et rafraîchit si nécessaire."""
        try:
            old_ids = frozenset(s.id for s in self.audio.get_streams())
            status  = self.audio._run(['wpctl', 'status'], log=False)
            new_streams = self.audio._parse_streams(status)
            new_ids = frozenset(s.id for s in new_streams)
            if old_ids != new_ids:
                GLib.idle_add(self._on_refresh)
        except Exception:
            pass
        return True  # continuer le timer

    # ── Fenêtre ───────────────────────────────────────────────────────────────

    def _build_window(self):
        win = Adw.ApplicationWindow(application=self)
        win.set_title('Linux Audio Manager')
        win.set_default_size(1180, 780)
        win.connect('close-request', self._on_close_request)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        hbar = Gtk.HeaderBar()

        ref_btn = Gtk.Button(icon_name='view-refresh-symbolic')
        ref_btn.set_tooltip_text('Rafraîchir les données PipeWire')
        ref_btn.connect('clicked', self._on_refresh)
        hbar.pack_end(ref_btn)

        hide_btn = Gtk.Button(icon_name='window-minimize-symbolic')
        hide_btn.set_tooltip_text("Réduire dans la barre d'état")
        hide_btn.connect('clicked', lambda _: self.window.set_visible(False))
        hbar.pack_end(hide_btn)

        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)
        self._append_all_pages()

        main_box.append(hbar)
        main_box.append(self.notebook)
        win.set_content(main_box)
        return win

    def _on_close_request(self, win):
        if self._tray and self._tray.available():
            win.set_visible(False); return True
        return False

    def _on_refresh(self, _=None):
        self.audio.refresh()
        cur = self.notebook.get_current_page()
        while self.notebook.get_n_pages(): self.notebook.remove_page(0)
        self._append_all_pages()
        self.notebook.set_current_page(cur)

    def _append_all_pages(self):
        self.notebook.append_page(self._build_devices_page(), Gtk.Label(label='🔊 Périphériques'))
        self.notebook.append_page(self._build_routing_page(), Gtk.Label(label='🔁 Routage'))
        self.notebook.append_page(self._build_about_page(),   Gtk.Label(label='ℹ️ À propos'))

    def _toggle_window(self):
        if self.window and self.window.get_visible(): self.window.set_visible(False)
        elif self.window: self.window.present()

    def _show_window(self):
        if self.window: self.window.present()

    def _quit_app(self):
        if self._tray: self._tray.stop()
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
        row = Gtk.ListBoxRow(); row.set_activatable(False); row.set_selectable(False)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_margin_top(14); outer.set_margin_start(16)
        outer.set_margin_end(16); outer.set_margin_bottom(14)

        hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        icon = Gtk.Image.new_from_icon_name(
            _SOURCE_ICON if not is_sink else _SINK_ICONS.get(device.type, 'audio-speakers-symbolic'))
        icon.set_icon_size(Gtk.IconSize.LARGE)
        hdr.append(icon)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info_box.set_hexpand(True)
        nm = Gtk.Label(label=device.display_name)
        nm.set_halign(Gtk.Align.START); nm.add_css_class('device-name')
        nm.set_ellipsize(Pango.EllipsizeMode.END)
        sub = Gtk.Label()
        sub.set_markup(f'<small>#{device.id}  ·  {device.type.upper()}  ·  '
                       + self._esc(device.node_name[:55]) + '</small>')
        sub.set_halign(Gtk.Align.START); sub.add_css_class('dim-label')
        sub.set_ellipsize(Pango.EllipsizeMode.END)
        info_box.append(nm); info_box.append(sub)
        hdr.append(info_box)

        badges = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        badges.set_valign(Gtk.Align.CENTER)
        if device.is_muted:
            mb = Gtk.Label(label='🔇 MUET'); mb.add_css_class('dim-label'); badges.append(mb)
        if device.is_default:
            db = Gtk.Label(label='⭐ Défaut'); db.add_css_class('default-badge'); badges.append(db)
        hdr.append(badges); outer.append(hdr)

        ctrl = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ctrl.set_margin_start(48)
        vol_lbl = Gtk.Label(); vol_lbl.set_size_request(56, -1); vol_lbl.set_halign(Gtk.Align.END)
        vol_lbl.set_text('🔇' if device.is_muted else device.volume_pct)
        adj = Gtk.Adjustment(value=device.volume, lower=0.0, upper=2.0,
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
        outer.append(ctrl); row.set_child(outer); return row

    # ══════════════════════════════════════════════════════════════════════════
    # ── Onglet Routage ────────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════

    def _build_routing_page(self):
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_vexpand(True)
        sinks   = self.audio.get_sinks()
        streams = self.audio.get_streams()
        stats   = self.audio.get_stats()

        # ── Barre de statut ──────────────────────────────────────────────
        sbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        sbar.set_margin_top(10); sbar.set_margin_start(18)
        sbar.set_margin_end(18); sbar.set_margin_bottom(8)
        tl = Gtk.Label(); tl.set_markup('<b>Routage PipeWire</b>'); tl.set_halign(Gtk.Align.START)
        sbar.append(tl)
        routed   = sum(1 for st in streams
                       if any(self.audio.is_linked(st.id, s.id) for s in sinks))
        unrouted = len(streams) - routed
        badges_data = [
            (f'{stats["streams"]} flux',    'accent', 'Flux audio actifs'),
            (f'{stats["devices"]} sorties', None,     'Périphériques de sortie'),
            (f'{stats["links"]} liens PW',  None,     'Liaisons PipeWire actives'),
            (f'{routed} routés', 'success' if routed else None, 'Flux avec routage actif'),
        ]
        if unrouted:
            badges_data.append((f'{unrouted} non routé{"s" if unrouted > 1 else ""}',
                                 None, 'Flux sans routage défini'))
        for text, css, tip in badges_data:
            badge = Gtk.Label(label=text); badge.add_css_class('stat-badge')
            badge.add_css_class('dim-label')
            if css: badge.add_css_class(css)
            fr = Gtk.Frame(); fr.set_child(badge); fr.set_tooltip_text(tip); sbar.append(fr)
        spacer = Gtk.Box(); spacer.set_hexpand(True); sbar.append(spacer)
        # Bouton "Tout → défaut"
        default_sink = next((s for s in sinks if s.is_default), sinks[0] if sinks else None)
        if default_sink and streams:
            ra_btn = Gtk.Button(label=f'Tout → {default_sink.display_name[:18]}')
            ra_btn.set_tooltip_text(
                f'Router tous les flux vers {default_sink.display_name}')
            def _do_route_all(_ds=default_sink, _sts=streams):
                for _st in _sts:
                    self.audio.route_stream_to_sink(_st.id, _ds.id)
                self._on_refresh()
            ra_btn.connect('clicked', lambda _: _do_route_all())
            sbar.append(ra_btn)
        rb = Gtk.Button(icon_name='view-refresh-symbolic')
        rb.set_tooltip_text('Rafraîchir'); rb.connect('clicked', self._on_refresh)
        sbar.append(rb)
        outer.append(sbar); outer.append(self._sep())
        # ── Légende des rôles ─────────────────────────────────────────────
        leg = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        leg.set_margin_start(18); leg.set_margin_end(18)
        leg.set_margin_top(5); leg.set_margin_bottom(5)
        leg_lbl = Gtk.Label(); leg_lbl.set_markup('<small><b>Rôles :</b></small>')
        leg_lbl.add_css_class('dim-label'); leg.append(leg_lbl)
        for bl_txt, bl_cls, bl_tip in [
            ('★ Primaire', 'role-primary', 'Sortie principale — écoute exclusive'),
            ('⊕ Miroir',   'role-mirror',  'Copie du son vers une sortie supplémentaire'),
            ('○ Off',      'role-idle',    'Non connecté — flux ignoré par cette sortie'),
        ]:
            bl = Gtk.Label(label=bl_txt); bl.add_css_class('role-badge')
            bl.add_css_class(bl_cls); bl.set_tooltip_text(bl_tip); leg.append(bl)
        outer.append(leg); outer.append(self._sep())

        # ── Zone scrollable ──────────────────────────────────────────────
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_top(14); content.set_margin_start(18)
        content.set_margin_end(18); content.set_margin_bottom(14)

        if not streams:
            empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            empty.set_valign(Gtk.Align.CENTER); empty.set_vexpand(True)
            el = Gtk.Label()
            el.set_markup('<span size="xx-large">🎵</span>\n'
                          '<big><b>Aucun flux audio actif</b></big>\n'
                          '<small>Lancez une application audio pour voir le routage</small>')
            el.set_justify(Gtk.Justification.CENTER); empty.append(el)
            content.append(empty)
        else:
            for stream in streams:
                content.append(self._make_stream_card(stream, sinks))

        scroll.set_child(content); outer.append(scroll)

        # ── Journal ──────────────────────────────────────────────────────
        jl_hdr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        jl_hdr.set_margin_start(18); jl_hdr.set_margin_end(18); jl_hdr.set_margin_top(6)
        jl_lbl = Gtk.Label()
        jl_lbl.set_markup('<small><b>Journal des commandes PipeWire</b></small>')
        jl_lbl.set_halign(Gtk.Align.START); jl_lbl.set_hexpand(True)
        jl_hdr.append(jl_lbl)
        vider_btn = Gtk.Button(label='Vider'); jl_hdr.append(vider_btn)
        outer.append(jl_hdr)
        jl_scroll = Gtk.ScrolledWindow()
        jl_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        jl_scroll.set_size_request(-1, 90)
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
        browser, media_title, media_artist, app_name = self.audio.get_browser_info(stream.id)
        pid_txt = f'PID {stream.pid}' if stream.pid else ''

        row1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row1.set_margin_top(12); row1.set_margin_start(14)
        row1.set_margin_end(14); row1.set_margin_bottom(6)

        # Icône
        icon_lbl = Gtk.Label(label='🌐' if browser else '🎵')
        icon_lbl.set_size_request(22, -1)
        row1.append(icon_lbl)

        # Nom + sous-titre
        name_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        if browser:
            disp = browser
            if media_title:
                disp += f'  —  {media_title[:55]}'
            if media_artist:
                disp += f'  ♪  {media_artist[:30]}'
        else:
            # Préférer le nom applicatif (application.name) au nom du nœud PipeWire
            disp = app_name if app_name else stream.name

        nm_lbl = Gtk.Label()
        nm_lbl.set_markup(f'<b>{self._esc(disp)}</b>')
        nm_lbl.set_halign(Gtk.Align.START)
        nm_lbl.set_ellipsize(Pango.EllipsizeMode.END)
        name_vbox.append(nm_lbl)

        # Sous-titre: nom d'application si différent
        if browser and app_name and app_name != stream.name:
            sub_lbl = Gtk.Label()
            sub_lbl.set_markup(f'<small>via  {self._esc(app_name)}  ·  '
                               f'{self._esc(stream.name)}</small>')
            sub_lbl.set_halign(Gtk.Align.START)
            sub_lbl.add_css_class('dim-label')
            sub_lbl.add_css_class('browser-title')
            sub_lbl.set_ellipsize(Pango.EllipsizeMode.END)
            name_vbox.append(sub_lbl)
        row1.append(name_vbox)

        # Méta
        meta_parts = [f'node:{stream.id}']
        if pid_txt: meta_parts.append(pid_txt)
        meta_parts.append(f'{stream.sample_rate} Hz')
        n_act = len(stream.active_connections)
        if stream.connections: meta_parts.append(f'{n_act}/{len(stream.connections)} conn.')
        meta = Gtk.Label()
        meta.set_markup(f'<small>{"  ·  ".join(meta_parts)}</small>')
        meta.add_css_class('dim-label'); meta.set_hexpand(True)
        meta.set_halign(Gtk.Align.END); meta.set_ellipsize(Pango.EllipsizeMode.START)
        row1.append(meta)

        # Bouton d'expansion (▶ / ▼) — un seul bouton
        expanded = bool(sett.get('ui', 'expanded', str(stream.id), default=False))
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

        def on_bal(sc, st=stream, m=_cur_mode):
            b = sc.get_value()
            sett.set('stream_balance', str(st.id), round(b, 4))
            self.audio.apply_stream_params(st.id, b, m[0], st.volume)
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
        def on_mode(drop, _, st=stream, bs=bal_slider, m=_cur_mode):
            mode = _CHAN_MODES[drop.get_selected()]
            m[0] = mode
            sett.set('stream_mode', str(st.id), mode)
            self.audio.apply_stream_params(st.id, bs.get_value(), mode, st.volume)
        chan_drop.connect('notify::selected', on_mode)
        row2.append(chan_drop)

        # Restaurer et appliquer les paramètres sauvegardés au chargement du flux
        if saved_bal is not None or saved_mode != 'Stéréo':
            GLib.idle_add(lambda sid=stream.id, b=bal_val, m=saved_mode, v=sv_val:
                          self.audio.apply_stream_params(sid, b, m, v) or False)

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
            f'application.name:   {_np.get("application.name","")}\n'
            f'application.binary: {_np.get("application.process.binary","")}\n'
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

        def on_expand(btn, bw=body_wrap, sid=str(stream.id)):
            bw.set_visible(btn.get_active())
            btn.set_label('▼' if btn.get_active() else '▶')
            sett.set('ui', 'expanded', sid, btn.get_active())
        exp_btn.connect('toggled', on_expand)
        return card

    def _get_role(self, stream, sink, primary):
        sett   = self.audio.settings
        saved  = sett.get('routing', str(stream.id), str(sink.id), 'role')
        if saved: return saved
        if sink.is_muted: return 'idle'
        if primary and sink.id == primary.id: return 'PRIMARY'
        connected = any(sink.display_name in c.sink_name or sink.nick in c.sink_name
                        for c in stream.connections)
        return 'MIRROR' if connected else 'idle'

    # ── Entrée de sink (ligne dans la carte flux) ─────────────────────────────

    def _make_sink_entry(self, sink: PipeWireSink, stream: PipeWireStream,
                         role: str, sinks, body_box, rebuild_fn):
        sett = self.audio.settings
        _rd  = {'PRIMARY': '★  Primaire', 'MIRROR': '⊕  Miroir', 'idle': '○  Off'}
        _rc  = {'PRIMARY': 'role-primary', 'MIRROR': 'role-mirror', 'idle': 'role-idle'}

        entry = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        entry.set_margin_top(7); entry.set_margin_bottom(7)
        entry.set_margin_start(6); entry.set_margin_end(6)
        entry.add_css_class('sink-row')

        # Icône
        icon = Gtk.Image.new_from_icon_name(_SINK_ICONS.get(sink.type, 'audio-speakers-symbolic'))
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

        # Menu button (⋯ uniquement, sans flèche)
        menu_btn = Gtk.MenuButton()
        menu_btn.set_always_show_arrow(False)
        menu_btn.set_label('⋯')
        menu_btn.add_css_class('flat')
        menu_btn.add_css_class('menubutton-no-arrow')
        menu_btn.set_tooltip_text('Options')
        entry.append(menu_btn)

        # Logique de changement de rôle
        def apply_role(new_role, pbn=p_btn, mbn=m_btn, obn=o_btn, d=dot, dvl=dv,
                       st=stream, s=sink, rb=rebuild_fn, sl=sinks):
            # Mettre à jour l'UI localement
            pbn.set_active(new_role == 'PRIMARY')
            mbn.set_active(new_role == 'MIRROR')
            obn.set_active(new_role == 'idle')
            if s.is_muted: d.set_markup('<span color="red">🔇</span>')
            elif new_role == 'idle': d.set_markup('<span color="gray">●</span>')
            else: d.set_markup('<span color="green">●</span>')
            dvl.set_markup(f'<small>{s.volume_pct}</small>' if new_role != 'idle' else '')
            sett.set('routing', str(st.id), str(s.id), 'role', new_role)
            # Appliquer le routage PipeWire
            if new_role == 'PRIMARY':
                # Désactiver les autres sinks
                for other in sl:
                    if other.id != s.id:
                        sett.set('routing', str(st.id), str(other.id), 'role', 'idle')
                        self.audio.unroute_stream_from_sink(st.id, other.id)
                self.audio.route_stream_to_sink(st.id, s.id)
                GLib.idle_add(rb)
            elif new_role == 'MIRROR':
                self.audio.route_stream_to_sink(st.id, s.id)
            else:
                self.audio.unroute_stream_from_sink(st.id, s.id)

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
        menu_btn.set_popover(pop)
        return entry

    # ── Popover "⋯" moderne ───────────────────────────────────────────────────

    def _make_sink_popover(self, sink, stream, p_btn, m_btn, o_btn, dot, dv_lbl, apply_role_fn):
        sett = self.audio.settings
        pop  = Gtk.Popover(); pop.set_position(Gtk.PositionType.LEFT)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        vbox.set_margin_top(12); vbox.set_margin_bottom(12)
        vbox.set_margin_start(12); vbox.set_margin_end(12)
        vbox.set_size_request(290, -1)

        # ─ Header ──────────────────────────────────────────────────────
        hdr = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        tl  = Gtk.Label(); tl.set_markup(f'<b>{self._esc(sink.display_name)}</b>')
        tl.set_halign(Gtk.Align.CENTER)
        sl  = Gtk.Label()
        sl.set_markup(f'<small>node:{sink.id}  ·  {sink.type.upper()}'
                      + (f'  ·  {self._esc(sink.bus)}' if sink.bus else '') + '</small>')
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
        adj = Gtk.Adjustment(value=sink.volume, lower=0.0, upper=2.0,
                              step_increment=0.01, page_increment=0.1, page_size=0.0)
        pvs = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj)
        pvs.set_draw_value(False); pvs.set_hexpand(True)
        def on_pvol(sc, s=sink, vl=vol_lbl):
            v=sc.get_value(); s.volume=v; vl.set_text(f'{int(v*100)}%')
            self.audio.set_volume(s.id, v)
        pvs.connect('value-changed', on_pvol)
        vol_row.append(vol_lbl); vol_row.append(pvs)
        vbox.append(vol_row); vbox.append(self._sep())

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
            pop.popdown(); self._show_node_info(sink)

        vbox.append(action_btn('audio-volume-muted-symbolic', 'Basculer muet', do_mute))
        vbox.append(action_btn('starred-symbolic', 'Définir par défaut', do_default))
        vbox.append(action_btn('edit-copy-symbolic', f'Copier node ID  ({sink.id})', do_copy))
        vbox.append(action_btn('help-about-symbolic', 'Infos nœud PipeWire', do_info))

        pop.set_child(vbox); return pop

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
        t_lbl.set_markup('<span size="x-large"><b>Linux Audio Manager</b></span>')
        v_lbl = Gtk.Label()
        v_lbl.set_markup('<span color="gray">v1.0  ·  Routage audio PipeWire avancé</span>')
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
        tray_ok   = bool(self._tray and self._tray.available())
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

        # ── Ligne tray avec mise à jour différée (TrayIcon init asynchrone) ──
        _tray_vl = Gtk.Label(label='Vérification…'); _tray_vl.set_halign(Gtk.Align.START)
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
            ok = bool(self._tray and self._tray.available())
            vl.set_text('Active — icône dans la barre système' if ok
                        else 'Inactive (pystray non installé)')
            ic.set_from_icon_name('emblem-ok-symbolic' if ok else 'dialog-warning-symbolic')
            return False
        GLib.timeout_add(1500, _upd_tray_row)

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
            info_row('Rafraîchissement', 'Automatique toutes les 2 secondes'),
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


# ─── Entrée ───────────────────────────────────────────────────────────────────

def main():
    app = LinuxAudioManagerApp()
    return app.run()

if __name__ == '__main__':
    exit(main())
