uv run python -m ecg_data.analysis.software_v_human.inspect_edits \
--data-name heedb \
--data-path /batch_data/heedb/preprocessed_250_10 \
--terms "digitalis effect" "1st degree av block" "2nd degree av block" \
--examples 2 > examples.json