#!/usr/bin/env python3
"""Test capture audio simple"""
import sounddevice as sd
import numpy as np
import time

print("=== TEST CAPTURE AUDIO ===")

# Trouvez le device HyperX
device_index = None
devices = sd.query_devices()
for i, dev in enumerate(devices):
    if 'HyperX' in dev['name'] and dev['max_input_channels'] > 0:
        device_index = i
        print(f"✓ Trouvé HyperX: {dev['name']}")
        break

if device_index is None:
    print("✗ HyperX non trouvé, utilisant device par défaut")
    device_index = sd.default.device[0]

print(f"\nCapture sur device #{device_index}...")
print("Parlez dans le micro (10 secondes)...\n")

# Variable pour stocker le niveau
peak_level = 0.0

def callback(indata, frames, time_info, status):
    global peak_level
    if status:
        print(f"Erreur audio: {status}")
    
    data = indata.flatten()
    rms = np.sqrt(np.mean(data ** 2))
    peak_level = min(1.0, rms / 0.22)
    
    level_pct = int(peak_level * 100)
    bar = "█" * (level_pct // 5) + "░" * (20 - level_pct // 5)
    print(f"\r[{bar}] {level_pct}%", end='', flush=True)

try:
    with sd.InputStream(
        device=device_index,
        channels=1,
        samplerate=44100,
        blocksize=1024,
        callback=callback,
        latency='low'
    ):
        time.sleep(10)
    print("\n✓ Test réussi!")
except Exception as e:
    print(f"\n✗ Erreur: {e}")
