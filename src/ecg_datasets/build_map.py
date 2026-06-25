def build_map_dataset(args):
    print(f"Building {args.map}")
    if args.map == "pretrain_mimic":
        from ecg_datasets.map.pretrain_mimic import PretrainMIMIC
        map_dataset_builder = PretrainMIMIC(args)
    elif args.map == "ecg_grounding":
        from ecg_datasets.map.ecg_grounding import ECGGrounding
        map_dataset_builder = ECGGrounding(args)
    elif args.map == "ecg_qa_mimic_iv" or args.map == "ecg_qa_ptb_xl":
        from ecg_datasets.map.ecg_qa import ECGQA
        map_dataset_builder = ECGQA(args)
    elif args.map == "ecg_instruct_45k":
        from ecg_datasets.map.ecg_instruct_45k import ECGInstruct45k
        map_dataset_builder = ECGInstruct45k(args)
    elif args.map == "ecg_bench_pulse":
        from ecg_datasets.map.ecg_bench_pulse import ECGBenchPulse
        map_dataset_builder = ECGBenchPulse(args)
    elif args.map == "ecg_instruct_pulse":
        from ecg_datasets.map.ecg_instruct_pulse import ECGInstructPulse
        map_dataset_builder = ECGInstructPulse(args)
    elif args.map == "ecg_protocol_gg_cot":
        from ecg_datasets.map.ecg_protocol_gg_cot import ECGProtocolGGCot
        map_dataset_builder = ECGProtocolGGCot(args)
    elif args.map == "ecg_comprehension":
        from ecg_datasets.map.ecg_comprehension import ECGComprehension
        map_dataset_builder = ECGComprehension(args)
    elif args.map == "ecg_qa_cot":
        from ecg_datasets.map.ecg_qa_cot import ECGQACot
        map_dataset_builder = ECGQACot(args)
    elif args.map == "heed":
        from ecg_datasets.map.heed import HEED
        map_dataset_builder = HEED(args)

    map_dataset_builder.map_data()