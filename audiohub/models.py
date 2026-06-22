"""Persistent settings and PipeWire-facing data models for AudioHub."""

from pathlib import Path
from typing import List

from audio_device_classifier import classify_audio_device


_SINK_ICON_KEYS = {
    'hdmi',
    'usb',
    'bluetooth',
    'headphones',
    'spdif',
    'jack',
    'speaker',
}


def _normalize_settings_fragment(value):
    text = str(value or '').strip().lower()
    if not text:
        return ''
    normalized = []
    previous_sep = False
    for char in text:
        if char.isalnum():
            normalized.append(char)
            previous_sep = False
            continue
        if not previous_sep:
            normalized.append('-')
            previous_sep = True
    return ''.join(normalized).strip('-')


def _extract_sample_rate(props, default=48000):
    candidates = [
        props.get('audio.rate'),
        props.get('node.force-rate'),
        props.get('node.rate'),
    ]
    for raw in candidates:
        try:
            if isinstance(raw, str) and '/' in raw:
                return int(raw.split('/')[-1])
            if raw is not None:
                value = int(raw)
                if value > 0:
                    return value
        except Exception:
            continue
    return default


class Settings:
    def __init__(self, path: Path):
        self._path = path
        self._data: dict = {}
        self._load()

    def _load(self):
        try:
            import json

            self._data = json.loads(self._path.read_text())
        except Exception:
            self._data = {}

    def save(self):
        try:
            import json

            self._path.write_text(json.dumps(self._data, indent=2))
        except Exception:
            pass

    def get(self, *keys, default=None):
        data = self._data
        for key in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(str(key))
            if data is None:
                return default
        return data

    def set(self, *args):
        *keys, value = args
        data = self._data
        for key in keys[:-1]:
            data = data.setdefault(str(key), {})
        data[str(keys[-1])] = value
        self.save()


class PipeWireSink:
    def __init__(
        self,
        node_id,
        nick,
        description,
        node_name,
        dev_type,
        volume,
        is_muted,
        is_default,
        bus='pci',
        props=None,
    ):
        self.id = node_id
        self.nick = nick
        self.description = description
        self.node_name = node_name
        self.type = dev_type
        self.volume = volume
        self.is_muted = is_muted
        self.is_default = is_default
        self.bus = bus
        self.props = dict(props or {})

        info = classify_audio_device(
            self.props or {
                'device.bus': bus,
                'node.name': node_name,
                'node.description': description,
                'node.nick': nick,
            },
            is_sink=True,
            node_name=node_name,
            description=description,
            nick=nick,
        )
        self.transport = info['transport']
        self.transport_label = info['transport_label']
        self.role = info['role']
        self.role_label = info['role_label']
        self.friendly_name = info['display_name']
        self.icon_key = self.transport if self.transport in _SINK_ICON_KEYS else self.role
        self.sample_rate = _extract_sample_rate(self.props)

    @property
    def display_name(self):
        if self.friendly_name:
            return self.friendly_name
        if self.description:
            return self.description
        if self.nick and 'alsa' not in self.nick.lower():
            return self.nick
        return f"Sortie #{self.id}"

    @property
    def volume_pct(self):
        return f"{int(self.volume * 100)}%"

    @property
    def settings_key(self):
        candidates = [
            self.props.get('api.bluez5.address'),
            self.props.get('device.serial'),
            self.props.get('device.bus-path'),
            self.props.get('device.name'),
            self.props.get('object.path'),
            self.props.get('node.name'),
            self.props.get('node.nick'),
            self.friendly_name,
            self.description,
            self.nick,
        ]
        for candidate in candidates:
            normalized = _normalize_settings_fragment(candidate)
            if normalized:
                return f'{self.transport}:{self.role}:{normalized}'
        return f'{self.transport}:{self.role}:sink-{self.id}'


class PipeWireSource:
    def __init__(
        self,
        node_id,
        nick,
        description,
        node_name,
        dev_type,
        volume,
        is_muted,
        is_default,
        bus='pci',
        props=None,
    ):
        self.id = node_id
        self.nick = nick
        self.description = description
        self.node_name = node_name
        self.type = dev_type
        self.volume = volume
        self.is_muted = is_muted
        self.is_default = is_default
        self.peak_level = 0.0
        self._smoothed_level = 0.0
        self.bus = bus

        info = classify_audio_device(
            props or {
                'device.bus': bus,
                'node.name': node_name,
                'node.description': description,
                'node.nick': nick,
            },
            is_sink=False,
            node_name=node_name,
            description=description,
            nick=nick,
        )
        self.transport = info['transport']
        self.transport_label = info['transport_label']
        self.role = info['role']
        self.role_label = info['role_label']
        self.friendly_name = info['display_name']
        self.props = dict(props or {})
        self.sample_rate = _extract_sample_rate(self.props)

    @property
    def is_real_microphone(self):
        return self.role == 'microphone'

    @property
    def display_name(self):
        if self.friendly_name:
            return self.friendly_name
        if self.description:
            return self.description
        if self.role == 'line_in':
            return 'Entrée ligne'
        if self.role == 'microphone':
            return 'Microphone'
        return f"Entrée #{self.id}"

    @property
    def volume_pct(self):
        return f"{int(self.volume * 100)}%"


class StreamConnection:
    def __init__(self, port_id, port_name, sink_name, sink_port, state):
        self.port_id = port_id
        self.port_name = port_name
        self.sink_name = sink_name
        self.sink_port = sink_port
        self.state = state


class PipeWireStream:
    def __init__(self, node_id, name, pid, sample_rate, media_class, driver_id=None, volume=1.0):
        self.id = node_id
        self.name = name
        self.pid = pid
        self.sample_rate = sample_rate
        self.media_class = media_class
        self.driver_id = driver_id
        self.volume = volume
        self.connections: List[StreamConnection] = []

    @property
    def display_name(self):
        name_lower = (self.name or '').lower()
        app_names = {
            'firefox': '🦊 Firefox',
            'chrome': '🌐 Chrome',
            'chromium': '🌐 Chromium',
            'discord': '💬 Discord',
            'spotify': '🎵 Spotify',
            'vlc': '▶️ VLC',
            'pulseaudio': '🔊 PulseAudio',
            'pipewire': '🔊 PipeWire',
            'wine': '🎮 Wine',
            'obs': '📹 OBS',
            'zoom': '📞 Zoom',
            'skype': '📞 Skype',
            'teams': '📞 Microsoft Teams',
        }

        for keyword, display_name in app_names.items():
            if keyword in name_lower:
                return display_name

        if self.name:
            return f"🔊 {self.name}"
        return f"Flux #{self.id}"

    @property
    def active_connections(self):
        return [connection for connection in self.connections if connection.state == 'active']

    @property
    def connected_sinks(self):
        return list(dict.fromkeys(connection.sink_name for connection in self.connections))

    @property
    def volume_pct(self):
        return f"{int(self.volume * 100)}%"
