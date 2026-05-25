"""
Backend PipeWire pour Linux Audio Manager.

Lecture via pw-dump, écriture via wpctl / pw-cli / pw-link / pw-metadata.
Aucune bibliothèque tierce n'est requise.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Détection des PWA Chrome/Chromium via MPRIS
# ---------------------------------------------------------------------------

_CHROME_BINARIES = {"chrome", "chromium", "google-chrome", "google-chrome-stable", "chromium-browser"}

# Cache MPRIS par ppid : {ppid: (title_ou_None, expiry_monotonic)}
# Évite de requêter D-Bus à chaque tick de 2 s.
_mpris_title_cache: dict[int, tuple[str | None, float]] = {}
_MPRIS_CACHE_TTL = 30.0  # secondes

# Noms de domaines → labels lisibles pour l'affichage
_MPRIS_DOMAIN_LABELS: dict[str, str] = {
    "netflix": "Netflix",
    "youtube": "YouTube",
    "primevideo": "Prime Video",
    "amazon": "Prime Video",
    "spotify": "Spotify",
    "twitch": "Twitch",
    "soundcloud": "SoundCloud",
    "deezer": "Deezer",
    "tidal": "Tidal",
    "disneyplus": "Disney+",
    "hulu": "Hulu",
    "crunchyroll": "Crunchyroll",
    "dailymotion": "Dailymotion",
    "vimeo": "Vimeo",
}


def _get_ppid(pid: int) -> int:
    """Retourne le PID parent depuis /proc/{pid}/status."""
    try:
        for line in open(f"/proc/{pid}/status"):
            if line.startswith("PPid:"):
                return int(line.split()[1])
    except Exception:
        pass
    return 0


def _query_mpris_title(ppid: int) -> str | None:
    """
    Interroge directement l'instance MPRIS du processus Chrome principal (ppid).
    Retourne le xesam:title ou None.
    """
    try:
        for vendor in ("chromium", "chrome"):
            r = subprocess.run(
                [
                    "gdbus", "call", "--session",
                    "--dest", f"org.mpris.MediaPlayer2.{vendor}.instance{ppid}",
                    "--object-path", "/org/mpris/MediaPlayer2",
                    "--method", "org.freedesktop.DBus.Properties.Get",
                    "org.mpris.MediaPlayer2.Player", "Metadata",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if r.returncode != 0:
                continue
            # gdbus délimite les strings avec ' normalement, ou " si apostrophe présente
            m = re.search(r"'xesam:title':\s*<(?:'([^']*)'|\"([^\"]*)\")", r.stdout)
            if m:
                return m.group(1) or m.group(2) or None
    except Exception:
        pass
    return None


def _mpris_title_to_app_name(title: str) -> str | None:
    """
    Tente de convertir un titre MPRIS (ex. 'Accueil - Netflix') en nom d'app lisible.
    Retourne None si le titre ne correspond à aucun service connu.
    """
    lower = title.lower()
    for domain, label in _MPRIS_DOMAIN_LABELS.items():
        if domain in lower:
            return label
    return None


def _get_mpris_title_cached(ppid: int) -> str | None:
    """Variante mise en cache de _query_mpris_title (validité : 30 s)."""
    now = time.monotonic()
    cached = _mpris_title_cache.get(ppid)
    if cached is not None:
        title, expiry = cached
        if now < expiry:
            return title
    title = _query_mpris_title(ppid)
    _mpris_title_cache[ppid] = (title, now + _MPRIS_CACHE_TTL)
    return title


# ---------------------------------------------------------------------------
# Structures de données
# ---------------------------------------------------------------------------

@dataclass
class AudioStream:
    """Flux audio sortant (Stream/Output/Audio) ou entrant (Stream/Input/Audio)."""
    node_id: int
    app_name: str
    media_name: str
    volume: float        # 0.0 – 1.5
    muted: bool = False
    node_name: str = ""
    balance: float = 0.0  # -1.0 (gauche) → 0.0 (centre) → +1.0 (droite)


@dataclass
class AudioSink:
    """Périphérique de sortie audio."""
    node_id: int
    name: str
    volume: float = 1.0
    muted: bool = False


@dataclass
class AudioSource:
    """Périphérique d'entrée audio (microphone, etc.)."""
    node_id: int
    name: str
    volume: float = 1.0
    muted: bool = False


