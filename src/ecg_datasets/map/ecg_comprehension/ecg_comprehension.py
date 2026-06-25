from tqdm import tqdm
import glob
import string
from collections import Counter, defaultdict
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks, butter, sosfiltfilt

from ecg_datasets.map.map_dataset import SyntheticDataset
from configs.constants import DATA_DIR
from utils.file_dir import ensure_directory_exists, open_npy

class ECGComprehension(SyntheticDataset):
    def __init__(self, args):
        super().__init__(args)
        self.data_name = "mimic_iv"
        self.saved_dir = glob.glob(f"{DATA_DIR}/{self.data_name}/preprocessed_{self.args.segment_len}/*.npy")
        if self.args.input_type:
            input_type = "_".join(self.args.input_type)
            name = f"{input_type}_{self.args.per_len}"
        elif self.args.ecg_numeric:
            ecg_numeric_types = "_".join(self.args.ecg_numeric)
            name = f"{ecg_numeric_types}_{self.args.per_len}_{self.args.n_per_answer}"
        self.save_dir_json = f"src/ecg_datasets/map/ecg_comprehension/{self.args.map}_{name}_hf.json"

    def get_map_data(self,):
        if ensure_directory_exists(file=self.save_dir_json):
            print("ECG Comprehension json already exists")
        if self.args.input_type:
            data = self.create_input_type_json()
        elif self.args.ecg_numeric:
            data = self.create_ecg_numeric_json()
        return data

    def create_input_type_json(self):
        data = []
        # to ensure balance
        total_len = len(self.args.input_type) * self.args.per_len
        print("total len", total_len)
        prompt = "What type of signal is provided?"
        question, mapping = self.format_mcq_question(prompt, self.args.input_type)
        print("question", question)
        print("mapping", mapping)
        for i in tqdm(range(self.args.per_len)):
            for signal_type in self.args.input_type:
                if signal_type == "ecg":
                    ecg_path = self.saved_dir[i]
                else:
                    ecg_path = signal_type
                text = [{"from": "human", "value": question},
                        {"from": "gpt", "value": mapping[signal_type]}]
                name = signal_type
                data.append({
                    "ecg_path": ecg_path,
                    "text": text,
                    "name": name
                })
        return data
    
    def create_ecg_numeric_json(self):
        data = []
        total_len = len(self.args.ecg_numeric) * self.args.per_len
        print("total len", total_len)
        for i in tqdm(range(self.args.per_len)):
            for numeric_type in self.args.ecg_numeric:
                ecg_path = self.saved_dir[i]
                ecg = open_npy(ecg_path)["ecg"]
                if numeric_type == "r_peak_count":
                    prompt = "Given the ECG signal, count the number of R-peaks."
                    r_peak_count = self.r_peak_count(ecg, self.args.target_sf)
                    if r_peak_count is None:
                        continue
                    answer = f"{r_peak_count}"
                elif numeric_type == "heart_rate_bpm_int":
                    prompt = "Count the R-peaks in the ECG signal, then compute BPM = 60 x (Number of R-peaks) / (duration in seconds). Output only the BPM rounded to the nearest whole number."
                    hr_bpm = self.heart_rate_bpm(ecg, self.args.target_sf)
                    if hr_bpm is None:
                        continue
                    answer = f"{int(hr_bpm)}"
                elif numeric_type == "heart_rate_bpm_float":
                    prompt = "Count the R-peaks in the ECG signal, then compute BPM = 60 x (Number of R-peaks) / (duration in seconds). Output only the BPM rounded to two decimal places."
                    hr_bpm = self.heart_rate_bpm(ecg, self.args.target_sf)
                    if hr_bpm is None:
                        continue
                    answer = f"{hr_bpm:.2f}"
                text = [{"from": "human", "value": prompt},
                        {"from": "gpt", "value": answer }]
                name = numeric_type
                data.append({
                    "ecg_path": ecg_path,
                    "text": text,
                    "name": name
                })
        if self.args.n_per_answer:
            data = self.balance_per_answer(data)
        return self.filter_and_plot_numeric_distribution(data)

    def balance_per_answer(self, items):
        buckets = defaultdict(list)
        for item in items:
            buckets[item["text"][-1]["value"]].append(item)
        rng = np.random.default_rng(seed = 42)
        data = []
        for ans, group in buckets.items():
            if len(group) < self.args.n_per_answer:
                continue
            idx = rng.choice(len(group), size = self.args.n_per_answer, replace = False)
            data.extend(group[i] for i in idx)
        return data

    def filter_and_plot_numeric_distribution(self, data):
        answer_counts = Counter(item["text"][1]["value"] for item in data)
        filtered_data = [item for item in data if answer_counts[item["text"][1]["value"]] > 1]
        filtered_counts = Counter(item["text"][1]["value"] for item in filtered_data)
        plot_path = self.save_dir_json.replace(".json", f"_{self.args.n_per_answer}_distribution.png")
        self.save_distribution_plot(filtered_counts, plot_path)
        print(f"Discarded singleton numeric instances: {len(data) - len(filtered_data)}")
        return filtered_data

    def save_distribution_plot(self, counts: Counter, save_path: str):
        if not counts:
            plt.figure(figsize=(8, 4))
            plt.title("Numeric value distribution (no values after singleton filtering)")
            plt.xlabel("Numeric value")
            plt.ylabel("Count")
            plt.tight_layout()
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            plt.close()
            return

        sorted_items = sorted(counts.items(), key=lambda x: float(x[0]))
        labels = [k for k, _ in sorted_items]
        values = [v for _, v in sorted_items]
        plt.figure(figsize=(max(10, len(labels) * 0.35), 4))
        plt.bar(labels, values)
        plt.title("Numeric value distribution (singleton values removed)")
        plt.xlabel("Numeric value")
        plt.ylabel("Count")
        if len(labels) > 20:
            plt.xticks(rotation=90)
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close()

    def format_mcq_question(self, prompt: str, choices: list[str]) -> str:
        labels = string.ascii_uppercase[:len(choices)]
        mapping = dict(zip(choices, labels))
        question = prompt + "\n" + "\n".join(f"{k}) {v}" for k, v in mapping.items())
        return question, mapping
    
    def bandpass(self, sig: np.ndarray, fs: int, lo: float = 0.5, hi: float = 40.0, order: int = 3) -> np.ndarray:
        sos = butter(order, [lo, hi], btype="band", fs=fs, output="sos")
        return sosfiltfilt(sos, sig)


    def detect_r_peaks(self, lead: np.ndarray, fs: int) -> np.ndarray:
        """Energy-based R-peak detection (simplified Pan-Tompkins idea)."""
        filtered = self.bandpass(lead, fs)
        diff = np.diff(filtered)
        energy = diff ** 2
        # smooth with ~50 ms window
        win = max(int(0.05 * fs), 1)
        smoothed = np.convolve(energy, np.ones(win) / win, mode="same")
        threshold = np.mean(smoothed) + np.std(smoothed)
        peaks, _ = find_peaks(smoothed, distance=int(0.4 * fs), height=threshold)
        return peaks

    def r_peak_count(self, ecg: np.ndarray, fs: int) -> int:
        return len(self.detect_r_peaks(ecg[1], fs))

    def heart_rate_bpm(self, ecg: np.ndarray, fs: int) -> float | None:
        peaks = self.detect_r_peaks(ecg[1], fs)
        if len(peaks) < 2:
            return None
        rr = np.diff(peaks) / fs
        return float(60.0 / np.median(rr))