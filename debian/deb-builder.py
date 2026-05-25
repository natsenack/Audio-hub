#!/usr/bin/env python3
"""
Setup script for debian/ubuntu packaging
Run: sudo python3 debian/deb-builder.py
"""

import subprocess
import sys
import os
from pathlib import Path

def run(cmd, check=True):
    """Run a command and return exit code."""
    print(f"→ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check).returncode

def build_deb():
    """Build a .deb package."""
    root = Path(__file__).parent.parent
    os.chdir(root)

    print("📦 Building Debian package...")

    # Install build dependencies
    print("\n1️⃣  Installing build dependencies...")
    run(["sudo", "apt-get", "update"])
    run(["sudo", "apt-get", "install", "-y",
         "python3-setuptools", "python3-wheel", "dh-python", "python3-all",
         "build-essential", "fakeroot"])

    # Build with dpkg-buildpackage
    print("\n2️⃣  Building package with dpkg-buildpackage...")
    run(["dpkg-buildpackage", "-us", "-uc"])

    # Show result
    deb_file = list(root.parent.glob("linux-audio-manager_*.deb"))
    if deb_file:
        print(f"\n✓ Package built: {deb_file[0]}")
        print(f"\nTo install:")
        print(f"  sudo dpkg -i {deb_file[0]}")
        print(f"  sudo apt-get install -f  # Install dependencies if needed")
        return 0
    else:
        print("❌ No .deb file found!")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(build_deb())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(130)
