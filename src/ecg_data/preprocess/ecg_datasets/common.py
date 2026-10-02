import wfdb
import numpy as np
import matplotlib
from importlib import import_module
from pathlib import Path
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator, MaxNLocator

def get_dataset_module(data_name: str, data_root_path: str, package: str):
    module = import_module(f"{package}.{data_name}.{data_name}")
    dataset = getattr(module, data_name.upper())
    return dataset(data_name, data_root_path)

def open_wfdb(path: str):
    signal, fields = wfdb.rdsamp(path)
    return signal, fields

PTB_ORDER = ["I", "II", "III", "aVL", "aVR", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]

def plot_ecg(ecg, seconds=10, fs=250, output="ecg", figsize=(12, 9), linewidth=1.0):
    """Save a (12, samples) ECG in PTB_ORDER as PNG and PDF.

    Plot from time zero; seconds=None uses the entire recording.
    Each panel has its own grid and a horizontal reference at zero.
    All panels share the same amplitude scale. Input values are unchanged:
    no filtering, normalization, resampling, or baseline correction is applied.
    fs describes the input sampling rate; it does not resample the signal.
    """
    ecg = np.asarray(ecg)
    if ecg.ndim != 2 or ecg.shape[0] != 12 or ecg.shape[1] < 2:
        raise ValueError("ecg must have shape (12, samples), with at least 2 samples.")
    if not np.isfinite(fs) or fs <= 0:
        raise ValueError("fs must be positive and finite.")
    if seconds is not None and (not np.isfinite(seconds) or seconds <= 0):
        raise ValueError("seconds must be positive and finite, or None.")

    n = ecg.shape[1] if seconds is None else min(round(seconds * fs), ecg.shape[1])
    if n < 2:
        raise ValueError("The requested duration must contain at least 2 samples.")
    time = np.arange(n) / fs

    fig, axes = plt.subplots(6, 2, figsize=figsize, sharex=True, sharey=True)
    for i, lead in enumerate(PTB_ORDER):
        row, col = i % 6, i // 6
        ax = axes[row, col]
        ax.plot(time, ecg[i, :n], color="black", linewidth=linewidth, zorder=3)
        ax.set_title(lead, loc="left", pad=6)
        ax.margins(y=0.15)
        ax.set_axisbelow(True)
        ax.yaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.xaxis.set_minor_locator(AutoMinorLocator(5))
        ax.yaxis.set_minor_locator(AutoMinorLocator(2))
        ax.grid(which="major", color="#c8c8c8", linewidth=0.7)
        ax.grid(which="minor", color="#e8e8e8", linewidth=0.4)
        ax.axhline(0, color="#777777", linewidth=1.0, zorder=2)
        for spine in ax.spines.values():
            spine.set_color("#b0b0b0")
            spine.set_linewidth(0.8)
        ax.tick_params(axis="x", length=4, width=1.1)
        ax.tick_params(axis="y", labelleft=True, labelsize=10)

        if row < 5:
            ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)
        else:
            ax.set_xlabel("Time (s)", labelpad=8)

    axes[0, 0].set_xlim(0, n / fs)
    fig.subplots_adjust(left=0.065, right=0.985, bottom=0.08, top=0.96,
                        hspace=0.55, wspace=0.18)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    for extension in ["png"]:
        fig.savefig(f"{output}.{extension}", dpi=400,
                    bbox_inches="tight", facecolor="white")
    plt.close(fig)
