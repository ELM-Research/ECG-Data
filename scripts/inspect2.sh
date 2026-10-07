uv run python -m ecg_data.analysis.software_v_human.inspect_edits \
--data-name agh \
--data-path /batch_data/agh/filtered_batch_meta_data_v3 \
--terms "digitalis effect" "1st degree av block" "2nd degree av block" \
--examples 2 > examples2.json