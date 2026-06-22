#!/usr/bin/env python3
"""Unit tests for stream identity heuristics."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from audiohub.pipewire import AudioManager
from audiohub.models import PipeWireSink, PipeWireStream, Settings


class StreamIdentityTests(unittest.TestCase):
    def _manager_with_props(self, props):
        manager = AudioManager.__new__(AudioManager)
        manager._nodes = {42: props}
        manager._mpris_cache = {'players': {}, 'expires_at': 0.0}
        manager._lookup_mpris_metadata = lambda browser, binary: {}
        return manager

    def test_classifies_browser_site_for_chrome_tab(self):
        manager = self._manager_with_props(
            {
                'application.process.binary': 'google-chrome',
                'application.name': 'Google Chrome',
                'media.title': 'YouTube',
            }
        )
        identity = manager.get_stream_identity(42, 'Chrome input')
        self.assertEqual(identity['kind'], 'browser_site')
        self.assertEqual(identity['kind_label'], 'Site')
        self.assertEqual(identity['family'], 'Chrome')
        self.assertEqual(identity['primary'], 'YouTube')

    def test_classifies_web_app_for_edge_app_mode(self):
        manager = self._manager_with_props(
            {
                'application.process.binary': 'microsoft-edge-stable',
                'application.name': 'Spotify',
                'media.title': 'Spotify',
                'application.process.commandline': '--profile-directory=Default --app-id=abc123',
            }
        )
        identity = manager.get_stream_identity(42, 'Edge app')
        self.assertEqual(identity['kind'], 'browser_app')
        self.assertEqual(identity['kind_label'], 'App web')
        self.assertEqual(identity['family'], 'Edge')
        self.assertEqual(identity['primary'], 'Spotify')

    def test_classifies_browser_shell_when_title_missing(self):
        manager = self._manager_with_props(
            {
                'application.process.binary': 'microsoft-edge',
                'application.name': 'Microsoft Edge',
            }
        )
        identity = manager.get_stream_identity(42)
        self.assertEqual(identity['kind'], 'browser_shell')
        self.assertEqual(identity['kind_label'], 'Navigateur')
        self.assertEqual(identity['family'], 'Edge')

    def test_uses_mpris_title_when_pipewire_only_reports_playback(self):
        manager = self._manager_with_props(
            {
                'application.process.binary': 'chrome',
                'application.name': 'Google Chrome',
                'media.name': 'Playback',
            }
        )
        manager._lookup_mpris_metadata = lambda browser, binary: {
            'title': 'Molotov TV - Molotov - Regardez la tele sur tous vos appareils',
            'artist': '',
            'source': 'org.mpris.MediaPlayer2.chromium.instance5574',
        }
        identity = manager.get_stream_identity(42, 'Chrome input')
        self.assertEqual(identity['kind'], 'browser_site')
        self.assertNotEqual(identity['primary'], 'Playback')
        self.assertTrue(identity['primary'])

    def test_classifies_chrome_pwa_as_browser_app(self):
        manager = self._manager_with_props(
            {
                'application.process.binary': 'google-chrome',
                'application.name': 'YouTube',
                'media.title': 'Ma vidéo préférée',
                'application.icon-name': 'youtube',
            }
        )
        identity = manager.get_stream_identity(42, 'YouTube')
        self.assertEqual(identity['kind'], 'browser_app')
        self.assertEqual(identity['kind_label'], 'App web')
        self.assertEqual(identity['family'], 'Chrome')
        self.assertEqual(identity['primary'], 'YouTube')

    def test_classifies_chrome_pwa_from_stream_name(self):
        manager = self._manager_with_props(
            {
                'application.process.binary': 'google-chrome',
                'application.name': 'Google Chrome',
                'media.name': 'Chrome — YouTube',
            }
        )
        identity = manager.get_stream_identity(42, 'Chrome — YouTube')
        self.assertEqual(identity['kind'], 'browser_app')
        self.assertEqual(identity['kind_label'], 'App web')
        self.assertEqual(identity['family'], 'Chrome')
        self.assertEqual(identity['primary'], 'YouTube')

    def test_disney_plus_pwa_with_playback_title(self):
        """Test Disney+ PWA where media.title is 'Playback' but media.name has the real app name."""
        manager = self._manager_with_props(
            {
                'application.process.binary': 'google-chrome',
                'application.name': 'Google Chrome',
                'media.title': 'Playback',
                'media.name': 'Chrome — Disney+',
            }
        )
        identity = manager.get_stream_identity(42, 'Chrome — Disney+')
        self.assertEqual(identity['kind'], 'browser_app')
        self.assertEqual(identity['kind_label'], 'App web')
        self.assertEqual(identity['family'], 'Chrome')
        self.assertEqual(identity['primary'], 'Disney+')

    def test_extracts_site_and_content_title_from_browser_page_title(self):
        manager = self._manager_with_props(
            {
                'application.process.binary': 'google-chrome',
                'application.name': 'Google Chrome',
                'media.title': 'Disney+ - Les Agents du S.H.I.E.L.D. | Disney+',
            }
        )
        identity = manager.get_stream_identity(42, 'Chrome')
        self.assertEqual(identity['kind'], 'browser_site')
        self.assertEqual(identity['primary'], 'Disney+')
        self.assertEqual(identity['secondary'], 'Les Agents du S.H.I.E.L.D.')

    def test_does_not_reuse_one_mpris_title_for_two_generic_chrome_streams(self):
        manager = AudioManager.__new__(AudioManager)
        manager._nodes = {
            78: {
                'media.class': 'Stream/Output/Audio',
                'application.process.binary': 'chrome',
                'application.name': 'Google Chrome',
                'media.name': 'Playback',
            },
            131: {
                'media.class': 'Stream/Output/Audio',
                'application.process.binary': 'chrome',
                'application.name': 'Google Chrome',
                'media.name': 'Playback',
            },
        }
        manager._streams = [
            PipeWireStream(78, 'Google Chrome', 19730, 48000, 'Stream/Output/Audio'),
            PipeWireStream(131, 'Google Chrome', 19730, 48000, 'Stream/Output/Audio'),
        ]
        manager._mpris_cache = {'players': {}, 'expires_at': 0.0}
        manager._lookup_mpris_metadata = lambda browser, binary: {
            'title': 'Molotov - Regardez la tele sur tous vos appareils',
            'artist': '',
            'source': 'org.mpris.MediaPlayer2.chromium.instance5574',
        }
        manager._lookup_browser_session_candidates = lambda browser, binary: []

        first = manager.get_stream_identity(78, 'Google Chrome')
        second = manager.get_stream_identity(131, 'Google Chrome')

        self.assertEqual(first['primary'], 'Chrome #1')
        self.assertEqual(second['primary'], 'Chrome #2')
        self.assertNotIn('Molotov', first.get('secondary') or '')
        self.assertNotIn('Molotov', second.get('secondary') or '')

    def test_uses_chrome_session_candidates_for_multiple_generic_streams(self):
        manager = AudioManager.__new__(AudioManager)
        manager._nodes = {
            78: {
                'media.class': 'Stream/Output/Audio',
                'application.process.binary': 'chrome',
                'application.name': 'Google Chrome',
                'media.name': 'Playback',
            },
            131: {
                'media.class': 'Stream/Output/Audio',
                'application.process.binary': 'chrome',
                'application.name': 'Google Chrome',
                'media.name': 'Playback',
            },
        }
        manager._streams = [
            PipeWireStream(78, 'Google Chrome', 19730, 48000, 'Stream/Output/Audio'),
            PipeWireStream(131, 'Google Chrome', 19730, 48000, 'Stream/Output/Audio'),
        ]
        manager._mpris_cache = {'players': {}, 'expires_at': 0.0}
        manager._lookup_mpris_metadata = lambda browser, binary: {}
        manager._lookup_browser_session_candidates = lambda browser, binary: ['Disney+', 'Molotov']

        first = manager.get_stream_identity(78, 'Google Chrome')
        second = manager.get_stream_identity(131, 'Google Chrome')

        self.assertEqual(first['primary'], 'Disney+')
        self.assertEqual(second['primary'], 'Molotov')

class StreamFilteringTests(unittest.TestCase):
    def _manager(self, streams, nodes):
        manager = AudioManager.__new__(AudioManager)
        manager._streams = streams
        manager._nodes = nodes
        return manager

    def test_keeps_routeable_output_streams_only(self):
        playback = PipeWireStream(10, 'Disney+', 1234, 48000, 'Stream/Output/Audio')
        capture = PipeWireStream(11, 'Portaudio source', 9999, 48000, 'Stream/Input/Audio')
        manager = self._manager(
            [playback, capture],
            {
                10: {
                    'media.class': 'Stream/Output/Audio',
                    'application.process.binary': 'google-chrome',
                    'application.name': 'Google Chrome',
                    'media.name': 'Playback',
                },
                11: {
                    'media.class': 'Stream/Input/Audio',
                    'application.process.binary': 'python3.14',
                    'application.name': 'python3',
                    'media.name': 'Portaudio source',
                },
            },
        )

        streams = manager.get_streams()
        self.assertEqual([stream.id for stream in streams], [10])

    def test_excludes_internal_output_markers(self):
        internal = PipeWireStream(12, 'monitor_MONO', 9999, 48000, 'Stream/Output/Audio')
        manager = self._manager(
            [internal],
            {
                12: {
                    'media.class': 'Stream/Output/Audio',
                    'application.process.binary': 'python3.14',
                    'application.name': 'python3',
                    'media.name': 'monitor_MONO',
                    'node.name': 'monitor_MONO',
                },
            },
        )

        self.assertEqual(manager.get_streams(), [])


class StreamParsingTests(unittest.TestCase):
    def test_parse_streams_does_not_promote_child_ports_to_root_streams(self):
        manager = AudioManager.__new__(AudioManager)
        manager._nodes = {
            78: {'media.class': 'Stream/Output/Audio', 'application.process.id': 19730},
            84: {'media.class': 'Stream/Input/Audio', 'application.process.id': 197388},
            88: {'media.class': 'Stream/Output/Audio', 'application.process.id': 2},
            112: {'media.class': 'Stream/Input/Audio', 'application.process.id': 197388},
        }
        manager._stream_volumes = {}
        manager._parse_rate = lambda props: 48000
        manager._node_props = lambda node_id: manager._nodes.get(node_id, {})

        status = """
