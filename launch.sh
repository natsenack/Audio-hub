#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPLACE_RUNNING=0
ARGS=()

for ARG in "$@"; do
    if [[ "${ARG}" == "--replace" ]]; then
        REPLACE_RUNNING=1
        continue
    fi
    ARGS+=("${ARG}")
done

# Chercher l'app Python
if [[ -n "${AUDIO_HUB_APP_PATH:-}" ]]; then
    APP_PATH="${AUDIO_HUB_APP_PATH}"
elif [[ -n "${LINUX_AUDIO_MANAGER_APP_PATH:-}" ]]; then
    # Compatibilite avec l'ancien nom de variable.
    APP_PATH="${LINUX_AUDIO_MANAGER_APP_PATH}"
else
    APP_PATH="${ROOT_DIR}/audio-hub.py"
    if [[ ! -f "${APP_PATH}" ]]; then
        APP_PATH="/usr/share/audio-hub/audio-hub.py"
    fi
fi

# Chercher Python (venv en priorité, puis system)
if [[ -x "${ROOT_DIR}/.venv/bin/python3" ]]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "❌ python3 est introuvable"
    exit 1
fi

stop_running_instances() {
    if ! command -v pgrep >/dev/null 2>&1; then
        return
    fi

    while IFS= read -r PID; do
        [[ -n "${PID}" ]] || continue
        [[ "${PID}" != "$$" ]] || continue
        [[ -r "/proc/${PID}/cmdline" ]] || continue

        CMDLINE="$(tr '\0' ' ' < "/proc/${PID}/cmdline" 2>/dev/null || true)"
        case "${CMDLINE}" in
            *python*audio-hub.py*|*python*linux-audio-manager.py*)
                kill "${PID}" 2>/dev/null || true
                ;;
        esac
    done < <(pgrep -u "$(id -u)" -f 'audio-hub\.py|linux-audio-manager\.py' || true)

    sleep 0.3
}

if (( REPLACE_RUNNING )); then
    stop_running_instances
fi

# Lancer l'app
exec "${PYTHON_BIN}" "${APP_PATH}" "${ARGS[@]}"
