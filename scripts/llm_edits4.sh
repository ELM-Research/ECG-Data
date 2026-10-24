#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(cd "$SCRIPT_DIR/.." && pwd)"

SGLANG_URL="${SGLANG_URL:-http://127.0.0.1:30001}"
RETRY_DELAY="${RETRY_DELAY:-2}"
export no_proxy="localhost,127.0.0.1${no_proxy:+,$no_proxy}"
export NO_PROXY="$no_proxy"

uv run python -m ecg_data.analysis.software_v_human.main \
--config src/ecg_data/analysis/config/llm_edits_sglang2.yaml