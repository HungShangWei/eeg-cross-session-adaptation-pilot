#!/usr/bin/env python3
"""Draw two figures from saved values (display only, no new analysis).

Reads SHA-256-pinned results/primary_results.json and the frozen run config
as JSON, without importing research modules. The participant figure plots
/summary/participants: the nine saved seed-averaged J and C values for T
(temperature recalibration) and H (classification-head update). The separate
T-minus-H figure uses /primary/delta/mean and /primary/delta/two_sided95,
the ordinary two-sided 95% t interval (n=9, df=8), plus /NI_margin from the
configuration. No means, intervals or other statistics are re-estimated.

Requires Matplotlib. From the repository root:
    python scripts/plot_participant_results.py
writes results/figures/participant_results.png and
results/figures/loss_difference.png. Only display arithmetic and rounding
of label strings are used; plotted coordinates retain saved full precision.
"""
import hashlib
import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results" / "primary_results.json"
SOURCE_SHA256 = "3f8f341d4fb638a994e8a9a33af9767934fdc48a01e24a8bdd3020036d259184"
CONFIG = ROOT / "code" / "pilot" / "candidate" / "config" / "RUN_CONFIG_v1.json"
CONFIG_SHA256 = "3ed6a42a724ec0ac46047501b2f79db8d589d308f7484c60e2a0c712d9d5e9f8"
OUT = ROOT / "results" / "figures"

J_MAX, C_MIN = 0.20, 0.50
INK, INK_2, GRID, SURFACE, BAND = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#f0efeb"
SERIES = {"T": ("#2a78d6", "o", "T  temperature recalibration"),
          "H": ("#eb6834", "s", "H  classification-head update")}


def read_pinned_json(path, expected_hash):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        sys.exit(f"refusing: {path.relative_to(ROOT)} is not the pinned source")
    return json.loads(raw)


def style_axes(ax):
    ax.set_facecolor(SURFACE)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def participant_figure(data):
    rows = data["summary"]["participants"]
    people = [r["participant"] for r in rows]
    meets = {m: [r[f"{m}_J"] <= J_MAX and r[f"{m}_C"] >= C_MIN for r in rows] for m in SERIES}
    fig = plt.figure(figsize=(8, 10.6), facecolor=SURFACE)
    fig.text(0.12, 0.978, "Participant-level saved results", fontsize=18, va="top")
    axes = [fig.add_axes((0.12, 0.525, 0.84, 0.285)),
            fig.add_axes((0.12, 0.18, 0.84, 0.275))]
    panels = [("J", "Decision loss J (lower is better)", J_MAX, (-0.015, 0.37)),
              ("C", "Coverage C (higher is better)", C_MIN, (-0.035, 1.035))]
    for ax, (metric, title, threshold, limits) in zip(axes, panels):
        style_axes(ax)
        for i, p in enumerate(people):
            if meets["T"][i] and meets["H"][i]:
                ax.axvspan(p - 0.45, p + 0.45, color=BAND, zorder=0, lw=0)
        ax.axhline(threshold, color=INK_2, lw=1.4, zorder=1)
        if metric == "J":
            ax.text(0.55, threshold + 0.008, "Individual threshold J ≤ 0.20",
                    ha="left", va="bottom", color=INK_2, fontsize=13)
            ax.set_yticks([0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35])
        else:
            ax.text(9.45, threshold - 0.035, "Individual threshold C ≥ 0.50",
                    ha="right", va="top", color=INK_2, fontsize=13)
            ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        for method, offset in (("T", -0.14), ("H", 0.14)):
            color, marker, name = SERIES[method]
            ax.scatter([p + offset for p in people], [r[f"{method}_{metric}"] for r in rows],
                       s=75, color=color, marker=marker, edgecolors=SURFACE,
                       linewidths=1.8, zorder=3, label=name)
        ax.set_xticks(people)
        ax.set_xlim(0.4, 9.6)
        ax.set_ylim(*limits)
        ax.set_title(title, loc="left", fontsize=16, pad=12)
        ax.grid(axis="y", color=GRID, lw=1)
    axes[1].set_xlabel("Participant\nBCI Competition IV 2b · physical session 3 → 4", fontsize=13, labelpad=9)
    handles, labels = axes[0].get_legend_handles_labels()
    handles.append(plt.Rectangle((0, 0), 1, 1, color=BAND))
    labels.append("Shaded: both T and H meet J ≤ 0.20 and C ≥ 0.50")
    fig.legend(handles, labels, loc="upper left", ncol=1, frameon=False,
               bbox_to_anchor=(0.105, 0.95), fontsize=13, labelspacing=0.55)
    fig.text(0.12, 0.085,
             "Saved values: each point is one participant's mean over 3 seeds.\n"
             "10 permitted labels per update; display only, no new analysis.\n"
             "Extra axis space avoids marker clipping; it is not negative coverage.",
             fontsize=12, color=INK_2, va="top", linespacing=1.5)
    return fig


