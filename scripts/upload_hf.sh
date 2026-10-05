#!/usr/bin/env bash
exec uv run python src/ecg_data/upload_hf.py "$@"
