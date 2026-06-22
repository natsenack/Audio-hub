#!/usr/bin/env python3
"""Classification helpers for PipeWire audio devices."""

from typing import Any, Dict, Mapping


TRANSPORT_LABELS = {
    'bluetooth': 'Bluetooth',
    'hdmi': 'HDMI / DisplayPort',
    'jack': 'Jack 3.5 mm',
    'spdif': 'Optique / SPDIF',
    'usb': 'USB',
    'internal': 'Interne',
    'unknown': 'Audio',
}

SINK_ROLE_LABELS = {
    'digital': 'Sortie numerique',
    'display': 'Ecran audio',
    'headphones': 'Casque',
    'line_out': 'Sortie ligne',
    'output': 'Sortie audio',
    'speaker': 'Haut-parleurs',
}

SOURCE_ROLE_LABELS = {
    'digital_in': 'Entree numerique',
    'input': 'Entree audio',
    'line_in': 'Entree ligne',
    'microphone': 'Microphone',
    'monitor': 'Monitor',
}


def classify_audio_device(
    props: Mapping[str, Any] = None,
    *,
    is_sink: bool,
    node_name: str = '',
    description: str = '',
    nick: str = '',
    fallback_name: str = '',
) -> Dict[str, str]:
    """Infer transport, role and friendly labels from PipeWire node props."""
    props = dict(props or {})
    node_name = node_name or str(props.get('node.name', '') or '')
    description = description or str(props.get('node.description', '') or '')
    nick = nick or str(props.get('node.nick', '') or '')
    fallback_name = fallback_name or description or nick or node_name

    text_blob = _build_text_blob(props, node_name, description, nick, fallback_name)
    transport = _detect_transport(props, text_blob)
    role = _detect_sink_role(text_blob, transport) if is_sink else _detect_source_role(text_blob, transport)
    role_label = (SINK_ROLE_LABELS if is_sink else SOURCE_ROLE_LABELS).get(
        role,
        'Sortie audio' if is_sink else 'Entree audio',
    )

    return {
        'transport': transport,
        'transport_label': TRANSPORT_LABELS.get(transport, 'Audio'),
        'role': role,
        'role_label': role_label,
        'display_name': _suggest_display_name(
            is_sink=is_sink,
            role=role,
            transport=transport,
            nick=nick,
            description=description,
            node_name=node_name,
            fallback_name=fallback_name,
        ),
    }


def _build_text_blob(props: Mapping[str, Any], *extra_texts: str) -> str:
    parts = []
    for key, value in props.items():
        parts.append(str(key).lower())
        parts.append(str(value).lower())
    for text in extra_texts:
        if text:
            parts.append(str(text).lower())
    return ' '.join(parts)


def _detect_transport(props: Mapping[str, Any], blob: str) -> str:
    bus = str(props.get('device.bus', '') or '').lower()
    device_api = str(props.get('device.api', '') or '').lower()
    form_factor = str(props.get('device.form-factor', '') or '').lower()

    if any(token in blob for token in ('bluez', 'bluetooth', 'a2dp', 'handsfree', 'headset-head-unit')):
        return 'bluetooth'
    if bus == 'bluetooth' or 'bluez' in device_api:
        return 'bluetooth'

    if any(token in blob for token in ('hdmi', 'displayport', 'display port', 'dp-')):
        return 'hdmi'

    if any(token in blob for token in ('spdif', 'iec958', 'optical', 'toslink')):
        return 'spdif'

    if bus == 'usb' or 'usb' in blob:
        return 'usb'

    if any(
        token in blob for token in (
            'analog-input-',
            'analog-output-',
            'linein',
            'line-in',
            'line input',
            'lineout',
            'line-out',
            'headphone',
            'headset',
            'microphone',
            'mono-fallback',
            'front-',
            'rear-',
        )
    ):
        return 'jack'

    if form_factor in ('internal', 'speaker'):
        return 'internal'

    return 'unknown'


def _detect_sink_role(blob: str, transport: str) -> str:
    if transport == 'hdmi':
        return 'display'
    if transport == 'spdif':
        return 'digital'
    if transport == 'bluetooth':
        return 'headphones'
    if any(token in blob for token in ('analog-output-headphones', 'headphone', 'headset', 'earbud')):
        return 'headphones'
    if any(token in blob for token in ('analog-output-lineout', 'lineout', 'line-out')):
        return 'line_out'
    if any(token in blob for token in ('analog-output-speaker', 'speaker', 'built-in audio')):
        return 'speaker'
    return 'output'


def _detect_source_role(blob: str, transport: str) -> str:
    if 'monitor' in blob:
        return 'monitor'
    if any(token in blob for token in ('analog-input-linein', 'linein', 'line-in', 'line input')):
        return 'line_in'
    if transport == 'spdif':
        return 'digital_in'
    if any(
        token in blob for token in (
            'analog-input-mic',
            'microphone',
            'mic',
            'headset',
            'mono-fallback',
            'input.mic',
        )
    ):
        return 'microphone'
    return 'input'


def _suggest_display_name(
    *,
    is_sink: bool,
    role: str,
    transport: str,
    nick: str,
    description: str,
    node_name: str,
    fallback_name: str,
) -> str:
    preferred = _preferred_name(nick, description, fallback_name, node_name)
    preferred_lower = preferred.lower()

    if not is_sink:
        if role == 'line_in':
            return 'Entree ligne'
        if role == 'monitor':
            return 'Monitor audio'
        if role == 'digital_in':
            return 'Entree optique'
        if role == 'microphone' and _is_generic_name(preferred_lower):
            if transport == 'usb':
                return 'Microphone USB'
            if transport == 'bluetooth':
                return 'Microphone Bluetooth'
            return 'Microphone'
        return preferred

    if role == 'display' and _is_generic_name(preferred_lower):
        return 'Sortie HDMI'
    if role == 'digital' and _is_generic_name(preferred_lower):
        return 'Sortie optique'
    if role == 'headphones' and _is_generic_name(preferred_lower):
        if transport == 'bluetooth':
            return 'Casque Bluetooth'
        if transport == 'usb':
            return 'Casque USB'
        return 'Casque'
    if role == 'speaker' and _is_generic_name(preferred_lower):
        return 'Haut-parleurs'
    return preferred


def _preferred_name(*candidates: str) -> str:
    for candidate in candidates:
        cleaned = str(candidate or '').strip()
        if cleaned and 'alsa_' not in cleaned.lower():
            return cleaned
    return 'Audio'


def _is_generic_name(text: str) -> bool:
    generic_tokens = (
        'analog stereo',
        'stereo analogique',
        'stereo analog',
        'built-in audio',
        'audio interne',
        'monitor of ',
        'monitor de ',
        'audio',
    )
    return any(token in text for token in generic_tokens)
