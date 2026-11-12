#!/usr/bin/env bash
set -euo pipefail

# No --statements: all terms.py categories. Otherwise: only the supplied statements.
input=default
for arg in "$@"; do
  case "$arg" in
    --config|--runs|--pairs|--annotations|--help|-h) input=provided ;;
  esac
done

if [[ "$input" == default ]]; then
  set -- --config src/ecg_data/analysis/config/llm_edits_sglang2.yaml "$@"
fi

uv run python -m ecg_data.analysis.software_v_human.plot_llm_edits "$@"