def loss_difference_figure(data, config):
    delta = data["primary"]["delta"]
    mean = delta["mean"]
    lower, upper = delta["two_sided95"]
    margin = config["NI_margin"]
    n, df = delta["n"], delta["df"]
    fig = plt.figure(figsize=(8, 5.6), facecolor=SURFACE)
    fig.text(0.08, 0.965, "Saved comparison: T − H decision loss", fontsize=18, va="top")
    fig.text(0.08, 0.885,
             "T = temperature recalibration\nH = classification-head update",
             fontsize=13, linespacing=1.45, color=INK_2, va="top")
    ax = fig.add_axes((0.10, 0.40, 0.85, 0.30))
    style_axes(ax)
    ax.axvline(0, color=INK_2, lw=1.4, linestyle=":", zorder=1)
    ax.axvline(margin, color=INK, lw=1.5, linestyle="--", zorder=1)
    ax.errorbar(mean, 0, xerr=[[mean - lower], [upper - mean]], fmt="o",
                color=SERIES["T"][0], markersize=8, elinewidth=2.2,
                capsize=7, capthick=2, zorder=3)
    ax.text(mean, 0.25, f"Mean {mean:.5f}\n95% t interval [{lower:.5f}, {upper:.5f}]",
            ha="center", va="bottom", fontsize=13, linespacing=1.4,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 3})
    ax.text(0, -0.26, "Zero", ha="center", va="top", fontsize=12, color=INK_2,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 2})
    ax.text(margin, 0.25, f"NI margin\n{margin:.2f}", ha="center", va="bottom", fontsize=13,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 3})
    ax.set_xlim(-0.009, 0.024)
    ax.set_ylim(-0.65, 0.9)
    ax.set_yticks([])
    ax.set_xticks([-0.005, 0, 0.005, 0.010, 0.015, 0.020])
    ax.set_xticklabels(["−0.005", "0", "0.005", "0.010", "0.015", "0.020"], fontsize=12)
    ax.set_xlabel("T − H in J · lower J is better", fontsize=13, labelpad=9)
    ax.spines["left"].set_visible(False)
    fig.text(0.08, 0.255,
             f"Ordinary two-sided 95% t interval; n = {n}, df = {df}.\n"
             "Each participant's 3 seeds were averaged first; n is not 54.",
             fontsize=12, color=INK_2, linespacing=1.45, va="top")
    fig.text(0.08, 0.145,
             "Numerical non-inferiority criterion met; equivalence not tested.\n"
             "Usefulness criteria were not met.\n"
             "Saved values; display only, no new analysis.",
             fontsize=12, linespacing=1.45, va="top")
    return fig


def main():
    data = read_pinned_json(SOURCE, SOURCE_SHA256)
    config = read_pinned_json(CONFIG, CONFIG_SHA256)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 14,
                         "axes.edgecolor": GRID, "axes.labelcolor": INK_2,
                         "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK})
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fig in [("participant_results.png", participant_figure(data)),
                      ("loss_difference.png", loss_difference_figure(data, config))]:
        fig.savefig(OUT / name, dpi=160, facecolor=SURFACE, metadata={"Software": None})
        plt.close(fig)
        print("wrote", (OUT / name).relative_to(ROOT))


if __name__ == "__main__":
    main()