@dataclass
class AudioLink:
    """Connexion entre deux nœuds PipeWire."""
    link_id: int
    source_node_id: int
    dest_node_id: int
    source_name: str
    dest_name: str
    active: bool = True


# ---------------------------------------------------------------------------
# Lecture PipeWire
# ---------------------------------------------------------------------------

def _pw_dump() -> list[dict]:
    """Exécute pw-dump et retourne les nœuds parsés, ou une liste vide."""
    try:
        result = subprocess.run(
            ["pw-dump"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
    except Exception:
        pass
    return []


def _balance_from_channel_volumes(ch_vols: list) -> float:
    """Dérive la balance stéréo [-1=gauche, 0=centre, +1=droite] depuis channelVolumes."""
    if not ch_vols or len(ch_vols) < 2:
        return 0.0
    l, r = float(ch_vols[0]), float(ch_vols[1])
    if l >= r:
        return 0.0 if l < 0.0001 else -(1.0 - r / l)
    else:
        return 0.0 if r < 0.0001 else 1.0 - l / r


def _volume_from_props(params: dict) -> tuple[float, bool, float]:
    """
    Extrait (volume, muted, balance) depuis le bloc Props d'un nœud PipeWire.
    volume : 0.0 – 1.5 ; balance : -1.0 – +1.0.
    """
    props_list = params.get("Props", [])
    if props_list and isinstance(props_list[0], dict):
        entry = props_list[0]
        volume = entry.get("volume")
        ch_vols = entry.get("channelVolumes")
        if volume is None:
            if ch_vols:
                volume = max(ch_vols)
            else:
                sv = entry.get("softVolumes")
                if sv:
                    volume = sum(sv) / len(sv)
        muted = bool(entry.get("mute", False))
        balance = _balance_from_channel_volumes(ch_vols) if ch_vols else 0.0
        return float(volume) if volume is not None else 1.0, muted, balance
    return 1.0, False, 0.0


def _parse_all_nodes(
    nodes: list[dict],
) -> tuple[list[AudioStream], list[AudioSink], list[AudioStream], list[AudioSource]]:
    """
    Parse tous les nœuds PipeWire en une passe.
    Retourne (output_streams, sinks, input_streams, sources).
    """
    output_streams: list[AudioStream] = []
    sinks: list[AudioSink] = []
    input_streams: list[AudioStream] = []
    sources: list[AudioSource] = []
    _mpris_assigned: set[int] = set()  # ppids déjà consommés pour cet appel

    for node in nodes:
        if node.get("type") != "PipeWire:Interface:Node":
            continue

        info = node.get("info", {})
        props = info.get("props", {})
        params = info.get("params", {})
        media_class = props.get("media.class", "")

        # ── Flux de sortie ─────────────────────────────────────────────
        if media_class == "Stream/Output/Audio":
            if props.get("node.virtual"):
                continue
            binary = props.get("application.process.binary", "") or ""
            pid = props.get("application.process.id")
            app_name = (
                props.get("application.name")
                or props.get("app.name")
                or props.get("node.name")
                or "Application inconnue"
            )
            # Pour Chrome/Chromium : utiliser MPRIS pour identifier le contenu
            mpris_title: str | None = None
            if binary.lower() in _CHROME_BINARIES and pid:
                ppid = _get_ppid(int(pid))
                if ppid > 1:
                    # N'assigner le titre qu'au PREMIER stream de cette instance Chrome
                    if ppid not in _mpris_assigned:
                        mpris_title = _get_mpris_title_cached(ppid)
                        if mpris_title:
                            pwa_app = _mpris_title_to_app_name(mpris_title)
                            if pwa_app:
                                app_name = pwa_app
                                if mpris_title.strip().lower() == pwa_app.lower():
                                    mpris_title = None
                            _mpris_assigned.add(ppid)
                # Supprimer "Playback" (valeur générique Chrome sans intérêt)
                raw_media = props.get("media.name") or props.get("node.description") or ""
                if raw_media.lower() == "playback":
                    raw_media = ""
                media_name = mpris_title or raw_media
            else:
                media_name = props.get("media.name") or props.get("node.description") or ""
            volume, muted, balance = _volume_from_props(params)
            output_streams.append(AudioStream(
                node_id=node["id"], app_name=app_name, media_name=media_name,
                volume=volume, muted=muted,
                node_name=props.get("node.name") or "",
                balance=balance,
            ))

        # ── Flux d'entrée (capture) ─────────────────────────────────────
        elif media_class == "Stream/Input/Audio":
            if props.get("node.virtual"):
                continue
            app_name = (
                props.get("application.name")
                or props.get("app.name")
                or props.get("node.name")
                or "Application inconnue"
            )
            media_name = props.get("media.name") or props.get("node.description") or ""
            volume, muted, _ = _volume_from_props(params)
            input_streams.append(AudioStream(
                node_id=node["id"], app_name=app_name, media_name=media_name,
                volume=volume, muted=muted,
                node_name=props.get("node.name") or "",
            ))

        # ── Sorties physiques ───────────────────────────────────────────
        elif media_class in ("Audio/Sink", "Audio/Duplex"):
            if props.get("node.virtual"):
                continue  # Ignorer les sinks virtuels (combined, etc.)
            name = (
                props.get("node.description")
                or props.get("node.nick")
                or props.get("node.name")
                or "Périphérique inconnu"
            )
            volume, muted, _ = _volume_from_props(params)
            sinks.append(AudioSink(node_id=node["id"], name=name, volume=volume, muted=muted))

        # ── Entrées physiques ───────────────────────────────────────────
        elif media_class == "Audio/Source":
            if props.get("node.virtual"):
                continue
            # Filtrer les moniteurs (captures virtuelles de la sortie d'un sink)
            if ".monitor" in (props.get("node.name") or "").lower():
                continue
            name = (
                props.get("node.description")
                or props.get("node.nick")
                or props.get("node.name")
                or "Entrée inconnue"
            )
            volume, muted, _ = _volume_from_props(params)
            sources.append(AudioSource(node_id=node["id"], name=name, volume=volume, muted=muted))

    return output_streams, sinks, input_streams, sources


def _parse_links(nodes: list[dict]) -> list[AudioLink]:
    """Parse les liens depuis des nœuds PipeWire déjà chargés."""
    node_names: dict[int, str] = {}
    for node in nodes:
        if node.get("type") == "PipeWire:Interface:Node":
            info = node.get("info", {})
            props = info.get("props", {})
            node_names[node["id"]] = (
                props.get("application.name")
                or props.get("app.name")
                or props.get("node.name")
                or f"Nœud {node['id']}"
            )

    links: list[AudioLink] = []
    for node in nodes:
        if node.get("type") != "PipeWire:Interface:Link":
            continue
        info = node.get("info", {})
        props = info.get("props", {})
        state = props.get("link.state", "unknown")
        source_id = int(props.get("link.output.node", 0))
        dest_id = int(props.get("link.input.node", 0))
        links.append(AudioLink(
            link_id=node["id"],
            source_node_id=source_id,
            dest_node_id=dest_id,
            source_name=node_names.get(source_id, f"Nœud {source_id}"),
            dest_name=node_names.get(dest_id, f"Nœud {dest_id}"),
            active=state in ("active", "paused"),
        ))

    return links


def _get_wpctl_defaults() -> tuple[int | None, int | None]:
    """Parse wpctl status pour les IDs par défaut (sink_id, source_id)."""
    try:
        r = subprocess.run(["wpctl", "status"], capture_output=True, text=True, timeout=3)
        sink_id: int | None = None
        source_id: int | None = None
        section: str | None = None
        for line in r.stdout.splitlines():
            if re.search(r"Sinks\s*:", line):
                section = "sinks"
            elif re.search(r"Sources\s*:", line):
                section = "sources"
            elif re.search(r"(Streams|Filters|Devices)\s*:", line):
                section = None
            elif section in ("sinks", "sources"):
                m = re.search(r"\*\s+(\d+)\.", line)
                if m:
                    nid = int(m.group(1))
                    if section == "sinks" and sink_id is None:
                        sink_id = nid
                    elif section == "sources" and source_id is None:
                        source_id = nid
        return sink_id, source_id
    except Exception:
        return None, None


def get_full_audio_state() -> tuple[
    list[AudioStream], list[AudioSink], list[AudioLink],
    list[AudioStream], list[AudioSource],
    int | None, int | None,
]:
    """
    Retourne en un seul appel :
      (output_streams, sinks, links, input_streams, sources,
       default_sink_id, default_source_id)
    """
    nodes = _pw_dump()
    output_streams, sinks, input_streams, sources = _parse_all_nodes(nodes)
    links = _parse_links(nodes)
    default_sink_id, default_source_id = _get_wpctl_defaults()
    return output_streams, sinks, links, input_streams, sources, default_sink_id, default_source_id


def get_audio_state() -> tuple[list[AudioStream], list[AudioSink]]:
    """Compatibilité : retourne (output_streams, sinks)."""
    nodes = _pw_dump()
    out, sinks, _, _ = _parse_all_nodes(nodes)
    return out, sinks


# ---------------------------------------------------------------------------
# Écriture PipeWire via WirePlumber (wpctl)
# ---------------------------------------------------------------------------

def set_node_volume(node_id: int, percent: float) -> None:
    """
    Règle le volume d'un nœud PipeWire via wpctl (WirePlumber).
    Plage acceptée : 0 – 150 % (au-delà de 100 % = amplification logicielle).
    """
    value = max(0.0, min(1.5, percent / 100.0))
    try:
        subprocess.run(
            ["wpctl", "set-volume", str(node_id), f"{value:.3f}"],
            capture_output=True,
            timeout=3,
        )
    except Exception:
        pass


def toggle_mute(node_id: int) -> None:
    """Bascule l'état mute d'un nœud via wpctl."""
    try:
        subprocess.run(
            ["wpctl", "set-mute", str(node_id), "toggle"],
            capture_output=True,
            timeout=3,
        )
    except Exception:
        pass


def set_mute(node_id: int, muted: bool) -> None:
    """Force l'état mute (True=muet, False=actif) d'un nœud via wpctl."""
    try:
        subprocess.run(
            ["wpctl", "set-mute", str(node_id), "1" if muted else "0"],
            capture_output=True,
            timeout=3,
        )
    except Exception:
        pass


def get_audio_links() -> list[AudioLink]:
    """Retourne les connexions depuis PipeWire."""
    nodes = _pw_dump()
    return _parse_links(nodes)


def get_default_sink() -> int | None:
    return _get_wpctl_defaults()[0]


def get_default_source() -> int | None:
    return _get_wpctl_defaults()[1]


def set_default_sink(node_id: int) -> None:
    try:
        subprocess.run(["wpctl", "set-default", str(node_id)], capture_output=True, timeout=3)
    except Exception:
        pass


def set_default_source(node_id: int) -> None:
    try:
        subprocess.run(["wpctl", "set-default", str(node_id)], capture_output=True, timeout=3)
    except Exception:
        pass


def set_node_balance(node_id: int, balance: float, current_vol: float = 1.0) -> None:
    """
    Règle la balance stéréo via pw-cli channelVolumes.
    balance     : -1.0 (tout gauche) → 0.0 (centre) → +1.0 (tout droite)
    current_vol : volume actuel du nœud (0.0–1.5) pour préserver le niveau perçu.
    """
    balance = max(-1.0, min(1.0, balance))
    vol = max(0.0, min(1.5, current_vol))
    # Atténuer le canal opposé tout en conservant le volume du canal dominant
    left  = vol * (1.0 - max(0.0,  balance))  # 0.0 quand balance = +1
    right = vol * (1.0 - max(0.0, -balance))  # 0.0 quand balance = -1
    try:
        subprocess.run(
            ["pw-cli", "set-param", str(node_id), "Props",
             f'{{ "channelVolumes": [{left:.4f}, {right:.4f}] }}'],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Routage PipeWire via pw-link / pw-metadata
# ---------------------------------------------------------------------------

def _get_node_ports(nodes: list[dict], node_id: int, direction: str) -> list[tuple[int, str]]:
    """
    Retourne les ports d'un nœud sous forme (port_id, audio_channel).
    direction : 'output' pour les flux sources, 'input' pour les sinks.
    """
    ports = []
    for n in nodes:
        if n.get("type") != "PipeWire:Interface:Port":
            continue
        info = n.get("info", {})
        if info.get("direction") != direction:
            continue
        props = info.get("props", {})
        try:
            if int(props.get("node.id", -1)) != node_id:
                continue
        except (TypeError, ValueError):
            continue
        ch = str(props.get("audio.channel") or props.get("port.name") or "")
        ports.append((n["id"], ch))
    return ports


def _pw_link_ports(out_ports: list[tuple[int, str]], in_ports: list[tuple[int, str]]) -> int:
    """
    Lie chaque port sortant au port entrant correspondant (par canal audio).
    Retourne le nombre de liens créés.
    """
    in_by_ch: dict[str, int] = {ch: pid for pid, ch in in_ports}
    fallback = next(iter(in_by_ch.values()), None) if in_by_ch else None
    linked = 0
    for out_id, ch in out_ports:
        target = in_by_ch.get(ch, fallback)
        if target is None:
            continue
        try:
            r = subprocess.run(
                ["pw-link", str(out_id), str(target)],
                capture_output=True,
                timeout=3,
            )
            if r.returncode == 0:
                linked += 1
        except Exception:
            pass
    return linked


def apply_stream_routing(stream_node_id: int, sink_node_ids: list[int]) -> None:
    """
    Route un flux vers les sinks sélectionnés.

    - 1er sink : pw-metadata target.node  (WirePlumber gère le lien principal)
    - Sinks supplémentaires : pw-link direct  (liens explicites, non gérés par WP)
    - Supprime les anciens liens directs vers les sinks non sélectionnés
    - Sans sélection : réinitialise la cible (suit la sortie par défaut)
    """
    nodes = _pw_dump()

    # Liens actuels partant de ce flux
    current_links = [
        n for n in nodes
        if n.get("type") == "PipeWire:Interface:Link"
        and int(n.get("info", {}).get("props", {}).get("link.output.node", -1)) == stream_node_id
    ]

    if not sink_node_ids:
        # Aucune sélection : revenir à la sortie par défaut
        try:
            subprocess.run(
                ["pw-metadata", str(stream_node_id), "target.node", "0"],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass
        return

    # 1. Définir la cible principale via WirePlumber
    try:
        subprocess.run(
            ["pw-metadata", str(stream_node_id), "target.node", str(sink_node_ids[0])],
            capture_output=True, timeout=3,
        )
    except Exception:
        pass

    # 2. Liens directs vers les sinks supplémentaires
    already_linked = {
        int(lk.get("info", {}).get("props", {}).get("link.input.node", -1))
        for lk in current_links
    }
    out_ports = _get_node_ports(nodes, stream_node_id, "output")
    for sink_id in sink_node_ids[1:]:
        if sink_id not in already_linked:
            in_ports = _get_node_ports(nodes, sink_id, "input")
            _pw_link_ports(out_ports, in_ports)

    # 3. Supprimer les anciens liens directs vers des sinks non sélectionnés
    selected_set = set(sink_node_ids)
    for lk in current_links:
        dest = int(lk.get("info", {}).get("props", {}).get("link.input.node", -1))
        if dest not in selected_set:
            try:
                subprocess.run(
                    ["pw-link", "-d", str(lk["id"])],
                    capture_output=True, timeout=3,
                )
            except Exception:
                pass


def disconnect_link(link_id: int) -> bool:
    """Supprime un lien PipeWire par son ID."""
    try:
        r = subprocess.run(
            ["pw-link", "-d", str(link_id)],
            capture_output=True, timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


def duplicate_stream_to_sink(stream_node_id: int, sink_node_id: int) -> bool:
    """Crée des liens PipeWire d'un flux vers un sink via pw-link."""
    nodes = _pw_dump()
    out_ports = _get_node_ports(nodes, stream_node_id, "output")
    in_ports = _get_node_ports(nodes, sink_node_id, "input")
    if not out_ports or not in_ports:
        return False
    return _pw_link_ports(out_ports, in_ports) > 0


# ---------------------------------------------------------------------------
# Surveillance PipeWire en temps réel (thread daemon)
# ---------------------------------------------------------------------------

_pw_monitor_thread: threading.Thread | None = None
_pw_monitor_pending: bool = False
_pw_monitor_proc: subprocess.Popen | None = None  # processus pw-cli en cours

# Mots-clés déclencheurs dans la sortie de pw-cli monitor :
# - changements de volume / sourdine (Props audio)
# - ajout / suppression d'un nœud (périphérique ou application)
_PW_TRIGGER_KEYWORDS = (
    b" volume:",       # changement de volume (Props)
    b" muted:",        # changement de sourdine
    b" channelVolumes:",  # balance / volumes par canal
    b"remote 0 added",    # nouveau périphérique ou flux
    b"remote 0 removed",  # périphérique ou flux retiré
)


def start_pw_monitor(callback) -> None:
    """
    Démarre (une seule fois) un thread daemon qui surveille `pw-cli monitor`.

    `callback()` est appelé sur le thread principal GLib via idle_add dès qu'un
    changement audio pertinent est détecté (volume, sourdine, appareil branché/retiré).
    Les appels sont dé-dupliqués : au plus un callback en attente à la fois.
    """
    global _pw_monitor_thread
    if _pw_monitor_thread and _pw_monitor_thread.is_alive():
        return
    _pw_monitor_thread = threading.Thread(
        target=_run_pw_monitor, args=(callback,), daemon=True
    )
    _pw_monitor_thread.name = "pw-monitor"
    _pw_monitor_thread.start()


def _run_pw_monitor(callback) -> None:
    """Boucle interne du thread daemon de surveillance PipeWire."""
    global _pw_monitor_pending, _pw_monitor_proc

    while True:
        try:
            proc = subprocess.Popen(
                ["pw-cli", "monitor"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            _pw_monitor_proc = proc
            # Ignorer les ~100 premières lignes : dump de l'état initial au démarrage
            startup_skip = 100
            for raw in proc.stdout:  # type: ignore[union-attr]
                if startup_skip > 0:
                    startup_skip -= 1
                    continue
                if any(kw in raw for kw in _PW_TRIGGER_KEYWORDS):
                    if not _pw_monitor_pending:
                        _pw_monitor_pending = True
                        try:
                            from gi.repository import GLib
                            GLib.idle_add(_fire_pw_callback, callback)
                        except Exception:
                            pass
            proc.wait()
        except Exception:
            pass
        _pw_monitor_proc = None
        # Relancer pw-cli après 5 s si la commande se ferme inopinément
        time.sleep(5)


def _fire_pw_callback(callback) -> bool:
    """Exécuté sur le thread principal GLib ; déclenche le callback puis réinitialise le verrou."""
    global _pw_monitor_pending
    _pw_monitor_pending = False
    try:
        callback()
    except Exception:
        pass
    return False  # Ne pas répéter via GLib.idle_add


def stop_pw_monitor() -> None:
    """Termine le processus pw-cli monitor (appelé au shutdown)."""
    global _pw_monitor_proc
    if _pw_monitor_proc is not None:
        try:
            _pw_monitor_proc.terminate()
        except Exception:
            pass
        _pw_monitor_proc = None


def cleanup_stream_routing() -> None:
    """
    Remet tous les flux audio sur la sortie par défaut en supprimant les
    surcharges de routage (pw-metadata target.node).

    À appeler au shutdown de l'application pour ne pas laisser des
    configurations persistantes dans WirePlumber.
    """
    try:
        out, _, links, inp, _, _, _ = get_full_audio_state()
        for stream in out + inp:
            subprocess.run(
                ["pw-metadata", str(stream.node_id), "target.node", "0"],
                capture_output=True,
                timeout=2,
            )
        # Supprimer les liens pw-link créés explicitement (hors liens WirePlumber)
        # Un lien explicite est reconnaissable à l'absence de gestion par WirePlumber :
        # on supprime tous les liens dont la source est l'un de nos flux.
        stream_ids = {s.node_id for s in out + inp}
        for link in links:
            if link.source_node_id in stream_ids:
                subprocess.run(
                    ["pw-link", "-d", str(link.link_id)],
                    capture_output=True,
                    timeout=2,
                )
    except Exception:
        pass
