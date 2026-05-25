"""Gestion de la persistance de la configuration audio."""
from __future__ import annotations

import json
from pathlib import Path


CONFIG_DIR = Path.home() / ".config" / "linux-audio-manager"
CONFIG_FILE = CONFIG_DIR / "settings.json"

# Cache mémoire : évite de relire le fichier à chaque appel
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                _cache = json.load(f)
                return _cache
        except Exception:
            pass
    _cache = {}
    return _cache


def _save(cfg: dict) -> None:
    global _cache
    _cache = cfg
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Sink par défaut
# ---------------------------------------------------------------------------

def get_last_default_sink() -> int | None:
    return _load().get("default_sink_id")


def save_default_sink(node_id: int) -> None:
    cfg = _load()
    cfg["default_sink_id"] = node_id
    _save(cfg)


# ---------------------------------------------------------------------------
# Sinks préférés pour la multi-sortie
# ---------------------------------------------------------------------------

def get_preferred_sinks() -> list[int]:
    return _load().get("preferred_sinks", [])


def save_preferred_sinks(sink_ids: list[int]) -> None:
    cfg = _load()
    cfg["preferred_sinks"] = sink_ids
    _save(cfg)


# ---------------------------------------------------------------------------
# Routage par application (clé = app_name, valeur = noms de sinks)
# Les noms de sinks sont stables entre sessions, contrairement aux node_id.
# ---------------------------------------------------------------------------

def get_stream_routing() -> dict[str, list[str]]:
    """Retourne {app_name: [sink_name, ...]} pour toutes les applications configurées."""
    return _load().get("stream_routing", {})


def save_stream_routing(app_name: str, sink_names: list[str]) -> None:
    """Sauvegarde les sinks choisis pour une application."""
    cfg = _load()
    routing = cfg.get("stream_routing", {})
    routing[app_name] = sink_names
    cfg["stream_routing"] = routing
    _save(cfg)
