import argparse

def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="All args for preprocessing")
    parser.add_argument("--seed", type=int, default=0, help="Random Seed")
    parser.add_argument("--dev", action="store_true", default=None, help="Development mode")
    parser.add_argument("--base", type=str, default=None, 
                        choices=["mimic_iv", "ptb_xl", "code15", "cpsc", "csn", "echonext", "heed"],
                        help="Base dataset to preprocess")
    parser.add_argument("--map", type=str, default=None,
                        choices=["pretrain_mimic", "ecg_grounding", "ecg_qa_mimic_iv",
                                 "ecg_qa_ptb_xl", "ecg_instruct_45k", "ecg_bench_pulse",
                                 "ecg_instruct_pulse", "ecg_protocol_gg_cot", "ecg_comprehension", "heed"],
                        help="External dataset to map to base dataset")
    parser.add_argument("--input_type", type=str, nargs="+", default = None)
    parser.add_argument("--per_len", type = int, default = None)
    parser.add_argument("--ecg_numeric", type = str, nargs="+", default = None)
    parser.add_argument("--toy", type=float, default=None, help="Create a toy dataset of the specified percentage (0-1)")
    parser.add_argument("--mix", type=str, default=None, help="Mix data: comma-separated list of JSON filenames")
    parser.add_argument("--target_sf", type=int, default=250, help="Target sampling frequency")
    parser.add_argument("--upload_hf", action="store_true", default = None, help = "Specify if you want to upload_hf")
    parser.add_argument("--num_cores", type=int, default=64, help="Number of cores for parallel processing")
    parser.add_argument("--segment_len", type=int, default=2500, help="ECG Segment Length")
    parser.add_argument("--train_ecg_byte", action = "store_true", default = None, help = "Train ECG Byte BPE algorithm")
    parser.add_argument("--ecg_tokenizer", type = str, default = None, help = "path to ECG Tokenizer")
    parser.add_argument("--num_merges", type = int, default = None, help = "Number of merges for BPE")
    parser.add_argument("--ecg_byte_token_dist", action = "store_true", default = None, help = "Analyze the average token length distribution for ECG Byte")
    return parser.parse_args()
