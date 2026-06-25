from argparse import Namespace

from ecg_datasets.build_base import build_base_dataset
from ecg_datasets.build_map import build_map_dataset

from ecg_tokenizer.build_ecg_tokenizer import BuildECGByte

from configs.configs import get_args

from utils.set_seed import set_seed

def main(args: Namespace):
    set_seed(args.seed)
    
    if args.base:
        build_base_dataset(args)

    if args.map:
        build_map_dataset(args)

    if args.train_ecg_byte:
        ecg_byte_builder = BuildECGByte(args)
        if args.num_merges:
            ecg_byte_builder.train_ecg_byte()


if __name__ == "__main__":
    main(get_args())