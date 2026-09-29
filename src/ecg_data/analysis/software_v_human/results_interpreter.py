import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def load_all(run_dir: Path) -> pd.DataFrame:
    df = pd.read_csv(run_dir / "terms.csv")
    df = df.loc[df["cohort"] == "all"].copy()
    df = df[(df["original_report_count"] > 0) | (df["final_report_count"] > 0)]
    df["term"] = df["term"].str.lower()
    return df.sort_values(["category", "original_report_count"], ascending=[True, False])


def plot_term_analysis(run_dir: Path) -> None:
    run_dir = Path(run_dir)
    df = load_all(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())
    n = summary["analyzed_reports"]
    categories = list(dict.fromkeys(df["category"]))

    # 1. Report counts before vs after
    fig, axes = plt.subplots(
        len(categories), 1,
        figsize=(8, max(2.2, 0.38 * len(df) + 0.6 * len(categories))),
        sharex=True,
        gridspec_kw={"height_ratios": [max(2, (g["term"].nunique())) for _, g in df.groupby("category", sort=False)]},
    )
    if len(categories) == 1:
        axes = [axes]

    for ax, cat in zip(axes, categories):
        g = df[df["category"] == cat].iloc[::-1]
        y = range(len(g))
        ax.hlines(y, g["original_report_count"], g["final_report_count"], color="#b0b0b0", lw=1)
        ax.plot(g["original_report_count"], y, "o", ms=5, color="#4c78a8", label="Automated")
        ax.plot(g["final_report_count"], y, "o", ms=5, color="#f58518", label="Physician")
        ax.set_yticks(list(y), g["term"])
        ax.set_ylabel(cat, rotation=0, ha="right", va="center", labelpad=70)
        ax.tick_params(length=0)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        if ax is not axes[0]:
            ax.get_legend().remove() if ax.get_legend() else None
        else:
            ax.legend(frameon=False, loc="lower right")

    axes[-1].set_xlabel(f"Reports containing term  (n = {n:,})")
    fig.tight_layout()
    fig.savefig(run_dir / "term_counts.png", dpi = 200, bbox_inches="tight")
    plt.close(fig)

    # 2. Added / deleted ratios
    fig, (ax_add, ax_del) = plt.subplots(1, 2, figsize=(10, max(4, 0.28 * len(df))), sharey=False)

    added = df.sort_values("added_report_ratio", ascending=True)
    ax_add.barh(added["term"], added["added_report_ratio"].fillna(0), color="#4c78a8", height=0.7)
    ax_add.set_xlabel("Added ratio")
    ax_add.set_xlim(0, 1)

    deleted = df.sort_values("deleted_report_ratio", ascending=True)
    ax_del.barh(deleted["term"], deleted["deleted_report_ratio"].fillna(0), color="#e45756", height=0.7)
    ax_del.set_xlabel("Deleted ratio")
    ax_del.set_xlim(0, 1)

    for ax in (ax_add, ax_del):
        ax.tick_params(length=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    fig.tight_layout()
    fig.savefig(run_dir / "term_ratios.png", dpi = 200, bbox_inches="tight")
    plt.close(fig)

if __name__ == "__main__":
    plot_term_analysis("src/ecg_data/analysis/software_v_human/results/agh")
    plot_term_analysis("src/ecg_data/analysis/software_v_human/results/heedb_new")
    plot_term_analysis("src/ecg_data/analysis/software_v_human/results/heedb_old")