Audio
 └─ Streams:
        78. Google Chrome
             80. output_FL       > ALC1220 Analog:playback_FL\t[active]
            113. output_FR       > HyperX Cloud Jet:playback_FR\t[active]
        84. python3
             85. input_MONO      < ALC1220 Analog:capture_FL\t[active]
             89. monitor_MONO
        88. jellyfin-desktop
             97. output_FL       > HyperX Cloud Jet:playback_FL\t[active]
            105. output_FR       > HyperX Cloud Jet:playback_FR\t[active]
       112. python3
            101. input_MONO      < HyperX Cloud Jet:capture_MONO\t[active]
            109. monitor_MONO
"""

        streams = manager._parse_streams(status)
        self.assertEqual([stream.id for stream in streams], [78, 84, 88, 112])
        self.assertEqual(streams[0].name, 'Google Chrome')
        self.assertEqual(streams[1].name, 'python3')
        self.assertEqual(len(streams[0].connections), 2)
        self.assertEqual(len(streams[1].connections), 0)


class RoutingPersistenceTests(unittest.TestCase):
    def test_restore_saved_routing_uses_stable_sink_key_after_bluetooth_reconnect(self):
        with TemporaryDirectory() as tmpdir:
            manager = AudioManager.__new__(AudioManager)
            manager.settings = Settings(Path(tmpdir) / 'settings.json')
            manager._nodes = {42: {'application.process.binary': 'google-chrome'}}
            manager._links = []
            manager._port_to_node = {}
            manager._journal = []
            restored_links = []
            manager.route_stream_to_sink = lambda stream_id, sink_id: restored_links.append((stream_id, sink_id))
            manager.is_linked = lambda stream_id, sink_id: False

            original_sink = PipeWireSink(
                77,
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'HyperX Cloud Jet',
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'bluetooth',
                1.0,
                False,
                False,
                'bluetooth',
                {
                    'device.bus': 'bluetooth',
                    'api.bluez5.address': 'AA:BB:CC:DD:EE:FF',
                    'node.name': 'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                    'node.description': 'HyperX Cloud Jet',
                },
            )
            manager.save_sink_role(42, original_sink, 'PRIMARY', 'google-chrome')

            reconnected_sink = PipeWireSink(
                105,
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'HyperX Cloud Jet',
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'bluetooth',
                1.0,
                False,
                False,
                'bluetooth',
                {
                    'device.bus': 'bluetooth',
                    'api.bluez5.address': 'AA:BB:CC:DD:EE:FF',
                    'node.name': 'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                    'node.description': 'HyperX Cloud Jet',
                },
            )

            manager.restore_saved_routing(42, [reconnected_sink])
            self.assertEqual(restored_links, [(42, 105)])

    def test_get_saved_sink_role_migrates_legacy_node_id_key(self):
        with TemporaryDirectory() as tmpdir:
            manager = AudioManager.__new__(AudioManager)
            manager.settings = Settings(Path(tmpdir) / 'settings.json')
            manager._nodes = {42: {'application.process.binary': 'google-chrome'}}

            sink = PipeWireSink(
                77,
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'HyperX Cloud Jet',
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'bluetooth',
                1.0,
                False,
                False,
                'bluetooth',
                {
                    'device.bus': 'bluetooth',
                    'api.bluez5.address': 'AA:BB:CC:DD:EE:FF',
                    'node.name': 'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                    'node.description': 'HyperX Cloud Jet',
                },
            )
            manager.settings.set('routing_by_app', 'google-chrome', str(sink.id), 'role', 'MIRROR')

            role = manager.get_saved_sink_role(42, sink)

            self.assertEqual(role, 'MIRROR')
            self.assertEqual(
                manager.settings.get('routing_by_app', 'google-chrome', sink.settings_key, 'role'),
                'MIRROR',
            )

    def test_restore_sink_sample_rate_uses_stable_sink_key_after_reconnect(self):
        with TemporaryDirectory() as tmpdir:
            manager = AudioManager.__new__(AudioManager)
            manager.settings = Settings(Path(tmpdir) / 'settings.json')
            manager._restored_sink_rates = {}
            applied_rates = []
            manager._run = lambda cmd, timeout=5, log=True: applied_rates.append(cmd) or ''

            original_sink = PipeWireSink(
                77,
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'HyperX Cloud Jet',
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'bluetooth',
                1.0,
                False,
                False,
                'bluetooth',
                {
                    'device.bus': 'bluetooth',
                    'api.bluez5.address': 'AA:BB:CC:DD:EE:FF',
                    'audio.rate': 48000,
                    'node.name': 'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                    'node.description': 'HyperX Cloud Jet',
                },
            )
            manager.save_sink_sample_rate(original_sink, 44100)

            reconnected_sink = PipeWireSink(
                105,
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'HyperX Cloud Jet',
                'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                'bluetooth',
                1.0,
                False,
                False,
                'bluetooth',
                {
                    'device.bus': 'bluetooth',
                    'api.bluez5.address': 'AA:BB:CC:DD:EE:FF',
                    'audio.rate': 48000,
                    'node.name': 'bluez_output.aa_bb_cc_dd_ee_ff.a2dp-sink',
                    'node.description': 'HyperX Cloud Jet',
                },
            )

            manager._sinks = [reconnected_sink]
            manager._journal = []
            manager._restore_sink_sample_rates()

            self.assertTrue(any(cmd[:4] == ['pw-cli', 'set-param', '105', 'Props'] for cmd in applied_rates))
            self.assertEqual(reconnected_sink.sample_rate, 44100)

    def test_route_stream_to_sink_skips_existing_links(self):
        manager = AudioManager.__new__(AudioManager)
        manager._ports = {
            10: [
                {'id': 100, 'direction': 'output', 'channel': 'FL'},
                {'id': 101, 'direction': 'output', 'channel': 'FR'},
            ],
            20: [
                {'id': 200, 'direction': 'input', 'channel': 'FL'},
                {'id': 201, 'direction': 'input', 'channel': 'FR'},
            ],
        }
        manager._links = [
            {
                'id': 1,
                'info': {
                    'output-port-id': 100,
                    'input-port-id': 200,
                    'output-node-id': 10,
                    'input-node-id': 20,
                },
            }
        ]
        manager._port_to_node = {100: 10, 101: 10, 200: 20, 201: 20}
        manager._journal = []
        executed = []
        manager._run = lambda cmd, timeout=5, log=True: executed.append(cmd) or ''

        manager.route_stream_to_sink(10, 20)

        self.assertEqual(executed, [['pw-link', '101', '201']])


if __name__ == '__main__':
    unittest.main()
