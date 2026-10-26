"""Shared chart style so every figure looks the same.

Colours are a fixed, colour-blind-checked palette. Each retailer always
keeps the same colour in every chart.
"""
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"

RETAILER_COLORS = {"Tesco": "#2a78d6", "Dunnes Stores": "#eb6834", "SuperValu": "#1baf7a"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
BLUE_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]


def apply():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "text.color": TEXT,
        "xtick.color": TEXT_2, "ytick.color": TEXT_2, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "legend.frameon": False,
    })


def title(fig, text):
    """Title aligned to the left edge of the whole figure (not the plot area)."""
    fig.suptitle(text, x=0.01, ha="left", fontsize=12, fontweight="bold", color=TEXT)


def source_note(fig, text):
    fig.text(0.01, 0.01, text, fontsize=8, color=TEXT_2, ha="left", va="bottom")
