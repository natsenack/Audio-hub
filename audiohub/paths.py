"""Common filesystem paths for AudioHub."""

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_ROOT = PROJECT_ROOT / 'data'
ICON_ROOT = DATA_ROOT / 'icons'
