#!/usr/bin/env python3
"""Unit tests for audio device classification heuristics."""

import unittest

from audio_device_classifier import classify_audio_device


class AudioDeviceClassifierTests(unittest.TestCase):
    def test_detects_line_in_from_alsa_path(self):
        info = classify_audio_device(
            {
                'node.name': 'alsa_input.pci-0000_00_1f.3.analog-stereo',
                'node.description': 'Built-in Audio Analog Stereo',
                'api.alsa.path': 'analog-input-linein',
                'device.bus': 'pci',
            },
            is_sink=False,
        )
        self.assertEqual(info['transport'], 'jack')
        self.assertEqual(info['role'], 'line_in')
        self.assertEqual(info['display_name'], 'Entree ligne')

    def test_detects_usb_microphone(self):
        info = classify_audio_device(
            {
                'node.name': 'alsa_input.usb-HP_HyperX_Cloud-00.mono-fallback',
                'node.description': 'HyperX Cloud',
                'device.bus': 'usb',
            },
            is_sink=False,
        )
        self.assertEqual(info['transport'], 'usb')
        self.assertEqual(info['role'], 'microphone')

    def test_detects_bluetooth_headphones(self):
        info = classify_audio_device(
            {
                'node.name': 'bluez_output.11_22_33_44_55_66.1',
                'node.description': 'WH-1000XM4',
                'device.api': 'bluez5',
            },
            is_sink=True,
        )
        self.assertEqual(info['transport'], 'bluetooth')
        self.assertEqual(info['role'], 'headphones')

    def test_detects_hdmi_output(self):
        info = classify_audio_device(
            {
                'node.name': 'alsa_output.pci-0000_03_00.1.hdmi-stereo',
                'node.description': 'NVIDIA HDMI',
                'device.bus': 'pci',
            },
            is_sink=True,
        )
        self.assertEqual(info['transport'], 'hdmi')
        self.assertEqual(info['role'], 'display')


if __name__ == '__main__':
    unittest.main()
