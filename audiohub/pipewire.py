"""PipeWire backend for AudioHub."""

import json
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List

from .browser_streams import BrowserStreamIdentityMixin
from .models import PipeWireSink, PipeWireSource, PipeWireStream, Settings, StreamConnection


class AudioManager(BrowserStreamIdentityMixin):
    COMMON_SAMPLE_RATES = (32000, 44100, 48000, 88200, 96000, 176400, 192000)

    def __init__(self):
        self.data_dir = Path.home() / '.local' / 'share' / 'audio-hub'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = Settings(self.data_dir / 'settings.json')
        self._journal: list[str] = []
        self._nodes: dict = {}
        self._stream_volumes: dict = {}
        self._ports: Dict = {}
        self._port_to_node: Dict = {}
        self._links: List = []
        self._links_count = 0
        self._sinks: List[PipeWireSink] = []
        self._sources: List[PipeWireSource] = []
        self._streams: List[PipeWireStream] = []

        self._source_threads = {}
        self._audio_running = True
        self._source_peak_levels = {}
        self._sounddevice = self._load_sounddevice()
        self._mpris_cache = {'players': {}, 'expires_at': 0.0}

        self.refresh()

        if self._sounddevice is not None:
            for source in self._sources:
                thread = threading.Thread(
                    target=self._audio_capture_source,
                    args=(source.id, source.description, source.node_name),
                    daemon=True,
                )
                thread.start()
                self._source_threads[source.id] = thread
                time.sleep(0.1)

    @staticmethod
    def _load_sounddevice():
        try:
            import sounddevice as sounddevice_module

            return sounddevice_module
        except ImportError:
            return None

    def _run(self, cmd, timeout=5, log=True):
        if log:
            self._journal.append(f"$ {' '.join(str(part) for part in cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if log:
                message = '→ OK' if result.returncode == 0 else f"→ ERR {result.stderr.strip()[:80]}"
                self._journal.append(message)
            return result.stdout
        except subprocess.TimeoutExpired:
            if log:
                self._journal.append(f"→ TIMEOUT: {timeout}s")
            return ''
        except Exception as exc:
            if log:
                self._journal.append(f"→ EXC: {str(exc)[:80]}")
            return ''

    def refresh(self):
        status_raw = self._run(['wpctl', 'status'], log=False)
        nodes_raw = self._run(['pw-dump', 'Node'], log=False)
        ports_raw = self._run(['pw-dump', 'Port'], log=False)
        links_raw = self._run(['pw-dump', 'Link'], log=False)

        self._nodes = {}
        self._stream_volumes = {}
        try:
            for node in json.loads(nodes_raw):
                info = node.get('info', {})
                node_id = node['id']
                self._nodes[node_id] = info.get('props', {})
                props_list = info.get('params', {}).get('Props', [{}])
                if props_list and isinstance(props_list, list):
                    volume = props_list[0].get('volume') if isinstance(props_list[0], dict) else None
                    if volume is not None:
                        self._stream_volumes[node_id] = float(volume)
        except Exception:
            pass

        self._ports = {}
        self._port_to_node = {}
        try:
            for port in json.loads(ports_raw):
                info = port.get('info', {})
                node_id = info.get('props', {}).get('node.id')
                port_id = port['id']
                if node_id is not None:
                    self._ports.setdefault(node_id, []).append(
                        {
                            'id': port_id,
                            'direction': info.get('direction', ''),
                            'name': info.get('props', {}).get('port.name', ''),
                            'channel': info.get('props', {}).get('audio.channel', ''),
                        }
                    )
                    self._port_to_node[port_id] = node_id
        except Exception:
            pass

        self._links = []
        try:
            self._links = json.loads(links_raw)
            self._links_count = len(self._links)
        except Exception:
            self._links_count = 0

        self._sinks = self._parse_sinks(status_raw)
        self._sources = self._parse_sources(status_raw)
        self._streams = self._parse_streams(status_raw)
        self._restore_sink_sample_rates()

        self._boost_weak_input_volumes()

        active_source_ids = {source.id for source in self._sources}
        self._source_peak_levels = {
            key: value for key, value in self._source_peak_levels.items() if key in active_source_ids
        }
        for source in self._sources:
            if source.id not in self._source_peak_levels:
                self._source_peak_levels[source.id] = 0.0

        self.update_source_peak_levels()

    def _parse_node_line(self, line):
        return re.search(r'(\*?)\s*(\d+)\.\s+(.+?)\s+\[vol:\s*([\d.]+)((?:\s+MUTED)?)\]', line)

    def _node_props(self, node_id):
        return self._nodes.get(node_id, {})

    def _parse_rate(self, props):
        raw = props.get('node.rate', '1/48000')
        try:
            return int(raw.split('/')[-1]) if isinstance(raw, str) and '/' in raw else int(raw)
        except Exception:
            return 48000

    def _parse_sinks(self, status):
        sinks, in_section = [], False
        for line in status.splitlines():
            if re.search(r'[├└]─\s+Sinks:', line):
                in_section = True
                continue
            if in_section:
                if re.search(r'[├└]─', line) and 'Sinks' not in line:
                    break
                match = self._parse_node_line(line)
                if not match:
                    continue
                node_id = int(match.group(2))
                props = self._node_props(node_id)
                bus = props.get('device.bus', 'pci')
                node_name = props.get('node.name', '')
                sinks.append(
                    PipeWireSink(
                        node_id,
                        props.get('node.nick', ''),
                        props.get('node.description', match.group(3).strip()),
                        node_name,
                        props.get('device.bus', 'unknown'),
                        float(match.group(4)),
                        'MUTED' in match.group(5),
                        bool(match.group(1).strip()),
                        bus,
                        props,
                    )
                )
        return sinks

    def _parse_sources(self, status):
        sources, in_section = [], False
        for line in status.splitlines():
            if re.search(r'[├└]─\s+Sources:', line):
                in_section = True
                continue
            if in_section:
                if re.search(r'[├└]─', line) and 'Sources' not in line:
                    break
                match = self._parse_node_line(line)
                if not match:
                    continue
                node_id = int(match.group(2))
                props = self._node_props(node_id)
                bus = props.get('device.bus', 'pci')
                node_name = props.get('node.name', '')
                sources.append(
                    PipeWireSource(
                        node_id,
                        props.get('node.nick', ''),
                        props.get('node.description', match.group(3).strip()),
                        node_name,
                        props.get('device.bus', 'unknown'),
                        float(match.group(4)),
                        'MUTED' in match.group(5),
                        bool(match.group(1).strip()),
                        bus,
                        props,
                    )
                )
        return sources

    def _boost_weak_input_volumes(self):
        for source in self._sources:
            if source.volume > 1.2:
                try:
                    subprocess.run(
                        ['wpctl', 'set-volume', str(source.id), '1.0'],
                        capture_output=True,
                        timeout=2,
                    )
                except Exception:
                    pass

    def _parse_streams(self, status):
        streams, in_section, current, current_indent = [], False, None, None
        for line in status.splitlines():
            if re.search(r'[└├]─\s+Streams:', line):
                in_section = True
                continue
            if in_section:
                if re.search(r'[└├]─', line) and 'Streams' not in line:
                    break
                match = re.search(r'^(\s+)(\d+)\.\s+(.+?)(?:\s{3,}|$)', line)
                if not match:
                    continue

                indent = len(match.group(1))
                if current is None or current_indent is None or indent <= current_indent:
                    node_id = int(match.group(2))
                    props = self._node_props(node_id)
                    current_indent = indent
                    current = PipeWireStream(
                        node_id,
                        match.group(3).strip(),
                        props.get('application.process.id'),
                        self._parse_rate(props),
                        props.get('media.class', 'Stream/Output/Audio'),
                        props.get('node.driver-id'),
                        self._stream_volumes.get(node_id, 1.0),
                    )
                    streams.append(current)
                    continue

                match2 = re.search(r'^\s+(\d+)\.\s+(\S+)\s+>\s+(.+?):(\S+)\s+\[(\w+)\]', line)
                if match2 and current:
                    current.connections.append(
                        StreamConnection(
                            int(match2.group(1)),
                            match2.group(2),
                            match2.group(3).strip(),
                            match2.group(4),
                            match2.group(5),
                        )
                    )
        return streams

    def get_sinks(self):
        return self._sinks

    def get_sources(self):
        return self._sources

    def get_streams(self):
        result = []
        for stream in self._streams:
            if not self._is_routeable_output_stream(stream):
                continue
            result.append(stream)
        return result

    def _is_routeable_output_stream(self, stream):
        if stream.sample_rate < 1000:
            return False

        props = self._nodes.get(stream.id, {})
        media_class = props.get('media.class', stream.media_class or '')
        if media_class != 'Stream/Output/Audio':
            return False

        binary = props.get('application.process.binary', '').lower()
        if binary in ('pipewire', 'pipewire-pulse', 'wireplumber'):
            return False

        app_name = (props.get('application.name', '') or '').lower()
        media_name = (props.get('media.name', '') or '').lower()
        node_name = (props.get('node.name', '') or '').lower()

        internal_markers = {
            'portaudio source',
            'monitor_mono',
            'input_mono',
        }
        if media_name in internal_markers or node_name in internal_markers or app_name in internal_markers:
            return False

        return True

    def get_journal(self):
        return '\n'.join(self._journal[-80:])

    def clear_journal(self):
        self._journal.clear()

    def get_stats(self):
        streams = self.get_streams()
        coherents = sum(
            1 for stream in streams if stream.connections and all(connection.state == 'active' for connection in stream.connections)
        )
        return {
            'streams': len(streams),
            'devices': len(self._sinks),
            'links': self._links_count,
            'coherents': coherents,
        }

    def get_primary_sink(self, stream):
        if stream.driver_id:
            sink = next((item for item in self._sinks if item.id == stream.driver_id), None)
            if sink:
                return sink
        for name in stream.connected_sinks:
            sink = next(
                (
                    item
                    for item in self._sinks
                    if name and (name in item.display_name or item.display_name in name or (item.nick and name in item.nick))
                ),
                None,
            )
            if sink:
                return sink
        return next((item for item in self._sinks if not item.is_muted), self._sinks[0] if self._sinks else None)

    @staticmethod
    def _sink_settings_primary_key(sink):
        return getattr(sink, 'settings_key', str(sink.id))

    def _sink_settings_lookup_keys(self, sink):
        keys = []
        primary_key = self._sink_settings_primary_key(sink)
        if primary_key:
            keys.append(primary_key)
        legacy_key = str(sink.id)
        if legacy_key not in keys:
            keys.append(legacy_key)
        return keys

    def get_saved_sink_role(self, stream_id, sink):
        app_bin = self._nodes.get(stream_id, {}).get('application.process.binary', '').lower()
        primary_key = self._sink_settings_primary_key(sink)

        for settings_key in self._sink_settings_lookup_keys(sink):
            role = self.settings.get('routing', str(stream_id), settings_key, 'role')
            if role:
                if settings_key != primary_key:
                    self.settings.set('routing', str(stream_id), primary_key, 'role', role)
                return role

        if not app_bin:
            return None

        for settings_key in self._sink_settings_lookup_keys(sink):
            role = self.settings.get('routing_by_app', app_bin, settings_key, 'role')
            if role:
                if settings_key != primary_key:
                    self.settings.set('routing_by_app', app_bin, primary_key, 'role', role)
                return role

        return None

    def save_sink_role(self, stream_id, sink, role, app_bin=''):
        settings_key = self._sink_settings_primary_key(sink)
        self.settings.set('routing', str(stream_id), settings_key, 'role', role)
        if app_bin:
            self.settings.set('routing_by_app', app_bin, settings_key, 'role', role)

    def get_saved_sink_sample_rate(self, sink):
        primary_key = self._sink_settings_primary_key(sink)
        for settings_key in self._sink_settings_lookup_keys(sink):
            sample_rate = self.settings.get('sink_profiles', settings_key, 'sample_rate')
            if sample_rate is None:
                continue
            try:
                rate_value = int(sample_rate)
            except (TypeError, ValueError):
                continue
            if settings_key != primary_key:
                self.settings.set('sink_profiles', primary_key, 'sample_rate', rate_value)
            return rate_value
        return None

    def save_sink_sample_rate(self, sink, sample_rate):
        self.settings.set('sink_profiles', self._sink_settings_primary_key(sink), 'sample_rate', int(sample_rate))

    def set_sink_sample_rate(self, sink, sample_rate, log_action=True):
        rate_value = int(sample_rate)
        props = f'{{ "audio.rate": {rate_value} }}'
        self._run(['pw-cli', 'set-param', str(sink.id), 'Props', props], log=False)
        sink.sample_rate = rate_value
        self.save_sink_sample_rate(sink, rate_value)
        if log_action:
            self._journal.append(f"# pw-cli set-param {sink.id} Props audio.rate={rate_value}")

    def _restore_sink_sample_rates(self):
        for sink in self._sinks:
            saved_rate = self.get_saved_sink_sample_rate(sink)
            if not saved_rate:
                continue
            if sink.sample_rate == saved_rate:
                continue
            self.set_sink_sample_rate(sink, saved_rate, log_action=False)

    def is_linked(self, stream_id, sink_id):
        for link in self._links:
            info = link.get('info', {})
            output_node = info.get('output-node-id') or self._port_to_node.get(info.get('output-port-id'))
            input_node = info.get('input-node-id') or self._port_to_node.get(info.get('input-port-id'))
            if output_node == stream_id and input_node == sink_id:
                return True
        return False

    def set_volume(self, node_id, vol):
        self._journal.append(f"# wpctl set-volume {node_id} {vol:.2f}  [device]")
        self._run(['wpctl', 'set-volume', str(node_id), f'{vol:.2f}'], log=False)

    def set_stream_volume(self, stream_id, vol):
        self._journal.append(f"# wpctl set-volume {stream_id} {vol:.2f}  [stream]")
        self._run(['wpctl', 'set-volume', str(stream_id), f'{vol:.2f}'], log=False)

    def apply_stream_params(self, stream_id, balance, mode, base_vol=1.0):
        balance_value = float(balance)
        if mode == 'Gauche':
            left, right = base_vol, 0.0
        elif mode == 'Droite':
            left, right = 0.0, base_vol
        elif mode == 'Mono':
            left = right = base_vol * 0.707
        else:
            left = base_vol * min(1.0, (1.0 - balance_value) * 2)
            right = base_vol * min(1.0, balance_value * 2)
            if mode == 'Swap':
                left, right = right, left
        props = f'{{ "channelVolumes": [{left:.4f}, {right:.4f}] }}'
        self._run(['pw-cli', 'set-param', str(stream_id), 'Props', props], log=False)
        self._journal.append(
            f"# pw-cli set-param {stream_id} Props channelVol=[{left:.3f},{right:.3f}] "
            f"[bal={balance_value:.2f} mode={mode}]"
        )

    def route_stream_to_sink(self, stream_id, sink_id):
        out_ports = {
            port['channel']: port['id'] for port in self._ports.get(stream_id, []) if port['direction'] == 'output'
        }
        in_ports = {
            port['channel']: port['id'] for port in self._ports.get(sink_id, []) if port['direction'] == 'input'
        }
        existing_pairs = {
            (
                info.get('output-port-id'),
                info.get('input-port-id'),
            )
            for link in self._links
            for info in [link.get('info', {})]
            if (
                (info.get('output-node-id') or self._port_to_node.get(info.get('output-port-id'))) == stream_id
                and (info.get('input-node-id') or self._port_to_node.get(info.get('input-port-id'))) == sink_id
            )
        }
        linked = 0
        for channel in ('FL', 'FR', 'MONO', 'AUX0', 'AUX1', 'UNKNOWN'):
            if channel in out_ports and channel in in_ports:
                pair = (out_ports[channel], in_ports[channel])
                if pair in existing_pairs:
                    continue
                self._run(['pw-link', str(out_ports[channel]), str(in_ports[channel])], log=False)
                linked += 1
        self._journal.append(f"# pw-link stream:{stream_id} → sink:{sink_id} ({linked} ch)")

    def route_source_to_sink(self, source_id, sink_id, log_action=True):
        out_ports = {
            port['channel']: port['id'] for port in self._ports.get(source_id, []) if port['direction'] == 'output'
        }
        in_ports = {
            port['channel']: port['id'] for port in self._ports.get(sink_id, []) if port['direction'] == 'input'
        }
        existing_pairs = {
            (
                info.get('output-port-id'),
                info.get('input-port-id'),
            )
            for link in self._links
            for info in [link.get('info', {})]
            if (
                (info.get('output-node-id') or self._port_to_node.get(info.get('output-port-id'))) == source_id
                and (info.get('input-node-id') or self._port_to_node.get(info.get('input-port-id'))) == sink_id
            )
        }
        linked = 0
        for channel in ('FL', 'FR', 'MONO', 'AUX0', 'AUX1', 'UNKNOWN'):
            if channel in out_ports and channel in in_ports:
                pair = (out_ports[channel], in_ports[channel])
                if pair in existing_pairs:
                    continue
                self._run(['pw-link', str(out_ports[channel]), str(in_ports[channel])], log=False)
                linked += 1
        if log_action:
            self._journal.append(f"# pw-link source:{source_id} → sink:{sink_id} (loopback, {linked} ch)")

    def unroute_stream_from_sink(self, stream_id, sink_id):
        removed = 0
        for link in list(self._links):
            info = link.get('info', {})
            output_node = info.get('output-node-id') or self._port_to_node.get(info.get('output-port-id'))
            input_node = info.get('input-node-id') or self._port_to_node.get(info.get('input-port-id'))
            if output_node == stream_id and input_node == sink_id:
                self._run(['pw-link', '-d', str(link['id'])], log=False)
                removed += 1
        self._journal.append(f"# pw-link -d stream:{stream_id} → sink:{sink_id} ({removed} liens)")

    def unroute_source_from_all_sinks(self, source_id, log_action=True):
        removed = 0
        for link in list(self._links):
            info = link.get('info', {})
            output_node = info.get('output-node-id') or self._port_to_node.get(info.get('output-port-id'))
            if output_node == source_id and 'input-node-id' in info:
                self._run(['pw-link', '-d', str(link['id'])], log=False)
                removed += 1
        if log_action and removed > 0:
            self._journal.append(f"# pw-link -d source:{source_id} (cleanup, {removed} liens)")
        return removed

    def toggle_mute(self, node_id):
        self._run(['wpctl', 'set-mute', str(node_id), 'toggle'])

    def set_default_sink(self, node_id):
        self._run(['wpctl', 'set-default', str(node_id)])

    def set_default_source(self, node_id):
        self._run(['wpctl', 'set-default', str(node_id)])

    def update_source_peak_levels(self):
        pass

    def _audio_capture_source(self, source_id, description, node_name):
        if self._sounddevice is None:
            return

        try:
            import numpy as np

            sd = self._sounddevice
            device_index = None
            devices = sd.query_devices()

            if node_name:
                parts = node_name.split('.')
                for index, device in enumerate(devices):
                    if device['max_input_channels'] > 0:
                        device_name = device['name'].lower()
                        if '.monitor' in device_name:
                            continue
                        for part in parts:
                            part_lower = part.lower().replace('_', ' ')
                            if part_lower in device_name or part_lower.replace('-', '') in device_name.replace('-', ''):
                                device_index = index
                                break
                    if device_index is not None:
                        break

            if device_index is None and description:
                keywords = description.lower().split()
                for index, device in enumerate(devices):
                    if device['max_input_channels'] > 0:
                        device_name = device['name'].lower()
                        if '.monitor' in device_name:
                            continue
                        if any(keyword in device_name for keyword in keywords[-2:]):
                            device_index = index
                            break

            if device_index is None:
                device_index = sd.default.device[0]

            sample_rate = 48000
            blocksize = 512
            channels = 1
            smooth_attack = 0.08
            smooth_attack_ultra = 0.02
            smooth_release = 0.94
            decay_rate = 0.84
            decay_floor = 0.01
            sensitivity = 1.2

            smoothed_level = 0.0
            last_update = time.time()
            peak_detected = False

            def callback(indata, frames, time_info, status):
                nonlocal smoothed_level, last_update, peak_detected

                if status or indata.size == 0:
                    return

                try:
                    data = indata.flatten()
                    data = np.clip(data, -0.5, 0.5)
                    rms = np.sqrt(np.mean(data**2))
                    raw_level = min(1.0, max(0.0, rms / sensitivity))
                    is_rising = raw_level > smoothed_level

                    if is_rising:
                        if raw_level > smoothed_level + 0.15 and not peak_detected:
                            smoothed_level = smooth_attack_ultra * smoothed_level + (1.0 - smooth_attack_ultra) * raw_level
                            peak_detected = True
                        else:
                            smoothed_level = smooth_attack * smoothed_level + (1.0 - smooth_attack) * raw_level
                    else:
                        smoothed_level = smooth_release * smoothed_level + (1.0 - smooth_release) * raw_level
                        peak_detected = False

                    smoothed_level = min(1.0, max(decay_floor, smoothed_level))
                    self._source_peak_levels[source_id] = smoothed_level
                    last_update = time.time()
                except Exception:
                    pass

            with sd.InputStream(
                device=device_index,
                channels=channels,
                samplerate=sample_rate,
                blocksize=blocksize,
                callback=callback,
                latency='low',
            ):
                while self._audio_running:
                    now = time.time()
                    silence_duration = now - last_update
                    if silence_duration > 0.2:
                        current_level = self._source_peak_levels.get(source_id, 0.0)
                        self._source_peak_levels[source_id] = max(decay_floor, current_level * decay_rate)
                    time.sleep(0.01)

        except Exception:
            decay = 0.95
            while self._audio_running:
                try:
                    for source in self._sources:
                        if source.id == source_id:
                            source.peak_level = max(0.0, source.peak_level * decay)
                    time.sleep(0.05)
                except Exception:
                    break

    def restore_saved_routing(self, stream_id, sinks):
        app_bin = self._nodes.get(stream_id, {}).get('application.process.binary', '').lower()

        for sink in sinks:
            role = self.get_saved_sink_role(stream_id, sink)
            if role in ('PRIMARY', 'MIRROR') and not self.is_linked(stream_id, sink.id):
                self.route_stream_to_sink(stream_id, sink.id)
                self._journal.append(f"# restore {stream_id} → {sink.id} ({role}) [app:{app_bin}]")
