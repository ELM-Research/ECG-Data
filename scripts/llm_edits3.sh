#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(cd "$SCRIPT_DIR/.." && pwd)"

SGLANG_URL="${SGLANG_URL:-http://127.0.0.1:30001}"
RETRY_DELAY="${RETRY_DELAY:-2}"
export no_proxy="localhost,127.0.0.1${no_proxy:+,$no_proxy}"
export NO_PROXY="$no_proxy"
trap 'echo; echo "Stopping."; exit 130' INT TERM

retry_until_success() {
    local rc

    while true; do
        "$@"
        rc=$?

        if (( rc == 0 )); then
            return 0
        fi

        if (( rc == 130 || rc == 143 )); then
            return "$rc"
        fi

        echo
        echo "Command crashed with status ${rc}."
        echo "Retrying from its checkpoint in ${RETRY_DELAY} seconds..."
        sleep "$RETRY_DELAY"
    done
}

retry_until_success \
    uv run python -m ecg_data.analysis.software_v_human.main \
    --config src/ecg_data/analysis/config/llm_edits_sglang.yaml
    || exit $?