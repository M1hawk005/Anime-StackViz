"""Publication-quality visual reporting."""

from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str((Path.cwd() / ".cache" / "matplotlib").resolve()))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import PrecisionRecallDisplay, RocCurveDisplay


COLORS = {"ink": "#172554", "blue": "#2563EB", "cyan": "#06B6D4", "coral": "#F97316", "grey": "#64748B"}


def _style() -> None:
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#CBD5E1",
        "axes.titleweight": "bold",
        "axes.titlesize": 13,
        "font.size": 10,
        "grid.color": "#E2E8F0",
        "grid.linewidth": 0.8,
    })


def create_overview(dataset: pd.DataFrame, output_path: str | Path) -> None:
    _style()
    frame = dataset.copy()
    yearly = frame.groupby(frame["CreationDate"].dt.year).agg(
        questions=("Id", "size"), response_rate=("answered_within_24h", "mean")
    )
    full_years = yearly.loc[yearly.index.to_series().between(2013, 2023)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Anime Stack Exchange: community responsiveness", fontsize=20, fontweight="bold", color=COLORS["ink"])
    fig.text(0.5, 0.94, "12,000+ questions observed from 2012–2024", ha="center", color=COLORS["grey"])

    axes[0, 0].plot(full_years.index, full_years["questions"], color=COLORS["blue"], linewidth=2.5, marker="o")
    axes[0, 0].set(title="Question volume peaked in 2015", xlabel="Year", ylabel="Questions")
    axes[0, 0].grid(axis="y")

    axes[0, 1].plot(full_years.index, full_years["response_rate"] * 100, color=COLORS["coral"], linewidth=2.5, marker="o")
    axes[0, 1].set(title="24-hour response rate over time", xlabel="Year", ylabel="Questions answered within 24h (%)")
    axes[0, 1].grid(axis="y")

    answered_hours = frame.loc[frame["hours_to_first_answer"].between(0, 168), "hours_to_first_answer"]
    axes[1, 0].hist(answered_hours, bins=35, color=COLORS["cyan"], edgecolor="white")
    axes[1, 0].axvline(24, color=COLORS["coral"], linestyle="--", label="24-hour target")
    axes[1, 0].set(title="Most responses arrive quickly", xlabel="Hours to first answer (responses within 7 days)", ylabel="Questions")
    axes[1, 0].legend(frameon=False)

    top_tags = frame.explode("tag_list").groupby("tag_list")["answered_within_24h"].agg(["size", "mean"])
    top_tags = top_tags.loc[top_tags["size"].ge(100)].sort_values("size", ascending=False).head(10).sort_values("size")
    axes[1, 1].barh(top_tags.index, top_tags["size"], color=COLORS["blue"])
    axes[1, 1].set(title="Most frequently used tags", xlabel="Questions", ylabel="")
    axes[1, 1].grid(axis="x")

    fig.text(0.01, 0.01, "Target: at least one answer posted within 24 hours. Partial 2012/2024 years omitted from annual panels.", color=COLORS["grey"], fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 0.92))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def create_model_evaluation(test: pd.DataFrame, probabilities: np.ndarray, metrics_path: str | Path, output_path: str | Path) -> None:
    _style()
    y_test = test["answered_within_24h"]
    metrics = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    RocCurveDisplay.from_predictions(y_test, probabilities, ax=axes[0])
    axes[0].plot([0, 1], [0, 1], linestyle="--", color=COLORS["grey"])
    axes[0].set_title("Discrimination")

    PrecisionRecallDisplay.from_predictions(y_test, probabilities, ax=axes[1])
    axes[1].axhline(y_test.mean(), linestyle="--", color=COLORS["grey"], label="Class prevalence")
    axes[1].set_title("Precision–recall")

    observed, predicted = calibration_curve(y_test, probabilities, n_bins=8, strategy="quantile")
    axes[2].plot(predicted, observed, marker="o", color=COLORS["cyan"], linewidth=2)
    axes[2].plot([0, 1], [0, 1], linestyle="--", color=COLORS["grey"])
    axes[2].set(title="Calibration", xlabel="Predicted probability", ylabel="Observed frequency")

    score = metrics["logistic_regression"]["roc_auc"]
    fig.suptitle(f"Chronological holdout evaluation — ROC AUC {score:.3f}", y=0.99, fontsize=17, fontweight="bold", color=COLORS["ink"])
    fig.text(0.5, 0.91, "Logistic regression using question text, tags, structure, and posting time", ha="center", color=COLORS["grey"])
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)
