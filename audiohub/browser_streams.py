"""Browser-specific stream labeling and title recovery helpers."""

from __future__ import annotations

import ast
import re
import subprocess
import time
from pathlib import Path


_BROWSERS = {
    'firefox': 'Firefox',
    'firefox-esr': 'Firefox ESR',
    'chromium': 'Chromium',
    'google-chrome': 'Chrome',
    'chrome': 'Chrome',
    'microsoft-edge': 'Edge',
    'microsoft-edge-stable': 'Edge',
    'msedge': 'Edge',
    'edge': 'Edge',
    'brave': 'Brave',
    'brave-browser': 'Brave',
    'opera': 'Opera',
    'vivaldi': 'Vivaldi',
    'librewolf': 'LibreWolf',
    'waterfox': 'Waterfox',
    'floorp': 'Floorp',
    'zen': 'Zen Browser',
    'epiphany': 'GNOME Web',
    'falkon': 'Falkon',
}


class BrowserStreamIdentityMixin:
    def get_browser_info(self, stream_id):
        props = self._nodes.get(stream_id, {})
        binary = props.get('application.process.binary', '').lower()
        app_name = props.get('application.name', '')
        media_title = props.get('media.title', '') or ''
        media_name = props.get('media.name', '') or ''
        artist = props.get('media.artist', '')
        app_lower = app_name.lower()
        browser = next((name for key, name in _BROWSERS.items() if key in binary or key in app_lower), None)

        if browser and media_title.lower() in {'playback', 'audio', 'music', 'video', 'media'}:
            pwa_name = self._extract_pwa_name(media_name, browser)
            if pwa_name:
                app_name = pwa_name
                title = pwa_name
            elif media_name and not self._looks_like_browser_shell(media_name, self._browser_tokens(browser, '')):
                title = media_name
            else:
                title = media_title
        elif browser and media_title:
            title = media_title
        else:
            title = media_title or media_name

        return browser, title, artist, app_name

    def get_stream_identity(self, stream_id, fallback_name=''):
        props = self._nodes.get(stream_id, {})
        binary = props.get('application.process.binary', '')
        binary_lower = binary.lower()
        app_name = props.get('application.name', '') or ''
        stream_name = props.get('media.name', '') or fallback_name or ''
        raw_media_title = props.get('media.title', '') or ''
        media_title = raw_media_title or stream_name
        media_artist = props.get('media.artist', '') or ''
        desktop_file = props.get('application.desktop_file', '') or props.get('application.id', '') or ''
        icon_name = props.get('application.icon-name', '') or props.get('application.icon_name', '') or ''
        commandline = props.get('application.process.commandline', '') or props.get('process.commandline', '') or ''

        browser = next(
            (name for key, name in _BROWSERS.items() if key in binary_lower or key in app_name.lower()),
            None,
        )
        if browser:
            browser_instance = self._browser_instance_label(stream_id, browser, binary)
            ambiguous_browser_streams = self._ambiguous_browser_streams(browser, binary)
            can_use_shared_mpris = len(ambiguous_browser_streams) <= 1

            if can_use_shared_mpris and self._is_generic_stream_title(raw_media_title or stream_name):
                mpris = self._lookup_mpris_metadata(browser, binary)
                if mpris.get('title'):
                    raw_media_title = mpris['title']
                    media_title = mpris['title']
                if not media_artist and mpris.get('artist'):
                    media_artist = mpris['artist']
            return self._classify_browser_stream(
                browser=browser,
                binary=binary,
                app_name=app_name,
                stream_name=stream_name,
                media_title=media_title,
                raw_media_title=raw_media_title,
                media_artist=media_artist,
                desktop_file=desktop_file,
                icon_name=icon_name,
                commandline=commandline,
                browser_instance=browser_instance,
            )

        primary = app_name or fallback_name or stream_name or media_title or 'Flux audio'
        return {
            'kind': 'native_app',
            'kind_label': 'Application',
            'icon': '🎵',
            'family': None,
            'primary': primary,
            'secondary': binary or stream_name or None,
            'raw_app_name': app_name,
            'raw_title': media_title,
            'raw_artist': media_artist,
        }

    @staticmethod
    def _is_generic_stream_title(value):
        if not value:
            return True
        return value.strip().lower() in {
            'playback',
            'record',
            'capture',
            'output',
            'input',
            'audio stream',
        }

    def _classify_browser_stream(
        self,
        *,
        browser,
        binary,
        app_name,
        stream_name,
        media_title,
        raw_media_title,
        media_artist,
        desktop_file,
        icon_name,
        commandline,
        browser_instance,
    ):
        browser_tokens = self._browser_tokens(browser, binary)
        generic_app_name = self._looks_like_browser_shell(app_name, browser_tokens)
        generic_stream_name = self._looks_like_browser_shell(stream_name, browser_tokens)
        site_name, content_title = self._extract_browser_site_and_title(
            media_title,
            app_name,
            browser_tokens,
        )
        custom_desktop = bool(desktop_file and not self._contains_browser_token(desktop_file, browser_tokens))
        custom_icon = bool(icon_name and not self._contains_browser_token(icon_name, browser_tokens))
        has_app_flag = '--app=' in commandline or '--app-id=' in commandline
        custom_app_name = bool(app_name and not generic_app_name)

        pwa_stream_name = self._extract_pwa_name(stream_name, browser) if stream_name else None
        if pwa_stream_name and not custom_app_name:
            app_name = pwa_stream_name
            custom_app_name = True
            generic_app_name = self._looks_like_browser_shell(app_name, browser_tokens)

        pwa_title = self._looks_like_app_name(media_title) if media_title else False
        has_real_media = bool(raw_media_title and len(raw_media_title.strip()) > 3)
        is_browser_shell = not has_real_media and generic_app_name and not pwa_title

        is_web_app = any(
            (
                has_app_flag,
                custom_desktop,
                custom_icon,
                custom_app_name,
                custom_app_name and not generic_stream_name and app_name.lower() == stream_name.lower(),
                pwa_title and not raw_media_title,
            )
        ) and not is_browser_shell

        if is_browser_shell:
            return {
                'kind': 'browser_shell',
                'kind_label': 'Navigateur',
                'icon': '🌐',
                'family': browser,
                'primary': browser_instance or browser,
                'secondary': app_name if app_name and app_name.lower() != browser.lower() else None,
                'raw_app_name': app_name,
                'raw_title': media_title,
                'raw_artist': media_artist,
            }

        if is_web_app:
            primary = app_name or site_name or media_title or stream_name or browser
            secondary_parts = []
            if content_title and content_title.lower() != primary.lower():
                secondary_parts.append(content_title)
            elif media_title and media_title.lower() != primary.lower():
                secondary_parts.append(media_title)
            if media_artist:
                secondary_parts.append(media_artist)
            return {
                'kind': 'browser_app',
                'kind_label': 'App web',
                'icon': '🧩',
                'family': browser,
                'primary': primary,
                'secondary': '  ·  '.join(part for part in secondary_parts if part),
                'raw_app_name': app_name,
                'raw_title': media_title,
                'raw_artist': media_artist,
            }

        primary = site_name or (app_name if not generic_app_name else '') or media_title or browser_instance or browser
        secondary_parts = []
        if content_title and content_title.lower() != primary.lower():
            secondary_parts.append(content_title)
        elif media_artist:
            secondary_parts.append(media_artist)
        elif media_title and media_title.lower() != primary.lower():
            secondary_parts.append(media_title)
        if media_artist and media_artist not in secondary_parts:
            secondary_parts.append(media_artist)
        elif app_name and not generic_app_name and app_name.lower() != primary.lower():
            secondary_parts.append(app_name)
        return {
            'kind': 'browser_site',
            'kind_label': 'Site',
            'icon': '🌐',
            'family': browser,
            'primary': primary,
            'secondary': '  ·  '.join(part for part in secondary_parts if part),
            'raw_app_name': app_name,
            'raw_title': media_title,
            'raw_artist': media_artist,
        }

    def _ambiguous_browser_streams(self, browser, binary):
        browser_tokens = self._browser_tokens(browser, binary)
        ambiguous = []
        for stream in getattr(self, '_streams', []):
            if not self._is_routeable_output_stream(stream):
                continue
            props = self._nodes.get(stream.id, {})
            stream_binary = (props.get('application.process.binary', '') or '').lower()
            stream_app = (props.get('application.name', '') or '').lower()
            if not any(token in stream_binary or token in stream_app for token in browser_tokens):
                continue

            stream_name = props.get('media.name', '') or stream.name or ''
            raw_title = props.get('media.title', '') or ''
            if self._is_generic_stream_title(raw_title or stream_name):
                ambiguous.append(stream)
        return sorted(ambiguous, key=lambda stream: stream.id)

    def _browser_instance_label(self, stream_id, browser, binary):
        ambiguous = self._ambiguous_browser_streams(browser, binary)
        if len(ambiguous) <= 1:
            return browser

        session_candidates = self._lookup_browser_session_candidates(browser, binary)
        if len(session_candidates) == len(ambiguous):
            for index, stream in enumerate(ambiguous):
                if stream.id == stream_id:
                    return session_candidates[index]

        for index, stream in enumerate(ambiguous, start=1):
            if stream.id == stream_id:
                return f'{browser} #{index}'

        return browser

    def _lookup_browser_session_candidates(self, browser, binary):
        session_file = self._latest_browser_apps_session_file(browser, binary)
        if session_file is None:
            return []

        try:
            raw_bytes = session_file.read_bytes()
        except Exception:
            return []

        urls = [
            match.decode('utf-8', errors='ignore')
            for match in re.findall(rb'https?://[^\x00-\x20"\']+', raw_bytes)
        ]

        labels = []
        seen = set()
        for url in urls:
            label = self._session_url_to_label(url)
            if not label or label in seen:
                continue
            seen.add(label)
            labels.append(label)
        return labels

    def _latest_browser_apps_session_file(self, browser, binary):
        for base_dir in self._browser_profile_dirs(browser, binary):
            sessions_dir = base_dir / 'Default' / 'Sessions'
            try:
                session_files = sorted(
                    sessions_dir.glob('Apps_*'),
                    key=lambda path: path.stat().st_mtime,
                    reverse=True,
                )
            except Exception:
                continue

            if session_files:
                return session_files[0]
        return None

    def _browser_profile_dirs(self, browser, binary):
        binary_lower = (binary or '').lower()
        browser_lower = browser.lower()
        home = Path.home()

        if 'edge' in binary_lower or browser_lower == 'edge':
            return [home / '.config' / 'microsoft-edge']
        if 'chromium' in binary_lower or browser_lower == 'chromium':
            return [home / '.config' / 'chromium']
        if 'brave' in binary_lower or browser_lower == 'brave':
            return [home / '.config' / 'BraveSoftware' / 'Brave-Browser']
        if 'vivaldi' in binary_lower or browser_lower == 'vivaldi':
            return [home / '.config' / 'vivaldi']
        if 'opera' in binary_lower or browser_lower == 'opera':
            return [home / '.config' / 'opera']
        return [home / '.config' / 'google-chrome']

    def _session_url_to_label(self, url):
        match = re.search(r'https?://([^/\s]+)', url)
        hostname = match.group(1).lower() if match else ''
        if not hostname:
            return None

        host_aliases = {
            'app.molotov.tv': 'Molotov',
            'molotov.tv': 'Molotov',
            'www.disneyplus.com': 'Disney+',
            'disneyplus.com': 'Disney+',
            'www.netflix.com': 'Netflix',
            'netflix.com': 'Netflix',
            'www.youtube.com': 'YouTube',
            'youtube.com': 'YouTube',
            'music.youtube.com': 'YouTube Music',
            'open.spotify.com': 'Spotify',
            'www.spotify.com': 'Spotify',
            'spotify.com': 'Spotify',
            'tv.apple.com': 'Apple TV',
            'www.primevideo.com': 'Prime Video',
            'primevideo.com': 'Prime Video',
            'www.twitch.tv': 'Twitch',
            'twitch.tv': 'Twitch',
        }
        return host_aliases.get(hostname)

    def _browser_tokens(self, browser, binary):
        tokens = {browser.lower(), binary.lower()}
        tokens.update(
            {
                'chrome',
                'chromium',
                'google-chrome',
                'microsoft-edge',
                'microsoft edge',
                'msedge',
                'edge',
                'brave',
                'brave-browser',
                'opera',
                'vivaldi',
                'firefox',
                'firefox-esr',
            }
        )
        return {token for token in tokens if token}

    def _contains_browser_token(self, value, browser_tokens):
        value_lower = value.lower()
        return any(token in value_lower for token in browser_tokens)

    def _extract_browser_site_and_title(self, media_title, app_name, browser_tokens):
        cleaned_title = (media_title or '').strip()
        cleaned_app = (app_name or '').strip()

        if not cleaned_title:
            if cleaned_app and not self._looks_like_browser_shell(cleaned_app, browser_tokens):
                return cleaned_app, ''
            return '', ''

        if self._looks_like_app_name(cleaned_title):
            return cleaned_title, ''

        for separator in (' | ', ' — ', ' - '):
            if separator not in cleaned_title:
                continue

            parts = [part.strip() for part in cleaned_title.split(separator) if part.strip()]
            if len(parts) < 2:
                continue

            first_part = parts[0]
            last_part = parts[-1]

            if self._looks_like_app_name(last_part):
                site_name = last_part
                content_title = separator.join(parts[:-1]).strip()
                return site_name, self._strip_repeated_site_prefix(content_title, site_name)

            if self._looks_like_app_name(first_part) and not self._looks_like_browser_shell(first_part, browser_tokens):
                site_name = first_part
                content_title = separator.join(parts[1:]).strip()
                return site_name, self._strip_repeated_site_prefix(content_title, site_name)

        if cleaned_app and not self._looks_like_browser_shell(cleaned_app, browser_tokens):
            return cleaned_app, cleaned_title if cleaned_title.lower() != cleaned_app.lower() else ''

        return '', cleaned_title

    @staticmethod
    def _strip_repeated_site_prefix(content_title, site_name):
        cleaned_content = (content_title or '').strip()
        cleaned_site = (site_name or '').strip()
        if not cleaned_content or not cleaned_site:
            return cleaned_content

        for separator in (' - ', ' — ', ': '):
            prefix = f'{cleaned_site}{separator}'
            if cleaned_content.startswith(prefix):
                return cleaned_content[len(prefix):].strip()

        return cleaned_content

    def _looks_like_browser_shell(self, value, browser_tokens):
        if not value:
            return True
        value_lower = value.lower().strip()
        generic_suffixes = (
            'web browser',
            'navigateur web',
            'browser',
        )
        return self._contains_browser_token(value_lower, browser_tokens) or value_lower.endswith(generic_suffixes)

    def _lookup_mpris_metadata(self, browser, binary):
        now = time.time()
        if now >= self._mpris_cache['expires_at']:
            self._mpris_cache = {
                'players': self._scan_mpris_players(),
                'expires_at': now + 3.0,
            }

        browser_tokens = self._mpris_browser_tokens(browser, binary)
        candidates = []
        for name, metadata in self._mpris_cache['players'].items():
            name_lower = name.lower()
            if any(token in name_lower for token in browser_tokens):
                candidates.append(metadata)

        if not candidates and browser in {'Chrome', 'Chromium', 'Edge', 'Brave', 'Opera', 'Vivaldi'}:
            for name, metadata in self._mpris_cache['players'].items():
                if 'chromium' in name.lower():
                    candidates.append(metadata)

        for candidate in candidates:
            if candidate.get('title') and not self._is_generic_stream_title(candidate['title']):
                return candidate

        return candidates[0] if candidates else {}

    def _mpris_browser_tokens(self, browser, binary):
        tokens = {browser.lower(), binary.lower()}
        if browser in {'Chrome', 'Chromium', 'Edge', 'Brave', 'Opera', 'Vivaldi'}:
            tokens.update({'chromium', 'chrome', 'edge', 'brave', 'opera', 'vivaldi'})
        elif browser in {'Firefox', 'Firefox ESR'}:
            tokens.update({'firefox', 'firefox-esr'})
        return {token for token in tokens if token}

    def _scan_mpris_players(self):
        players = {}
        try:
            list_cmd = [
                'gdbus',
                'call',
                '--session',
                '--dest',
                'org.freedesktop.DBus',
                '--object-path',
                '/org/freedesktop/DBus',
                '--method',
                'org.freedesktop.DBus.ListNames',
            ]
            result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=2, check=False)
            names = ast.literal_eval(result.stdout.strip() or '([],)')
            if isinstance(names, tuple):
                names = names[0]
            for name in names:
                if not str(name).startswith('org.mpris.MediaPlayer2.'):
                    continue
                metadata = self._read_mpris_metadata(str(name))
                if metadata:
                    players[str(name)] = metadata
        except Exception:
            return {}
        return players

    def _read_mpris_metadata(self, bus_name):
        cmd = [
            'gdbus',
            'call',
            '--session',
            '--dest',
            bus_name,
            '--object-path',
            '/org/mpris/MediaPlayer2',
            '--method',
            'org.freedesktop.DBus.Properties.Get',
            'org.mpris.MediaPlayer2.Player',
            'Metadata',
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
            stdout = result.stdout or ''
            title_match = re.search(r"'xesam:title': <'([^']*)'>", stdout)
            artist_match = re.search(r"'xesam:artist': <\[(.*?)\]>", stdout, re.DOTALL)
            artist = ''
            if artist_match:
                artists = re.findall(r"'([^']*)'", artist_match.group(1))
                artist = ' / '.join(filter(None, artists))
            return {
                'title': title_match.group(1) if title_match else '',
                'artist': artist,
                'source': bus_name,
            }
        except Exception:
            return {}

    def _looks_like_app_name(self, value):
        if not value or len(value) > 40:
            return False
        value_lower = value.lower().strip()
        page_title_indicators = (
            ' - ', ' | ', ' — ', '  ',
            'youtube.com', 'google.com', 'github.com',
            'http', 'www.',
        )
        for indicator in page_title_indicators:
            if indicator in value_lower:
                return False
        generic_terms = {
            'playback', 'audio', 'music', 'video', 'media',
            'stream', 'output', 'input', 'microphone', 'mic',
        }
        if value_lower in generic_terms:
            return False
        words = value_lower.split()
        if 1 <= len(words) <= 4 and not any(char in value for char in ':/?=&%'):
            return True
        return False

    def _extract_pwa_name(self, stream_name, browser):
        if not stream_name or not browser:
            return None
        browser_lower = browser.lower()
        stream_lower = stream_name.lower()
        for separator in (' — ', ' - ', ':'):
            if separator not in stream_lower:
                continue
            parts = stream_lower.split(separator, 1)
            if len(parts) != 2 or parts[0].strip() != browser_lower:
                continue
            app_candidate = parts[1].strip()
            if not app_candidate:
                continue
            app_candidate_lower = app_candidate.lower()
            if self._looks_like_browser_shell(app_candidate, self._browser_tokens(browser, '')):
                continue
            if app_candidate_lower in {
                'playback', 'audio', 'music', 'video', 'media',
                'stream', 'output', 'input', 'microphone', 'mic',
            }:
                continue
            original_parts = stream_name.split(separator, 1)
            return original_parts[1].strip()
        return None
