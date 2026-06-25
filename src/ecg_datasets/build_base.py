from utils.file_dir import ensure_directory_exists
from configs.constants import DATA_DIR

def build_base_dataset(args):
    print(f"Building {args.base}")
    if args.base == "mimic_iv":
        from ecg_datasets.base.mimic_iv import MIMIC_IV
        base_dataset_builder = MIMIC_IV(args)
    elif args.base == "ptb_xl":
        from ecg_datasets.base.ptb_xl import PTB_XL
        base_dataset_builder = PTB_XL(args)
    elif args.base == "code15":
        from ecg_datasets.base.code15 import CODE15
        base_dataset_builder = CODE15(args)
    elif args.base == "csn":
        from ecg_datasets.base.csn import CSN
        base_dataset_builder = CSN(args)
    elif args.base == "cpsc":
        from ecg_datasets.base.cpsc import CPSC
        base_dataset_builder = CPSC(args)
    elif args.base == "echonext":
        from ecg_datasets.base.echonext import EchoNext
        base_dataset_builder = EchoNext(args)
    elif args.base == "heed":
        from ecg_datasets.base.heed import HEED
        base_dataset_builder = HEED(args)


    if ensure_directory_exists(file = f"{DATA_DIR}/{args.base}/{args.base}.csv"):
        print("DF already exists")
        pass
    else:
        base_dataset_builder.prepare_df()
    
    print("Preparing DF")
    df = base_dataset_builder.get_df()
    base_dataset_builder.create_dataset(df)
